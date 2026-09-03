import boto3
import logging
from botocore.config import Config as BotoConfig
from config import config
from enum import Enum

logger = logging.getLogger(__name__)


class BucketType(Enum):
    """Typ bucketu pro uložení obrázků."""
    THUMB = "thumb"
    FULLSIZE = "fullsize"


# Typ bucketu -> konfiguracni klic (s3.<key> v config.yaml, nebo env S3_<KEY>)
BUCKET_CONFIG_KEYS = {
    BucketType.THUMB: "thumb_bucket",
    BucketType.FULLSIZE: "fullsize_bucket",
}


class S3ConfigError(RuntimeError):
    """S3 konfigurace potřebná ke stažení obrázku chybí."""


class S3Storage:
    def __init__(self, thumb_bucket: str | None = None, fullsize_bucket: str | None = None):
        # Získání konfigurace bucketů - pokud nejsou explicitně zadány, použije se konfigurace
        self.thumb_bucket = thumb_bucket or config.get_s3_config("thumb_bucket")
        self.fullsize_bucket = fullsize_bucket or config.get_s3_config("fullsize_bucket")

        missing = config.missing_s3_config()
        if missing:
            # Tady to nahlásit - jinak se to objeví až o hodiny později jako
            # záhadné "unsupported operand type(s) for +: 'NoneType' and 'str'".
            logger.error(
                "Incomplete S3 configuration - missing %s "
                "(set s3.<key> in config.yaml or env S3_<KEY>)",
                ", ".join(missing),
            )

        endpoint = config.get_s3_config("endpoint_url", None)

        # Without explicit timeouts a dead S3 endpoint blocks the worker thread
        # forever, which in turn keeps a job (and its database connection slot)
        # occupied indefinitely.
        boto_config = BotoConfig(
            connect_timeout=config.get_http_int("s3_connect_timeout", 5),
            read_timeout=config.get_http_int("s3_read_timeout", 60),
            retries={
                "max_attempts": config.get_http_int("s3_max_attempts", 3),
                "mode": "standard",
            },
        )

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=config.get_s3_config("access_key"),
            aws_secret_access_key=config.get_s3_config("secret_key"),
            endpoint_url=endpoint,
            config=boto_config,
        )

    def _get_bucket(self, bucket_type: BucketType) -> str:
        """Získej název bucketu podle typu."""
        if bucket_type == BucketType.THUMB:
            return self.thumb_bucket
        elif bucket_type == BucketType.FULLSIZE:
            return self.fullsize_bucket
        raise ValueError(f"Unknown bucket type: {bucket_type!r}")

    @staticmethod
    def bucket_name(bucket: str, suffix: str | None) -> str:
        """Jméno bucketu včetně eventuelního číselného suffixu.

        photos.bucket_suffix je NULL pro fotky v základním bucketu - to není chyba,
        suffix se prost jen nepoužije. Přímé ``bucket + suffix`` na tom spadlo.
        """
        if suffix is None:
            return bucket
        suffix = str(suffix).strip()
        return bucket + suffix if suffix else bucket

    def download_file_to_path(self, bucket_type: BucketType, suffix: str, key: str, local_path: str):
        """
        Stáhni soubor z S3 na zadanou lokální cestu.
        
        Args:
            bucket_type: Typ bucketu (BucketType.THUMB nebo BucketType.FULLSIZE)
            suffix: Suffix pro číslování bucketů (např. '-1', '-2' atd.; NULL = základní bucket)
            key: Klíč souboru v S3
            local_path: Cesta kde uložit stažený soubor
        """
        bucket = self._get_bucket(bucket_type)
        config_key = BUCKET_CONFIG_KEYS.get(bucket_type, "bucket")
        if not bucket:
            raise S3ConfigError(
                f"No S3 bucket configured for {bucket_type.value} images "
                f"(set s3.{config_key} in config.yaml or env S3_{config_key.upper()})"
            )
        if not key:
            raise ValueError(f"Missing S3 object key ({key!r}) for a {bucket_type.value} image")

        self.s3.download_file(self.bucket_name(bucket, suffix), key, local_path)