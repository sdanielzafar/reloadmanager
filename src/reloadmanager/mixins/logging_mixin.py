import logging


class LoggingMixin:
    @property
    def logger(self):
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.getLogger().getEffectiveLevel())

        if not logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setLevel(logging.getLogger().getEffectiveLevel())
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger
