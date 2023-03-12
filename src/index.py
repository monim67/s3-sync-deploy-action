import mimetypes
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import boto3

if TYPE_CHECKING:
    from aws_lambda_typing.events import CodePipelineEvent


def handler(event: "CodePipelineEvent", context: Any) -> None:
    codepipeline = boto3.client("codepipeline")
    try:
        return sync_artifact(event, codepipeline)
    except Exception as exc:
        codepipeline.put_job_failure_result(
            jobId=event["CodePipeline.job"]["id"],
            failureDetails={"type": "JobFailed", "message": str(exc)},
        )


def sync_artifact(event: "CodePipelineEvent", codepipeline: Any) -> None:
    job = event["CodePipeline.job"]
    bucket_name = os.getenv("BUCKET_NAME")
    bucket_prefix = (os.getenv("BUCKET_PREFIX", "") + "/").lstrip("/")
    if not bucket_name:
        raise ValueError("Missing env BUCKET_NAME")
    if len(job["data"]["inputArtifacts"]) != 1:
        raise ValueError("Artifact count should be 1")

    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdirpath = Path(tmpdirname)
        with tempfile.NamedTemporaryFile() as tmp_file:
            s3_location = job["data"]["inputArtifacts"][0]["location"]["s3Location"]
            artifactCredentials = job["data"]["artifactCredentials"]
            boto3.client(
                "s3",
                aws_access_key_id=artifactCredentials["accessKeyId"],
                aws_secret_access_key=artifactCredentials["secretAccessKey"],
                aws_session_token=artifactCredentials["sessionToken"],
            ).download_fileobj(
                s3_location["bucketName"], s3_location["objectKey"], tmp_file
            )
            tmp_file.seek(0)
            shutil.unpack_archive(tmp_file.name, tmpdirname, "zip")
        s3 = boto3.client("s3")
        s3_paginator = s3.get_paginator("list_objects_v2")
        for page in s3_paginator.paginate(Bucket=bucket_name, Prefix=bucket_prefix):
            for content in page.get("Contents", ()):
                file_name = content["Key"][len(bucket_prefix) :]
                if not (tmpdirpath / file_name).exists():
                    s3.delete_object(Bucket=bucket_name, Key=content["Key"])
        for file_name in tmpdirpath.glob("**/*"):
            if not file_name.is_dir():
                content_type, _ = mimetypes.guess_type(file_name)
                s3.upload_file(
                    Filename=str(file_name),
                    Bucket=bucket_name,
                    Key=f"{bucket_prefix}{file_name.relative_to(tmpdirpath)}",
                    ExtraArgs={"ContentType": content_type} if content_type else None,
                )

    codepipeline.put_job_success_result(jobId=job["id"])
