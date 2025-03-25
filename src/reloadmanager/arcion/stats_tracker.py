class RunStatsTracker:
    durations: list[tuple[str, str, float]] = []

    @classmethod
    def record(cls, table: str, status: str, minutes: float) -> None:
        cls.durations.append((table, status, minutes))

    @classmethod
    def generate_report(cls, csv_path: str) -> None:
        with open(csv_path, 'w') as file:
            if not cls.durations:
                file.write("No runs recorded.")
            file.write("TABLE,STATUS,DURATION_MINS\n")
            for record in cls.durations:
                file.write(f"{record[0]},{record[1]},{record[2]: .2f}\n")
