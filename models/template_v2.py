from database import Base
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
import datetime
import uuid
from sqlalchemy.orm import relationship

class TemplateV2(Base):

    __tablename__ = "template_v2"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_name = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False)
    template = Column(String)
    hidden = Column(Boolean, nullable=False, default=False)
    challenge_id = Column(String, ForeignKey("arena_challenge.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))