from database import Base
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import datetime
import uuid


class TextCategory(Base):

    __tablename__ = "text_category"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(String, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(String, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))