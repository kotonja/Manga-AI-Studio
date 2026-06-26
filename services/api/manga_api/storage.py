from __future__ import annotations

import boto3

from manga_api.config import get_settings


class ObjectStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            region_name=self.settings.s3_region,
        )

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.settings.s3_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.settings.s3_bucket_name, Key=key)
        return response["Body"].read()

    def public_url(self, key: str) -> str:
        public_base = self.settings.s3_public_url.rstrip("/")
        return f"{public_base}/{self.settings.s3_bucket_name}/{key}"

    def check(self) -> None:
        self.client.head_bucket(Bucket=self.settings.s3_bucket_name)


def get_object_storage() -> ObjectStorage:
    return ObjectStorage()
