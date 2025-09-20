from database import Base
from sqlalchemy import Column
from token import STRING, DateTime
import datetime

class TemplateV2(Base):

    __tablename__ = "template_v2"

    id = Column(STRING, primary_key=True, unique=True, nullable=False)
    template_name = Column(STRING, nullable=False)
    username = Column(STRING, nullable=False)
    template = Column(STRING)
    text = Column(STRING, nullable=False)
    input_text = Column(STRING)
    from_language = Column(STRING, nullable=False)
    to_language = Column(STRING, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))