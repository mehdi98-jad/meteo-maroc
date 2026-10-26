import json
import os
import re

import boto3
from botocore.config import Config

BUCKET_NAME = "meteo-raw"


def get_s3_client():
    """Créer un client S3 connecté à SeaweedFS."""

    return boto3.client(
        "s3",
        endpoint_url=os.getenv(
            "S3_ENDPOINT",
            "http://127.0.0.1:8333",
        ),
        aws_access_key_id="local",
        aws_secret_access_key="local",
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket(client):
    """Vérifier que le bucket existe, sinon le créer."""

    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' existe déjà.")

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]

        if error_code in ("404", "NoSuchBucket", "NotFound"):
            client.create_bucket(Bucket=BUCKET_NAME)
            print(f"Bucket '{BUCKET_NAME}' créé.")
        else:
            raise


def save_raw_json(client, city, data, run_date):
    """Sauvegarder le JSON brut dans SeaweedFS."""

    city_slug = city.lower()

    city_slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        city_slug,
    ).strip("-")

    key = f"source=open-meteo/date={run_date}/city={city_slug}/forecast.json"

    body = json.dumps(
        data,
        ensure_ascii=False,
    ).encode("utf-8")

    client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=body,
        ContentType="application/json",
    )

    return key
