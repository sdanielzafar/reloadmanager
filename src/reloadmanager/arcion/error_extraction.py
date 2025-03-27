import re
import os


def find_error(log_file: str) -> str:
    if not os.path.exists(log_file):
        return ""

    with open(log_file, "r") as f:
        error_re: re.Pattern = re.compile(
            r"Error running query|HiveSQLException|DeltaAnalysisException|FAILED: Execution Error|"
            r"Failed to initialize pool"
        )
        unique_errors: set[str] = set([line for line in f if error_re.search(line)])

    if unique_errors:
        return unique_errors.pop()
    return ""

print(find_error("../../../tests/data/sample_error.log"))
