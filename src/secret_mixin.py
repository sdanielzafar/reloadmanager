import os


class SecretMixin:
    @staticmethod
    def get_secret(key: str) -> str:
        try:
            return os.environ[key]
        except KeyError:
            raise RuntimeError(f"Missing required env var: {key}")
