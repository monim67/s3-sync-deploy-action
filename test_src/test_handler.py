import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import boto3
import pytest
from aws_lambda_typing.events.code_pipeline import Artifact, ArtifactCredentials
from botocore.exceptions import ClientError
from moto import mock_s3, mock_sts

from index import sync_artifact


class MockCodePipeline:
    def __init__(self) -> None:
        self.put_job_success_result = MagicMock()
        self.put_job_failure_result = MagicMock()


@pytest.fixture
def s3():
    with mock_s3():
        yield boto3.client("s3")


@pytest.fixture
@mock_sts
def artifact_credentials():
    sts = boto3.client("sts")
    default_account = "123456789012"
    response = sts.assume_role(
        RoleArn=f"arn:aws:iam::{default_account}:role/my-role",
        RoleSessionName="test-session-name",
        ExternalId="test-external-id",
    )
    return {
        "accessKeyId": response["Credentials"]["AccessKeyId"],
        "secretAccessKey": response["Credentials"]["SecretAccessKey"],
        "sessionToken": response["Credentials"]["SessionToken"],
    }


def artifacts_factory(s3) -> list[Artifact]:
    s3_location = {
        "bucketName": str(uuid.uuid4()),
        "objectKey": str(uuid.uuid4()),
    }
    s3.create_bucket(Bucket=s3_location["bucketName"])
    with tempfile.TemporaryFile() as tmp:
        with zipfile.ZipFile(tmp, "w") as zip:
            zip.writestr("index.html", "It works!")
            zip.writestr("scripts/main.new.js", "console.log(0)")
            zip.writestr("file", "console.log(0)")
        tmp.seek(0)
        s3.upload_fileobj(
            Fileobj=tmp, Bucket=s3_location["bucketName"], Key=s3_location["objectKey"]
        )
    return [{"location": {"s3Location": s3_location}}]


@dataclass
class BucketConfig:
    bucket_name: str
    keys_to_exist: list[str]
    keys_not_to_exist: list[str]


def destination_bucket_factory(
    s3, monkeypatch: pytest.MonkeyPatch, create_files: bool, prefix: Optional[str]
) -> BucketConfig:
    path_prefix: str = f"{prefix}/" if prefix else ""
    bucket_config = BucketConfig(
        bucket_name=str(uuid.uuid4()),
        keys_to_exist=[f"{path_prefix}index.html", f"{path_prefix}scripts/main.new.js"],
        keys_not_to_exist=[f"{path_prefix}scripts/main.old.js"],
    )
    s3.create_bucket(Bucket=bucket_config.bucket_name)
    if create_files:
        s3.put_object(
            Bucket=bucket_config.bucket_name,
            Key=f"{path_prefix}index.html",
            Body=b"It works!!",
        )
        s3.put_object(
            Bucket=bucket_config.bucket_name,
            Key=f"{path_prefix}scripts/main.old.js",
            Body=b"console.log(1)",
        )
    if prefix:
        s3.put_object(
            Bucket=bucket_config.bucket_name,
            Key="other.html",
            Body=b"It works!!",
        )
        bucket_config.keys_to_exist.append("other.html")

    monkeypatch.setenv("BUCKET_NAME", bucket_config.bucket_name)
    if prefix:
        monkeypatch.setenv("BUCKET_PREFIX", prefix)
    return bucket_config


@pytest.mark.parametrize("create_files", [True, False])
@pytest.mark.parametrize("prefix", [None, "abc"])
def test_abc(
    s3,
    monkeypatch: pytest.MonkeyPatch,
    artifact_credentials: ArtifactCredentials,
    create_files: bool,
    prefix: Optional[str],
):
    codepipeline = MockCodePipeline()
    job_id = str(uuid.uuid4())
    event = {
        "CodePipeline.job": {
            "id": job_id,
            "data": {
                "inputArtifacts": artifacts_factory(s3),
                "artifactCredentials": artifact_credentials,
            },
        }
    }
    destination_bucket_config = destination_bucket_factory(
        s3, monkeypatch, create_files, prefix
    )
    sync_artifact(event, codepipeline)
    codepipeline.put_job_failure_result.assert_not_called()
    codepipeline.put_job_success_result.assert_called_once()
    assert codepipeline.put_job_success_result.call_args.kwargs["jobId"] == job_id
    for key in destination_bucket_config.keys_to_exist:
        s3.head_object(Bucket=destination_bucket_config.bucket_name, Key=key)
    for key in destination_bucket_config.keys_not_to_exist:
        with pytest.raises(ClientError):
            s3.head_object(Bucket=destination_bucket_config.bucket_name, Key=key)
