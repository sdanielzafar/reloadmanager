import os


class SecretMixin:
    @staticmethod
    def get_secret(key: str) -> str:
        try:
            return os.environ[key]
        except KeyError:
            raise RuntimeError(f"Missing required env var: {key}")

    @staticmethod
    def load_env_file(path=".env"):
        if not os.path.exists(path):
            raise FileNotFoundError(f"No .env file found at {path}")

        with open(path) as f:
            for line in f:
                line = line.strip()

                # skip comments and blank lines
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    continue  # invalid line format

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                os.environ[key] = value
