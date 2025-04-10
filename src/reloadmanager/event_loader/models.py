from dataclasses import dataclass, fields

from reloadmanager.utils.datetimes import EventTime


@dataclass(frozen=True)
class TrackerRecord:
    source_table: str
    event_time: EventTime


@dataclass()
class QueueRecord:
    source_table: str
    target_table: str
    event_time: str
    trigger_time: str | None
    strategy: str
    lock_rows: bool
    status: str
    priority: int
    event_time_latest: str | None

    def __getitem__(self, index):
        f = (
            self.source_table,
            self.target_table,
            self.event_time,
            self.trigger_time,
            self.strategy,
            self.lock_rows,
            self.status,
            self.priority,
            self.event_time_latest
        )
        return f[index]

    def __len__(self):
        return 9


@dataclass(frozen=True)
class TableAttrRecord:
    source_table: str
    target_table: str
    strategy: str
    disabled: bool
    priority: int
    min_staleness: int
    max_staleness: int

    @classmethod
    def from_csv(cls, line_str: str):
        line: list[str] = line_str.split(",")
        if len(line) != len(fields(cls)):
            raise ValueError(f"CSV line {line} should have {len(fields(cls))} fields")

        source_table, target_table, strategy, disabled, priority, min_staleness, max_staleness = line

        if not target_table:
            target_table = source_table

        if not min_staleness:
            min_staleness = 0

        def valid_table(s: str) -> str | None:
            if s:
                if len(s.split(".")) != 2:
                    raise ValueError(f"Table '{s}' must have 2 namespaces in the input config file")
                return s
            return None

        if strategy not in ["TPT", "WriteNOS"]:
            raise ValueError(f"Input line: {line} has invalid method. Should be 'TPT' or 'WriteNOS'")

        if disabled.strip().lower() not in ["true", "false"]:
            raise ValueError(f"Input line: {line} has invalid disabled status. Should be 'true' or 'false'")
        disabled = disabled.strip().lower() == "true"

        return cls(
            valid_table(source_table),
            valid_table(target_table),
            strategy,
            disabled,
            int(priority),
            int(min_staleness or 0),
            int(max_staleness)
        )
