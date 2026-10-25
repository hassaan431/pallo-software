"""
Pallo SaaS Cloud & Local Storage Adapter
Provides unified media handling for company branding (logos) and assets.
Supports Neon Object Storage (S3-compatible) and Cloudflare R2 with automatic fallback to local filesystem.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Ensure environment variables from .env.local and .env are loaded
load_dotenv(".env.local")
load_dotenv(".env")

logger = logging.getLogger("pallo.storage")

# Optional boto3 import for Neon Object Storage / Cloudflare R2 / S3
try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    Config = None
    ClientError = Exception
    BOTO3_AVAILABLE = False

BASE_DIR = Path(__file__).resolve().parent
LOCAL_LOGOS_DIR = BASE_DIR / "static" / "logos" / "companies"


def is_neon_storage_configured() -> bool:
    """Check if all required Neon Object Storage environment variables are present and boto3 is installed."""
    if not BOTO3_AVAILABLE:
        return False
    required = ["AWS_ENDPOINT_URL_S3", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    return all(bool(os.environ.get(k, "").strip()) for k in required)


def get_neon_bucket_name() -> str:
    """Return the configured Neon Object Storage bucket name, defaulting to 'assets'."""
    return os.environ.get("NEON_STORAGE_BUCKET", "").strip() or os.environ.get("AWS_STORAGE_BUCKET", "").strip() or "assets"


def get_neon_storage_client():
    """
    Build and return an S3 client configured for Neon Object Storage.
    Neon requires path-style addressing and SigV4 authentication.
    """
    if not is_neon_storage_configured():
        return None
    
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3", "").strip()
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.environ.get("AWS_REGION", "us-east-2").strip()
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(s3={"addressing_style": "path"}),
    )


def is_r2_configured() -> bool:
    """Check if all required Cloudflare R2 environment variables are present and boto3 is installed."""
    if not BOTO3_AVAILABLE:
        return False
    
    required = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"]
    return all(bool(os.environ.get(k, "").strip()) for k in required)


def get_r2_client():
    """Build and return an S3 client configured for Cloudflare R2."""
    if not is_r2_configured():
        return None
    
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def get_storage_provider() -> str:
    """Return the name of the active storage provider."""
    if is_neon_storage_configured():
        return "neon-object-storage"
    if is_r2_configured():
        return "cloudflare-r2"
    return "local-filesystem"


def save_company_logo(file_bytes: bytes, filename: str, content_type: str = "image/png") -> str:
    """
    Save a company logo to Neon Object Storage if configured;
    falls back to Cloudflare R2, then local filesystem.
    Returns the URL/path to be stored in companies.logo_url.
    """
    # 1. Neon Object Storage (Primary cloud storage)
    if is_neon_storage_configured():
        try:
            s3 = get_neon_storage_client()
            bucket = get_neon_bucket_name()
            key = f"logos/companies/{filename}"
            
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            
            endpoint = os.environ.get("AWS_ENDPOINT_URL_S3", "").strip().rstrip("/")
            logo_url = f"{endpoint}/{bucket}/{key}"
            logger.info("Successfully uploaded company logo to Neon Object Storage: %s", logo_url)
            return logo_url
        except Exception as e:
            logger.error("Failed to upload to Neon Object Storage, falling back: %s", e)

    # 2. Cloudflare R2 (Secondary cloud storage)
    if is_r2_configured():
        try:
            s3 = get_r2_client()
            bucket = os.environ.get("R2_BUCKET_NAME", "").strip()
            key = f"logos/companies/{filename}"
            
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
            )
            
            public_url = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")
            if public_url:
                logo_url = f"{public_url}/{key}"
            else:
                logo_url = f"https://{bucket}.r2.cloudflarestorage.com/{key}"
            
            logger.info("Successfully uploaded company logo to Cloudflare R2: %s", logo_url)
            return logo_url
        except Exception as e:
            logger.error("Failed to upload to Cloudflare R2, falling back to local disk: %s", e)

    # 3. Local filesystem fallback
    os.makedirs(LOCAL_LOGOS_DIR, exist_ok=True)
    local_path = LOCAL_LOGOS_DIR / filename
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    
    return f"/static/logos/companies/{filename}"


def delete_company_logo(logo_url: Optional[str]) -> bool:
    """
    Delete a company logo from Neon Object Storage, Cloudflare R2, or local filesystem.
    """
    if not logo_url:
        return False
    
    # 1. Neon Object Storage check
    if is_neon_storage_configured():
        endpoint = os.environ.get("AWS_ENDPOINT_URL_S3", "").strip()
        if (endpoint and endpoint in logo_url) or "neon.tech" in logo_url:
            try:
                s3 = get_neon_storage_client()
                bucket = get_neon_bucket_name()
                if "logos/companies/" in logo_url:
                    key = "logos/companies/" + logo_url.split("logos/companies/")[-1]
                    s3.delete_object(Bucket=bucket, Key=key)
                    logger.info("Deleted company logo from Neon Object Storage: %s", key)
                    return True
            except Exception as e:
                logger.error("Error deleting logo from Neon Object Storage: %s", e)

    # 2. Cloudflare R2 check
    if is_r2_configured() and ("r2.cloudflarestorage.com" in logo_url or os.environ.get("R2_PUBLIC_URL", "") in logo_url):
        try:
            s3 = get_r2_client()
            bucket = os.environ.get("R2_BUCKET_NAME", "").strip()
            if "logos/companies/" in logo_url:
                key = "logos/companies/" + logo_url.split("logos/companies/")[-1]
                s3.delete_object(Bucket=bucket, Key=key)
                logger.info("Deleted company logo from Cloudflare R2: %s", key)
                return True
        except Exception as e:
            logger.error("Error deleting logo from R2: %s", e)
    
    # 3. Local filesystem check
    if logo_url.startswith("/static/logos/companies/"):
        filename = logo_url.replace("/static/logos/companies/", "")
        local_path = LOCAL_LOGOS_DIR / filename
        if local_path.exists():
            try:
                local_path.unlink()
                logger.info("Deleted local company logo: %s", local_path)
                return True
            except OSError as e:
                logger.warning("Could not delete local logo file %s: %s", local_path, e)
    
    return False
