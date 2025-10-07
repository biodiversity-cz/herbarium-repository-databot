import boto3
import os
import tempfile
from src.config import config


class S3Storage:
    def __init__(self, bucket: str | None = None):
        self.bucket = bucket or config.get_s3_config("bucket")
        endpoint = config.get_s3_config("endpoint_url", None)

        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=config.get_s3_config("access_key"),
            aws_secret_access_key=config.get_s3_config("secret_key"),
            endpoint_url=endpoint,
        )

    def download_file(self, key: str) -> str:
        """
        Stáhni soubor z S3 a vrať cestu k lokálnímu dočasnému souboru.
        """
        fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(key)[-1])
        os.close(fd)
        self.s3.download_file(self.bucket, key, tmp_path)
        return tmp_path

    def cleanup_file(self, path: str):
        """Smaž dočasný lokální soubor."""
        try:
            os.remove(path)
        except FileNotFoundError:
            pass