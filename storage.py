import json
import os
import re
import unicodedata

import boto3
from botocore.config import Config

BUCKET_NAME = os.getenv("S3_BUCKET", "meteo-raw")

def city_to_slug(city: str) -> str:
    """Convertir un nom de ville en identifiant ASCII pour S3."""

    normalized = unicodedata.normalize("NFKD", city)

    without_accents = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        without_accents.lower(),
    ).strip("-")

    return slug


def get_s3_client():
    """Créer un client S3 à partir des variables d'environnement."""

    access_key = os.environ["S3_ACCESS_KEY"]
    secret_key = os.environ["S3_SECRET_KEY"]

    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://127.0.0.1:8333"),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.getenv("S3_REGION", "us-east-1"),
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

    city_slug = city_to_slug(city)

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
