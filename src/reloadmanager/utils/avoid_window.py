from reloadmanager.mixins.logging_mixin import LoggingMixin
from datetime import datetime
import time


class AvoidWindow(LoggingMixin):
    def __init__(self, window_str: str):
        self.start, self.end = [int(t) for t in window_str.split("-")]
        if self.start > self.end:
            raise Exception(
                f"Logic assumes start time < end time, please revise code if needed. {self.start} > {self.end}"
            )
        self.asleep: bool = False

    def check(self):
        now = datetime.now().hour
        if self.start <= now < self.end:
            if not self.asleep:
                self.logger.info(f"It is {datetime.now()}, putting job to sleep...zzZZzz")
            time.sleep(60 * 5)
            self.check()
        else:
            if self.asleep:
                self.logger.info(f"It is {datetime.now()}, waking up job...*yawn*")
