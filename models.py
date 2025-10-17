from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, Integer, DateTime

class Base(DeclarativeBase): pass

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    excerpt: Mapped[str] = mapped_column(String(300), default="")
    content_html: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(String(200), default="")   # через запятую
    status: Mapped[str] = mapped_column(String(20), default="published")  # draft/published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
