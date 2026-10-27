from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class CurrentUser(BaseModel):
    id: UUID
    email: str


class GenerationRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=160)
    product_description: str = Field(min_length=10, max_length=5000)
    target_audience: str = Field(min_length=2, max_length=240)
    tone: str = Field(default="clear and persuasive", max_length=120)


class GenerationAccepted(BaseModel):
    job_id: UUID
    status: str


class GenerationStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: UUID
    status: str
    error: str | None = None
    slug: str | None = None


class PageSummary(BaseModel):
    id: UUID
    slug: str
    status: str
    created_at: str | None = None


class GenerationResult(BaseModel):
    html: str = Field(min_length=1, max_length=500_000)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=180)
