from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[User] = relationship(back_populates="sessions")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(240))
    tone: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    jobs: Mapped[list["GenerationJob"]] = relationship(back_populates="product")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    product: Mapped[Product] = relationship(back_populates="jobs")
    page: Mapped["LandingPage | None"] = relationship(back_populates="job", uselist=False)


class LandingPage(Base):
    __tablename__ = "landing_pages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("generation_jobs.id"), unique=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    job: Mapped[GenerationJob] = relationship(back_populates="page")
    versions: Mapped[list["LandingPageVersion"]] = relationship(back_populates="page")


class LandingPageVersion(Base):
    __tablename__ = "landing_page_versions"
    __table_args__ = (UniqueConstraint("page_id", "version_number"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    page_id: Mapped[UUID] = mapped_column(ForeignKey("landing_pages.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    html: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    page: Mapped[LandingPage] = relationship(back_populates="versions")
