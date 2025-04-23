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
                 reset_queue: bool = False,
                 table_metadata_csv: str = "/home/arcion/event_loader/table_metadata/TRTables.csv",
                 avoid_window_utc: str = "6-18",
                 sqlite_path: str = "/home/arcion/event_loader/sqlite/primary.db",
                 lock_rows: bool = True):

        self.catalog: str = catalog
        self.threads: dict = {"TPT": tpt_threads, "WriteNOS": writenos_threads}
        self.thread_pool: dict[str, list[EventLoaderThread]] = {"TPT": [], "WriteNOS": []}
        self.table_metadata_csv = table_metadata_csv
        self.run_name: str = f"EventLoader_{str(EventTime.now()).replace(' ', 'T').replace(':', '-')}"
        self.avoid_window: AvoidWindow | None = AvoidWindow(avoid_window_utc) if "-" in avoid_window_utc else None
        self.lock_rows_default: bool = lock_rows
        self.sqlite_path: str = sqlite_path
        self.queue: EventQueue = EventQueue(sqlite_path)
        self.reset_queue: bool = reset_queue
        self.watermark: EventTime = EventTime(validate_dt_fmt(starting_watermark))
        self.stop_signal: Event = Event()
        self.output_lock: Lock = Lock()
        self.log_lock: Lock = Lock()
        self.td_client: TeradataClient = TeradataClient()

    def init_watermark(self):
        """
        If there are things in the queue or queue history then the starting watermark is the latest timestamp from those
        If these are empty then we use the starting timestamp.
        We assume that all running jobs have been re-queued before this is called.
        """
        last_load_time: str = self.queue.last_load_time()
        if last_load_time:
            self.logger.info(f"Determined watermark from the queue: {last_load_time}.")
            self.watermark = EventTime(last_load_time)
        else:
            self.logger.info(f"Using starting watermark: {str(self.watermark)}.")

    def query_tracking_table(self) -> list[TrackerRecord]:
        td_query: str = f"""
            SELECT 
                ObjectDatabaseName || '.' || ObjectTableName as tbl, 
                LoadCompletionTS as reload_ts 
            FROM EDWPC_SYNC.EBI_LOAD_COMPLETION_GOLD 
            WHERE LoadCompletionTS > '{self.watermark}'
            AND LoadCompletionTS <= '{EventTime.now()}' 
        """
        self.logger.debug(f"Teradata query: {td_query}")
        rows = self.td_client.query(td_query, max_attempts=200)
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
                case _:
                    return 25

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
                record.source_table,
                f"{self.catalog}.{(attrs := tbl_metadata[record.source_table]).target_table}",
                str(record.event_time),
                None,
                attrs.strategy,
                True,
                'Q',
                attrs.priority,
                None
            ) for record in new_tables
            # some tables in tracking table are actually CDC, so we only include if they are in the metadata table
            if record.source_table in tbl_metadata.keys()
        ]

        self.logger.info(f"Found {len(new_tables_queue)} tables to enqueue.")
        self.logger.debug(f"{str(new_tables_queue)}")

        # update priorities for all, sorry this is ugly
        return [
            replace(
                t,
                priority=self.set_priority(
                    t.event_time,
                    (attrs := tbl_metadata[t.source_table]).min_staleness,
                    attrs.max_staleness
                ) * attrs.priority
            ) for t in queued_tables + new_tables_queue
        ]

    def create_workers(self, strategy, count) -> list[EventLoaderThread]:
        if count > 0:
            self.logger.info(f"Creating {count} {strategy} threads...")
            threads = [
                EventLoaderThread(i, strategy, self.run_name, self.sqlite_path, self.stop_signal)
                for i in range(count)
            ]
            for thread in threads:
                thread.start()
            return threads
        return []

    def num_active_threads(self):
        threads: list[EventLoaderThread] = self.thread_pool["TPT"] + self.thread_pool["WriteNOS"]
        return len([t for t in threads if t.is_alive()])

    def run(self):
        self.logger.info(f"Initializing..")
        self.queue.create()
        if self.reset_queue:
            self.logger.info("Clearing the queue...")
            self.queue.truncate()
        else:
            self.queue.requeue_running()

        self.init_watermark()

        self.thread_pool["TPT"]: list[EventLoaderThread] = self.create_workers("TPT", self.threads["TPT"])
        self.thread_pool["WriteNOS"]: list[EventLoaderThread] = self.create_workers("WriteNOS", self.threads["WriteNOS"])

        try:
            while True:
                # grab tables from the Teradata tracking table
                self.logger.info(f"Querying tracking table with watermark: {str(self.watermark)}.")
                updated_tables: list[TrackerRecord] = self.query_tracking_table()

                # grab tables from queue
                queue_tables: list[QueueRecord] = self.queue.in_queue

                # grab the table details from the flat file and update priority
                new_tables: list[QueueRecord] = self.update_priority(queue_tables, updated_tables)

                if not new_tables:
                    self.logger.info(f"No tables in queue")
                    time.sleep(60)
                    continue

                # put them in the queue
                self.queue.upsert_queued(new_tables)
                self.logger.info(f"Enqueud new tables and updated priorities.")

                # update watermark
                self.watermark = self.queue.last_load_time()

                num_queued: int = len(new_tables)
                self.logger.info(f"PROGRESS: {num_queued} tables in queue")
                if num_queued > 0 and self.num_active_threads() == 0:
                    raise RuntimeError(f"{num_queued} items in queue, but no active threads.")

                time.sleep(120)
        except KeyboardInterrupt:
            self.logger.info("Interrupt received. Sending stop signal for active threads...")
            self.stop_signal.set()

        for thread in self.thread_pool["TPT"] + self.thread_pool["WriteNOS"]:
            thread.join()
