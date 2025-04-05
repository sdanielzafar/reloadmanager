import time
from threading import Event, Lock
from dataclasses import replace

from reloadmanager.clients.teradata_client import TeradataClient
from reloadmanager.event_loader.event_loader_thread import EventLoaderThread
from reloadmanager.event_loader.event_queue import EventQueue
from reloadmanager.event_loader.models import TrackerRecord, QueueRecord, TableAttrRecord
from reloadmanager.mixins.logging_mixin import LoggingMixin
from reloadmanager.utils.avoid_window import AvoidWindow
from reloadmanager.utils.datetimes import EventTime, validate_dt_fmt


class EventLoader(LoggingMixin):
    def __init__(self,
                 catalog: str,
                 tpt_threads: int = 8,
                 writenos_threads: int = 2,
                 starting_watermark: str = str(EventTime.now()),
                 table_metadata_csv: str = "/home/arcion/event_loader/table_metadata/TRTables.csv",
                 avoid_window_utc: str = "6-18",
                 sqlite_path: str = "/home/arcion/event_loader/sqlite/primary.db",
                 lock_rows: bool = True):

        self.catalog: str = catalog
        self.threads: dict = {"TPT": tpt_threads, "WriteNOS": writenos_threads}
        self.starting_watermark: str = validate_dt_fmt(starting_watermark)
        self.watermark: EventTime = EventTime(validate_dt_fmt(starting_watermark))
        self.table_metadata_csv = table_metadata_csv
        self.run_name: str = f"EventLoader_{str(EventTime.now())}"
        self.avoid_window: AvoidWindow | None = AvoidWindow(avoid_window_utc) if "-" in avoid_window_utc else None
        self.lock_rows_default: bool = lock_rows
        self.queue: EventQueue = EventQueue(sqlite_path)
        self.stop_signal: Event = Event()
        self.output_lock: Lock = Lock()
        self.log_lock: Lock = Lock()
        self.td_client: TeradataClient = TeradataClient()

    def query_tracking_table(self) -> list[TrackerRecord]:
        now: EventTime = EventTime.now()
        rows = self.td_client.query(f"""
            SELECT 
                ObjectDatabaseName || '.' || ObjectTableName as tbl, 
                LoadCompletionTS as reload_ts 
            FROM BACKUPDB.EBI_LOAD_COMPLETION_TS_GOLD 
            WHERE LoadCompletionTS > {self.watermark}
        """)
        self.watermark = now
        return [TrackerRecord(tbl, EventTime(ts)) for tbl, ts in rows]

    @staticmethod
    def set_priority(load_time: str, min_staleness: int, max_staleness: int) -> int:
        staleness: int = int(time.time()) - EventTime(load_time)
        if staleness < min_staleness:
            return 0
        else:
            match max_staleness - staleness:
                case t if t > 60:
                    return 1
                case t if t > 45:
                    return 2
                case t if t > 30:
                    return 3
                case t if t > 15:
                    return 4
                case t if t > 10:
                    return 5
                case t if t > 5:
                    return 6
                case t if t > 3:
                    return 7
                case t if t > 2:
                    return 8
                case t if t > 1:
                    return 9
                case t if t > 0:
                    return 10
                case t if t > -5:
                    return 15
                case t if t > -10:
                    return 20

    # this uses the walrus operator :=, it just makes an intermediary variable available during for comprehension
    def update_priority(self, queued_tables: list[QueueRecord], new_tables: list[TrackerRecord]) -> list[QueueRecord]:
        tables: set[str] = {r.source_table for r in new_tables} | {q.source_table for q in queued_tables}
        with open(self.table_metadata_csv, "r") as f:
            tbl_metadata: dict[str, TableAttrRecord] = {
                r.source_table: r for line in f if (r := TableAttrRecord.from_csv(line)).source_table in tables
            }

        # augment the new tables with the metadata
        new_tables_queue: list[QueueRecord] = [
            QueueRecord(
                source_table,
                (attrs := tbl_metadata[source_table]).target_table,
                str(event_time),
                None,
                attrs.strategy,
                True,
                'Q',
                attrs.priority
            ) for source_table, event_time in new_tables
        ]

        # update priorities for all, sorry this is ugly
        return [
            replace(t,
                    priority=self.set_priority(
                        t.event_time,
                        (attrs := tbl_metadata[t.source_table]).min_staleness,
                        attrs.max_staleness
                    ) * attrs.priority
                    )
            for t in queued_tables + new_tables_queue
        ]

    def create_workers(self, strategy, count) -> list[EventLoaderThread]:
        if count > 0:
            self.logger.info(f"Creating {count} {strategy} threads...")
            threads = [
                EventLoaderThread(i, strategy, self.run_name, self.stop_signal) for i in range(count)
            ]
            for thread in threads:
                thread.start()
            return threads

    def num_active_threads(self):
        threads: list[EventLoaderThread] = self.threads["TPT"] + self.threads["WriteNOS"]
        return len([t for t in threads if t.is_alive()])

    def run(self):
        self.queue.create_queue()

        self.threads["TPT"]: list[EventLoaderThread] = self.create_workers("TPT", self.threads["TPT"])
        self.threads["WriteNOS"]: list[EventLoaderThread] = self.create_workers("WriteNOS", self.threads["WriteNOS"])

        try:
            while True:
                # grab tables from the Teradata tracking table
                self.logger.info(f"Querying tracking table with watermark {str(self.watermark)}.")
                new_tables: list[TrackerRecord] = self.query_tracking_table()
                self.logger.info(f"Found {len(new_tables)} tables to enqueue.")

                # grab tables from queue
                queue_tables: list[QueueRecord] = self.queue.in_queue

                # grab the table details from the flat file and update priority
                new_tables: list[QueueRecord] = self.update_priority(queue_tables, new_tables)

                if not new_tables:
                    self.logger.info(f"No tables in queue")
                    time.sleep(60)
                    continue

                # put them in the queue
                self.queue.upsert_queued(new_tables)
                self.logger.info(f"Enqueud new tables and updated priorities.")

                num_queued: int = len(new_tables)
                self.logger.info(f"PROGRESS: {num_queued} tables in queue")
                if num_queued > 0 and self.num_active_threads() == 0:
                    raise RuntimeError(f"{num_queued} items in queue, but no active threads.")

                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received. Sending stop signal for active threads...")
            self.stop_signal.set()

        for thread in self.threads["TPT"] + self.threads["WriteNOS"]:
            thread.join()
