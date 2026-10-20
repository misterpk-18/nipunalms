"""Configuration classes, read from backend/.env."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _derive_test_database_url(url: str | None) -> str | None:
    """nipunalms -> nipunalms_test, unless TEST_DATABASE_URL is set explicitly."""
    if not url:
        return None
    parsed = make_url(url)
    return parsed.set(database=f"{parsed.database}_test").render_as_string(hide_password=False)


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    API_PREFIX = "/api/v1"
    PER_PAGE_DEFAULT = 25
    PER_PAGE_MAX = 100

    # SQL migrations are the source of truth for the schema
    MIGRATIONS_DIR = BASE_DIR.parent / "db"

    # The CRM proves who it is with this key (header X-Service-Key) when it posts events
    CRM_SERVICE_KEY = os.getenv("CRM_SERVICE_KEY")
    # Where the LMS hands WhatsApp messages to the CRM (POST {CRM_BASE_URL}/lms/whatsapp, same service key). Unset = not available.
    CRM_BASE_URL = os.getenv("CRM_BASE_URL")
    CRM_REQUEST_TIMEOUT = float(os.getenv("CRM_REQUEST_TIMEOUT", "10"))
    # The address people open the LMS at (https://lms.example.com): printed, with a QR code, on certificate PDFs so they can be verified. Unset = no QR code.
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

    # Uploaded files (content, submissions, CVs, support attachments). STORAGE_BACKEND=local keeps them under UPLOAD_DIR;
    # s3 keeps them in S3_BUCKET (UPLOAD_DIR is then only the staging folder). Credentials are the AWS_* values in .env.
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    S3_BUCKET = os.getenv("S3_BUCKET")
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Ask Nipuna: without a key the rule-based fallback is used (a later slice)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # Local development and frontend testing run against the staging replica (nipunalms-dev)
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL") or os.getenv("DATABASE_URL")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    S3_BUCKET = os.getenv("S3_BUCKET", "nipunalms-uploads-test")


class TestingConfig(BaseConfig):
    TESTING = True
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"  # fast hashing for tests only
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL") or _derive_test_database_url(os.getenv("DATABASE_URL"))
    LOG_LEVEL = "WARNING"
    CRM_SERVICE_KEY = "test-crm-service-key"
    CRM_BASE_URL = None  # tests never hand WhatsApp to a real CRM; a test that needs it sets it
    UPLOAD_DIR = Path(os.getenv("TEST_UPLOAD_DIR", "/tmp/nipunalms-test-uploads"))
    STORAGE_BACKEND = "local"  # tests never touch AWS; the S3 path is tested with a fake client
    ANTHROPIC_API_KEY = None  # tests never call the real API


class ProductionConfig(BaseConfig):
    DEBUG = False
    S3_BUCKET = os.getenv("S3_BUCKET", "nipunalms-uploads-prod")
