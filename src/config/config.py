import os
import yaml


def _is_configured(value) -> bool:
    """None and empty strings mean "not configured" and fall through to env.

    Without this a key that exists in config.yaml but is empty (typical when the
    file is mounted from a ConfigMap and the real value is injected as an env var)
    silently shadows the environment variable and the bot ends up with None,
    which later surfaces as an obscure "NoneType + str" TypeError.
    """
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


class Config:
    def __init__(self, path="src/config.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        data = data or {}

        self.connection = data.get("connection", {}) or {}
        self.pool = self.connection.get("pool", {}) or {}
        self.bots = data.get("bots", {}) or {}
        self.application = data.get("application", {}) or {}
        self.s3 = data.get("s3", {}) or {}
        self.http = data.get("http", {}) or {}

    def get_bot_config(self, bot_name):
        return self.bots.get(bot_name, {})

    def _lookup(self, section: dict, key: str, env_prefix: str, default=None):
        """section.<key> -> <env_prefix><KEY> -> default."""
        if key in section and _is_configured(section[key]):
            return section[key]
        env = os.getenv(f"{env_prefix}{key.upper()}")
        if _is_configured(env):
            return env
        return default

    def get_database_config(self, key, default=None):
        return self._lookup(self.connection, key, "DB_", default)

    def get_pool_config(self, key, default=None):
        """Database pool settings: connection.pool.<key>, or DB_POOL_<KEY>."""
        return self._lookup(self.pool, key, "DB_POOL_", default)

    def get_pool_int(self, key, default: int) -> int:
        return self._as_int(self.get_pool_config(key, default), default)

    def get_application_config(self, key, default=None):
        return self._lookup(self.application, key, "APP_", default)

    def get_application_int(self, key, default: int) -> int:
        """Same as get_application_config but always returns an int."""
        return self._as_int(self.get_application_config(key, default), default)

    def get_s3_config(self, key: str, default=None):
        return self._lookup(self.s3, key, "S3_", default)

    def missing_s3_config(self) -> list[str]:
        """s3 keys required to download images that are not configured at all."""
        return [
            key
            for key in ("thumb_bucket", "fullsize_bucket", "access_key", "secret_key")
            if not _is_configured(self.get_s3_config(key))
        ]

    def get_http_config(self, key: str, default=None):
        """Outbound HTTP/S3 settings: http.<key>, or HTTP_<KEY>."""
        return self._lookup(self.http, key, "HTTP_", default)

    def get_http_int(self, key: str, default: int) -> int:
        return self._as_int(self.get_http_config(key, default), default)

    def get_http_timeout(self, read_timeout_key: str = "read_timeout", default_read: int = 60) -> tuple[int, int]:
        """(connect, read) tuple as requests understands it."""
        return (
            self.get_http_int("connect_timeout", 5),
            self.get_http_int(read_timeout_key, default_read),
        )

    @staticmethod
    def _as_int(value, default: int) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_bool(value) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_application_bool(self, key, default: bool = False) -> bool:
        return self._as_bool(self.get_application_config(key, default))
