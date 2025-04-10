from datetime import datetime
from zoneinfo import ZoneInfo


def validate_dt_fmt(dt_string: str) -> str:
    try:
        datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
        return dt_string
    except ValueError:
        raise ValueError(f"Datetime passed {dt_string} is incorrect. Must match format '%Y-%m-%d %H:%M:%S'")


tz = ZoneInfo("America/Phoenix")


class EventTime(int):
    def __new__(cls, ts_str: str | None):
        if ts_str is None:
            raise ValueError("None is not a valid EventTime")
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        dt_phx = dt.replace(tzinfo=tz)
        epoch = int(dt_phx.timestamp())
        return super().__new__(cls, epoch)

    def __str__(self):
        return datetime.fromtimestamp(int(self), tz=tz).strftime("%Y-%m-%d %H:%M:%S")

    def to_datetime(self) -> datetime:
        return datetime.fromtimestamp(int(self), tz=tz)

    @classmethod
    def now(cls):
        return cls(datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"))

    @classmethod
    def from_epoch(cls, epoch: int):
        return super().__new__(cls, epoch)

