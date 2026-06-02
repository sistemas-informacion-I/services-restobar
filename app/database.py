import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load .env from this service
current_dir = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=current_dir.parent / ".env")

# Also try Spring Boot .env for fallback
spring_env = current_dir.parent.parent.parent / "backend-restobar" / ".env"
load_dotenv(dotenv_path=spring_env)

# Build DB URL
db_url = os.getenv("DB_URL", "postgresql://postgres:my_password@localhost:5432/produccion_restobar")

# Handle JDBC prefix if coming from Spring env
if db_url.startswith("jdbc:"):
    db_url = db_url.replace("jdbc:", "", 1)

# Inject credentials if not in URL
if "://" in db_url and "@" not in db_url:
    db_username = os.getenv("DB_USERNAME")
    db_password = os.getenv("DB_PASSWORD")
    if db_username and db_password:
        prefix, rest = db_url.split("://", 1)
        db_url = f"{prefix}://{db_username}:{db_password}@{rest}"

import re

# Normalize postgres:// to postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Normalize Cloud SQL syntax from Spring Boot (cloudSqlInstance) to Python psycopg2 syntax (host=/cloudsql/...)
if "cloudSqlInstance=" in db_url:
    match = re.search(r"cloudSqlInstance=([^&]+)", db_url)
    if match:
        instance = match.group(1)
        db_url = re.sub(r"cloudSqlInstance=[^&]+", f"host=/cloudsql/{instance}", db_url)
    
    # Remove Java specific socketFactory if present
    db_url = re.sub(r"&?socketFactory=[^&]+", "", db_url)
    # Clean up trailing or dangling &
    db_url = db_url.replace("?&", "?").rstrip("&")

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
