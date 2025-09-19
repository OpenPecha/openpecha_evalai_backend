from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime
from database import Base

class Template(Base):

    __tablename__ = "template"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    template_name = Column(String, nullable=False)
    username = Column(String, nullable=False)
    template_text = Column(String, nullable=False)
    template_score = Column(Float, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))