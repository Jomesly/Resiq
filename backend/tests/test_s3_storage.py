import io
from datetime import UTC, datetime
from unittest.mock import patch

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.config import Settings
from app.storage import S3BlobStore


def test_s3_roundtrip_pagination_and_deletion_failures():
    client = boto3.client(
        "s3", region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test"
    )
    with patch("boto3.client", return_value=client):
        store = S3BlobStore(Settings(s3_bucket="receipts-test"))
    now = datetime.now(UTC)
    with Stubber(client) as stub:
        stub.add_response(
            "put_object", {}, {"Bucket": "receipts-test", "Key": "w/r/photo", "Body": b"pixels"}
        )
        stub.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(b"pixels"), 6)},
            {"Bucket": "receipts-test", "Key": "w/r/photo"},
        )
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": True,
                "NextContinuationToken": "page2",
                "Contents": [{"Key": "w/r/photo", "LastModified": now}],
            },
            {"Bucket": "receipts-test"},
        )
        stub.add_response(
            "list_objects_v2",
            {"IsTruncated": False, "Contents": [{"Key": "w/r/other", "LastModified": now}]},
            {"Bucket": "receipts-test", "ContinuationToken": "page2"},
        )
        stub.add_response("delete_object", {}, {"Bucket": "receipts-test", "Key": "w/r/other"})
        stub.add_response(
            "list_objects_v2",
            {"Contents": [{"Key": "w/r/photo"}]},
            {"Bucket": "receipts-test", "Prefix": "w/r/"},
        )
        stub.add_response(
            "delete_objects",
            {"Errors": [{"Key": "w/r/photo", "Code": "AccessDenied"}]},
            {"Bucket": "receipts-test", "Delete": {"Objects": [{"Key": "w/r/photo"}]}},
        )
        store.put("w/r/photo", b"pixels")
        assert store.get("w/r/photo") == b"pixels"
        assert [key for key, _ in store.objects()] == ["w/r/photo", "w/r/other"]
        store.delete("w/r/other")
        with pytest.raises(OSError):
            store.delete_prefix("w/r")
        stub.assert_no_pending_responses()
