from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
import uuid
import datetime
from database import Base

class Template(Base):

    __tablename__ = "template"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_name = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False, index=True)
    template_text = Column(String, nullable=False)
    template_score = Column(Float, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    user = relationship("User", backref="templates")