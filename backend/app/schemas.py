from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)


class CurrentUser(BaseModel):
    id: UUID
    email: str


class SkillSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    category: str


class SkillCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=2, max_length=1000)
    prompt: str = Field(min_length=2, max_length=5000)
    category: str = Field(default="design", max_length=80)


class DesignSystemSummary(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str
    category: str
    tokens: dict[str, object] = Field(default_factory=dict)


class DesignSystemCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=2, max_length=1000)
    prompt: str = Field(min_length=2, max_length=5000)
    category: str = Field(default="web", max_length=80)


class GenerationRequest(BaseModel):
    product_name: str = Field(min_length=2, max_length=160)
    product_description: str = Field(min_length=10, max_length=5000)
    target_audience: str = Field(min_length=2, max_length=240)
    benefits: str | None = Field(default=None, max_length=5000)
    offer: str | None = Field(default=None, max_length=5000)
    cta: str | None = Field(default=None, max_length=240)
    language: str | None = Field(default=None, max_length=80)
    market: str | None = Field(default=None, max_length=160)
    tone: str = Field(default="clear and persuasive", max_length=120)
    brand_identity: str | None = Field(default=None, max_length=5000)
    visual_direction: str | None = Field(default=None, max_length=3000)
    reference_urls: list[str] = Field(default_factory=list, max_length=5)
    image_urls: list[str] = Field(default_factory=list, max_length=10)
    skill_slugs: list[str] = Field(default_factory=list)
    design_system_slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)

    @field_validator("reference_urls", "image_urls", "skill_slugs", mode="before")
    @classmethod
    def split_lines(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()]
        return value


class GenerationAccepted(BaseModel):
    job_id: UUID
    status: str
    slug: str


class GenerationStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: UUID
    status: str
    error: str | None = None
    slug: str | None = None
    version_id: UUID | None = None


class PageSummary(BaseModel):
    id: UUID
    slug: str
    status: str
    created_at: str | None = None
    published_version_id: UUID | None = None


class GenerationResult(BaseModel):
    html: str = Field(min_length=1, max_length=500_000)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=180)


class GenerationFailure(BaseModel):
    error: str = Field(min_length=1, max_length=5000)


class VersionSummary(BaseModel):
    id: UUID
    version_number: int
    checksum: str
    status: str
    published_at: str | None = None
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    section_id: str | None = Field(default=None, max_length=120)
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = Field(min_length=1, max_length=5000)


class FeedbackResponse(FeedbackRequest):
    id: UUID
    version_id: UUID


class RevisionRequest(BaseModel):
    feedback_ids: list[UUID] = Field(default_factory=list, max_length=50)


class BriefingResponse(BaseModel):
    job_id: UUID
    status: str
    product_name: str
    product_description: str
    target_audience: str
    benefits: str | None = None
    offer: str | None = None
    cta: str | None = None
    language: str | None = None
    market: str | None = None
    tone: str
    brand_identity: str | None = None
    visual_direction: str | None = None
    reference_urls: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    skill_slugs: list[str] = Field(default_factory=list)
    design_system_slug: str | None = None


class BriefingUpdate(BaseModel):
    product_name: str = Field(min_length=2, max_length=160)
    product_description: str = Field(min_length=10, max_length=5000)
    target_audience: str = Field(min_length=2, max_length=240)
    benefits: str | None = Field(default=None, max_length=5000)
    offer: str | None = Field(default=None, max_length=5000)
    cta: str | None = Field(default=None, max_length=240)
    tone: str = Field(default="clear and persuasive", max_length=120)
    visual_direction: str | None = Field(default=None, max_length=3000)
    reference_urls: list[str] | None = Field(default=None, max_length=5)
    image_urls: list[str] | None = Field(default=None, max_length=10)
    skill_slugs: list[str] | None = Field(default=None, max_length=20)
    design_system_slug: str | None = None
