from dataclasses import dataclass


@dataclass(frozen=True)
class InputRecord:
    source: str
    target: str
    strategy: str
    lock_rows: bool

    @classmethod
    def from_csv(cls, line: str, lock_row_default: bool):
        def valid_table(s: str, n: int):
            if len(s.split(".")) != n:
                raise ValueError(f"Table '{s}' must have {n} namespaces in the input config file")
            return s

        source, target, method, *lock_rows_str = line.split(",")
        if method not in ["TPT", "WriteNOS"]:
            raise ValueError(f"Input line: {line} has invalid method. Should be 'TPT' or 'WriteNOS'")

        lock_rows = lock_row_default
        if lock_rows_str:
            if lock_rows_str[0].strip().lower() not in ["true", "false"]:
                raise ValueError(f"Input line: {line} has invalid lock rows. Should be 'true' or 'false'")
            lock_rows = lock_rows_str[0].strip().lower() == "true"
        return cls(valid_table(source, 2), valid_table(target, 3), method, lock_rows)
