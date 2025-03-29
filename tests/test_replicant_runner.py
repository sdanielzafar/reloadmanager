import os
import re
from collections import deque


def num_records(log_file) -> int:
    if not os.path.exists(log_file):
        raise Exception(f"No log file found: {log_file}")

    # open the file and go to the end, only keeping 10 lines in memory at a time
    with open(log_file, "r") as f:
        last_10_lines: list[str] = [line.strip() for line in deque(f, 10)]

    if "replicant exited with error code: 1" in "|".join(last_10_lines) or \
            "replicant exited with error code: 2" in "|".join(last_10_lines):
        return 0

    row_count_re: re.Pattern = re.compile(r"[^ ]* +([0-9]+) +.*")
    num_records: str = next(
        (row_count_re.match(s).groups()[0] for s in reversed(last_10_lines) if row_count_re.match(s)),
        None
    )
    if not num_records:
        if "replicant exited with error code: 0" in "|".join(last_10_lines):
            return 0
        last_10_fmt: str = "'\n\t'".join(last_10_lines)
        raise Exception(f"Issue parsing log file: \n\t'{last_10_fmt}'")

    return int(num_records)


print(num_records("data/sample_num_records_1.log"))
print(num_records("data/sample_num_records_2.log"))
