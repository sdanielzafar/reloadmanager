import logging


class LoggingMixin:
    @property
    def logger(self):
        return logging.getLogger(self.__class__.__name__)