"""Shared storage for the serverless deployment: one small JSON object per record in an S3 bucket.

Lambda runs many copies of the app at once and each has its own disk, so trials, classes, re-hearings and uploaded
books live in S3 (WHYCOURT_BUCKET) where every copy sees them. Without the variable, the JSON files are used.
Each record is its own object, so two children never overwrite each other's trials.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

BUCKET = os.getenv("WHYCOURT_BUCKET", "")
PREFIX = "whycourt/data/"


@lru_cache(maxsize=1)
def _s3():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"),
                        config=Config(max_pool_connections=32))   # all() reads 16 records at once


def on() -> bool:
    return bool(BUCKET)


def put(kind: str, key: str, record: dict) -> None:
    _s3().put_object(Bucket=BUCKET, Key=f"{PREFIX}{kind}/{key}.json", Body=json.dumps(record).encode(),
                     ContentType="application/json")


def get(kind: str, key: str) -> dict | None:
    try:
        body = _s3().get_object(Bucket=BUCKET, Key=f"{PREFIX}{kind}/{key}.json")["Body"].read()
    except _s3().exceptions.NoSuchKey:
        return None
    return json.loads(body)


def all(kind: str) -> list[dict]:
    keys = []
    for page in _s3().get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"{PREFIX}{kind}/"):
        keys += [o["Key"] for o in page.get("Contents", [])]
    if not keys:
        return []

    def read(k: str) -> dict | None:
        try:
            return json.loads(_s3().get_object(Bucket=BUCKET, Key=k)["Body"].read())
        except Exception:
            return None
    with ThreadPoolExecutor(16) as pool:
        return [r for r in pool.map(read, keys) if r]


def mark(index: str, key: str) -> None:
    """An empty marker object (index/key): listing an index never races, unlike a shared list being rewritten."""
    _s3().put_object(Bucket=BUCKET, Key=f"{PREFIX}{index}/{key}", Body=b"")


def marked(index: str) -> list[str]:
    keys = []
    for page in _s3().get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=f"{PREFIX}{index}/"):
        keys += [o["Key"].rsplit("/", 1)[1] for o in page.get("Contents", [])]
    return keys


def get_many(kind: str, keys: list[str]) -> list[dict]:
    with ThreadPoolExecutor(16) as pool:
        return [r for r in pool.map(lambda k: get(kind, k), keys) if r]
