from database import Base
from sqlalchemy import Column, String, DateTime
import datetime
import uuid

class TemplateV2(Base):

    __tablename__ = "template_v2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_name = Column(String, nullable=False)
    username = Column(String, nullable=False)
    template = Column(String)
    text = Column(String, nullable=False)
    from_language = Column(String, nullable=False)
    to_language = Column(String, nullable=False)
    challenge_name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))