import boto3
from config import config
from enum import Enum


class BucketType(Enum):
    """Typ bucketu pro uložení obrázků."""
    THUMB = "thumb"
    FULLSIZE = "fullsize"


class S3Storage:
    def __init__(self, thumb_bucket: str | None = None, fullsize_bucket: str | None = None):
        # Získání konfigurace bucketů - pokud nejsou explicitně zadány, použije se konfigurace
        self.thumb_bucket = thumb_bucket or config.get_s3_config("thumb_bucket")
        self.fullsize_bucket = fullsize_bucket or config.get_s3_config("fullsize_bucket")
        
        endpoint = config.get_s3_config("endpoint_url", None)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=config.get_s3_config("access_key"),
            aws_secret_access_key=config.get_s3_config("secret_key"),
            endpoint_url=endpoint,
        )

    def _get_bucket(self, bucket_type: BucketType) -> str:
        """Získej název bucketu podle typu."""
        if bucket_type == BucketType.THUMB:
            return self.thumb_bucket
        elif bucket_type == BucketType.FULLSIZE:
            return self.fullsize_bucket

    def download_file_to_path(self, bucket_type: BucketType, suffix: str, key: str, local_path: str):
        """
        Stáhni soubor z S3 na zadanou lokální cestu.
        
        Args:
            bucket_type: Typ bucketu (BucketType.THUMB nebo BucketType.FULLSIZE)
            suffix: Suffix pro číslování bucketů (např. '-1', '-2' atd.)
            key: Klíč souboru v S3
            local_path: Cesta kde uložit stažený soubor
        """
        bucket = self._get_bucket(bucket_type)
        self.s3.download_file(bucket + suffix, key, local_path)