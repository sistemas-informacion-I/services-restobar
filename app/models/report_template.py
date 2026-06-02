from sqlalchemy import Column, String, Boolean, DateTime, Text, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class ReportTemplateModel(Base):
    __tablename__ = "report_templates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    department = Column(String(150), nullable=True)
    report_type = Column(String(80), nullable=False)
    selected_fields = Column(JSONB, nullable=False)
    filters = Column(JSONB, nullable=False, default=list)
    sort_field = Column(String(80), nullable=True)
    sort_order = Column(String(4), default="asc")
    is_shared = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
