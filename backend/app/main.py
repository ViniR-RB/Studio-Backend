from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import Cookie, Depends, FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import engine, get_session
from app.models import Base, GenerationJob, GenerationSkill, LandingPage, LandingPageVersion, PageFeedback, Product, Session, User
from app.schemas import (
    BriefingResponse,
    SkillCreate,
    SkillSummary,
    CurrentUser,
    FeedbackRequest,
    FeedbackResponse,
    GenerationAccepted,
    GenerationRequest,
    BriefingUpdate,
    GenerationFailure,
    GenerationResult,
    GenerationStatus,
    LoginRequest,
    PageSummary,
    RevisionRequest,
    VersionSummary,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for statement in (
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS benefits TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS offer TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS cta VARCHAR(240)",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS language VARCHAR(80)",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS market VARCHAR(160)",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS brand_identity TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS visual_direction TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS reference_urls TEXT",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_urls TEXT",
            "ALTER TABLE generation_jobs ALTER COLUMN status TYPE VARCHAR(32)",
            "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS skill_prompts TEXT",
            "ALTER TABLE landing_page_versions ADD COLUMN IF NOT EXISTS validation_errors TEXT",
            "ALTER TABLE landing_page_versions ADD COLUMN IF NOT EXISTS validation_warnings TEXT",
        ):
            await connection.execute(text(statement))
        await connection.run_sync(Base.metadata.create_all)
        async with AsyncSession(bind=connection, expire_on_commit=False) as migration_session:
            orphan_jobs = await migration_session.scalars(select(GenerationJob).options(selectinload(GenerationJob.page), selectinload(GenerationJob.product)).where(GenerationJob.page == None))
            for orphan in orphan_jobs:
                base_slug = re.sub(r"[^a-z0-9]+", "-", orphan.product.name.lower()).strip("-")
                slug = base_slug or f"page-{orphan.id.hex[:8]}"
                suffix = 2
                while await migration_session.scalar(select(LandingPage.id).where(LandingPage.slug == slug)):
                    slug = f"{base_slug}-{suffix}"
                    suffix += 1
                migration_session.add(LandingPage(job_id=orphan.id, slug=slug))
            await migration_session.commit()
        skills = (
            ("conversion-focused", "Conversão direta", "Hero e CTA orientados a conversão.", "Priorize proposta de valor clara, prova e CTA direto."),
            ("premium-editorial", "Premium editorial", "Layout sofisticado e editorial.", "Use hierarquia tipográfica elegante, espaço generoso e aparência premium."),
            ("mobile-first", "Mobile first", "Experiência otimizada para telas pequenas.", "Priorize leitura e CTA em mobile, com blocos curtos e controles grandes."),
        )
        for slug, name, description, prompt in skills:
            existing = await connection.scalar(select(GenerationSkill).where(GenerationSkill.slug == slug))
            if not existing:
                await connection.execute(GenerationSkill.__table__.insert().values(slug=slug, name=name, description=description, prompt=prompt, category="design"))
    yield
    await engine.dispose()


app = FastAPI(title="Landing Page Generator", lifespan=lifespan)
UPLOAD_DIR = Path("uploads")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-XSRF-TOKEN", "Idempotency-Key"],
)


def _hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), settings.internal_api_token.encode(), 240_000).hex()


def _valid_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(_hash_password(password), password_hash)


def _validation(html: str) -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    lowered = html.lower()
    if "<html" not in lowered or "</html>" not in lowered:
        errors.append("HTML must contain an html element")
    if "<body" not in lowered or "</body>" not in lowered:
        errors.append("HTML must contain a body element")
    if "<title" not in lowered:
        warnings.append("HTML is missing a title")
    if "<style" not in lowered and "stylesheet" not in lowered:
        warnings.append("HTML has no stylesheet; visual styling may be incomplete")
    if "<a " not in lowered and "<button" not in lowered:
        warnings.append("HTML has no call to action")
    if "{{" in html or "}}" in html:
        errors.append("HTML contains unresolved placeholders")
    return errors, warnings


def _json_list(value: str | None) -> list[str]:
    return json.loads(value) if value else []


async def current_user(
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    auth_session = await session.scalar(select(Session).options(selectinload(Session.user)).where(Session.id == session_id))
    if not auth_session or auth_session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return auth_session.user


@app.post("/api/v1/auth/login", response_model=CurrentUser)
async def login(request: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)) -> CurrentUser:
    user = await session.scalar(select(User).where(User.email == request.email.lower()))
    if not user or not _valid_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    session_id = secrets.token_urlsafe(48)
    session.add(Session(id=session_id, user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_ttl_seconds)))
    await session.commit()
    response.set_cookie(settings.session_cookie_name, session_id, max_age=settings.session_ttl_seconds, httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite)
    return CurrentUser(id=user.id, email=user.email)


@app.get("/api/v1/auth/me", response_model=CurrentUser)
async def me(user: User = Depends(current_user)) -> CurrentUser:
    return CurrentUser(id=user.id, email=user.email)


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name), session: AsyncSession = Depends(get_session)) -> None:
    if session_id:
        auth_session = await session.get(Session, session_id)
        if auth_session:
            await session.delete(auth_session)
            await session.commit()
    response.delete_cookie(settings.session_cookie_name, httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite)


async def require_internal_token(authorization: str | None = Header(default=None)) -> None:
    if authorization != f"Bearer {settings.internal_api_token}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.post("/api/v1/assets/images", status_code=status.HTTP_201_CREATED)
async def upload_image(file: UploadFile = File(...), user: User = Depends(current_user)) -> dict[str, str]:
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(status_code=415, detail="Only PNG, JPEG or WebP images are supported")
    content = await file.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller")
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[file.content_type]
    UPLOAD_DIR.mkdir(exist_ok=True)
    target = UPLOAD_DIR / f"{uuid4().hex}{extension}"
    target.write_bytes(content)
    path = f"/api/v1/assets/images/{target.name}"
    return {"url": path, "public_url": path, "internal_url": f"http://api:8000{path}", "content_type": file.content_type}


@app.get("/api/v1/assets/images/{filename}")
async def get_image(filename: str) -> Response:
    target = UPLOAD_DIR / Path(filename).name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(target.read_bytes(), media_type={".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(target.suffix, "application/octet-stream"))


@app.get("/api/v1/skills", response_model=list[SkillSummary])
async def list_skills(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[SkillSummary]:
    skills = await session.scalars(select(GenerationSkill).order_by(GenerationSkill.category, GenerationSkill.name))
    return [SkillSummary(id=item.id, slug=item.slug, name=item.name, description=item.description, category=item.category) for item in skills]


@app.post("/api/v1/skills", response_model=SkillSummary, status_code=status.HTTP_201_CREATED)
async def create_skill(request: SkillCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> SkillSummary:
    if await session.scalar(select(GenerationSkill).where(GenerationSkill.slug == request.slug)):
        raise HTTPException(status_code=409, detail="Skill slug already exists")
    skill = GenerationSkill(**request.model_dump())
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    return SkillSummary(id=skill.id, slug=skill.slug, name=skill.name, description=skill.description, category=skill.category)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/v1/pages", response_model=list[PageSummary])
async def list_pages(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[PageSummary]:
    rows = await session.execute(
        select(LandingPage, GenerationJob)
        .join(GenerationJob)
        .options(selectinload(LandingPage.versions))
        .where(
            or_(
                exists(select(LandingPageVersion.id).where(LandingPageVersion.page_id == LandingPage.id)),
                GenerationJob.status == "generating",
            )
        )
        .order_by(GenerationJob.created_at.desc())
    )
    return [PageSummary(id=page.id, slug=page.slug, status="published" if any(version.published_at for version in page.versions) else job.status, created_at=job.created_at.isoformat() if job.created_at else None, published_version_id=next((version.id for version in page.versions if version.published_at), None)) for page, job in rows]


@app.post("/api/v1/generations", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    request: GenerationRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> GenerationAccepted:
    if idempotency_key:
        existing = await session.scalar(select(GenerationJob).where(GenerationJob.idempotency_key == idempotency_key))
        if existing:
            return GenerationAccepted(job_id=existing.id, status=existing.status, slug="")
    slug = re.sub(r"[^a-z0-9]+", "-", request.product_name.lower()).strip("-")
    product = Product(name=request.product_name, description=request.product_description, audience=request.target_audience, tone=request.tone, benefits=request.benefits, offer=request.offer, cta=request.cta, language=request.language, market=request.market, brand_identity=request.brand_identity, visual_direction=request.visual_direction, reference_urls=json.dumps(request.reference_urls), image_urls=json.dumps(request.image_urls))
    skills = await session.scalars(select(GenerationSkill).where(GenerationSkill.slug.in_(request.skill_slugs)))
    skill_prompts = [skill.prompt for skill in skills]
    job = GenerationJob(product=product, idempotency_key=idempotency_key, status="queued", skill_prompts=json.dumps(skill_prompts))
    page = LandingPage(job=job, slug=slug)
    session.add(job)
    session.add(page)
    await session.commit()
    await session.refresh(job)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": request.model_dump(), "skills": skill_prompts})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        job.status = "failed"
        job.error_message = "Generation workflow unavailable"
        await session.commit()
        raise HTTPException(status_code=503, detail="Generation workflow unavailable") from exc
    job.status = "generating"
    await session.commit()
    return GenerationAccepted(job_id=job.id, status=job.status, slug=slug)


@app.get("/api/v1/generations/{job_id}", response_model=GenerationStatus)
async def get_generation(job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> GenerationStatus:
    job = await session.scalar(select(GenerationJob).options(selectinload(GenerationJob.page).selectinload(LandingPage.versions)).where(GenerationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    slug = job.page.slug if job.page else None
    version_id = job.page.versions[-1].id if job.page and job.page.versions else None
    return GenerationStatus(job_id=job.id, status=job.status, error=job.error_message, slug=slug, version_id=version_id)


@app.post("/api/v1/internal/generations/{job_id}/result", dependencies=[Depends(require_internal_token)])
async def save_result(job_id: UUID, result: GenerationResult, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    job = await session.scalar(select(GenerationJob).options(selectinload(GenerationJob.page)).where(GenerationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    errors, warnings = _validation(result.html)
    page = job.page or await session.scalar(select(LandingPage).where(LandingPage.slug == result.slug))
    if not page:
        page = LandingPage(job=job, slug=result.slug)
        session.add(page)
        await session.flush()
    latest = await session.scalar(select(LandingPageVersion).where(LandingPageVersion.page_id == page.id).order_by(LandingPageVersion.version_number.desc()))
    version = LandingPageVersion(page=page, version_number=(latest.version_number + 1 if latest else 1), html=result.html, checksum=hashlib.sha256(result.html.encode()).hexdigest(), validation_errors=json.dumps(errors), validation_warnings=json.dumps(warnings))
    session.add(version)
    job.status = "draft" if not errors else "failed"
    job.error_message = "; ".join(errors) if errors else None
    await session.commit()
    return {"status": job.status, "version_id": str(version.id)}


@app.post("/api/v1/internal/generations/{job_id}/failure", dependencies=[Depends(require_internal_token)])
async def save_generation_failure(job_id: UUID, failure: GenerationFailure, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    job = await session.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "failed"
    job.error_message = failure.error
    await session.commit()
    return {"status": job.status, "job_id": str(job.id)}


@app.get("/api/v1/pages/{slug}/briefing", response_model=BriefingResponse)
async def get_briefing(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> BriefingResponse:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    product = page.job.product
    skill_slugs = []
    return BriefingResponse(job_id=page.job.id, status=page.job.status, product_name=product.name, product_description=product.description, target_audience=product.audience, benefits=product.benefits, offer=product.offer, cta=product.cta, language=product.language, market=product.market, tone=product.tone, brand_identity=product.brand_identity, visual_direction=product.visual_direction, reference_urls=_json_list(product.reference_urls), image_urls=_json_list(product.image_urls), skill_slugs=skill_slugs)


@app.put("/api/v1/pages/{slug}/briefing", response_model=BriefingResponse)
async def update_briefing(slug: str, request: BriefingUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> BriefingResponse:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    product = page.job.product
    for field in ("product_name", "product_description", "target_audience", "benefits", "offer", "cta", "tone", "visual_direction"):
        setattr(product, {"product_name": "name", "product_description": "description", "target_audience": "audience"}.get(field, field), getattr(request, field))
    product.reference_urls = json.dumps(request.reference_urls)
    product.image_urls = json.dumps(request.image_urls)
    skills = await session.scalars(select(GenerationSkill).where(GenerationSkill.slug.in_(request.skill_slugs)))
    page.job.skill_prompts = json.dumps([skill.prompt for skill in skills])
    await session.commit()
    return await get_briefing(slug, user, session)


async def _get_page(slug: str, session: AsyncSession) -> LandingPage:
    page = await session.scalar(select(LandingPage).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


async def _get_version(slug: str, version_id: UUID, session: AsyncSession) -> LandingPageVersion:
    page = await _get_page(slug, session)
    version = await session.scalar(select(LandingPageVersion).where(LandingPageVersion.id == version_id, LandingPageVersion.page_id == page.id))
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@app.get("/api/v1/pages/{slug}/versions", response_model=list[VersionSummary])
async def list_versions(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[VersionSummary]:
    page = await _get_page(slug, session)
    versions = await session.scalars(select(LandingPageVersion).where(LandingPageVersion.page_id == page.id).order_by(LandingPageVersion.version_number))
    return [VersionSummary(id=version.id, version_number=version.version_number, checksum=version.checksum, status="published" if version.published_at else "draft", published_at=version.published_at.isoformat() if version.published_at else None, validation_errors=_json_list(version.validation_errors), validation_warnings=_json_list(version.validation_warnings)) for version in versions]


@app.get("/api/v1/pages/{slug}/versions/{version_id}/preview", response_class=HTMLResponse)
async def preview_version(slug: str, version_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    version = await _get_version(slug, version_id, session)
    return HTMLResponse(version.html, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src https:; base-uri 'none'; frame-ancestors 'self'"})


@app.get("/api/v1/pages/{slug}/versions/{version_id}/feedback", response_model=list[FeedbackResponse])
async def list_feedback(slug: str, version_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[FeedbackResponse]:
    version = await _get_version(slug, version_id, session)
    feedback = await session.scalars(select(PageFeedback).where(PageFeedback.version_id == version.id).order_by(PageFeedback.created_at.desc()))
    return [FeedbackResponse(id=item.id, version_id=item.version_id, section_id=item.section_id, rating=item.rating, comment=item.comment) for item in feedback]


@app.post("/api/v1/pages/{slug}/versions/{version_id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def add_feedback(slug: str, version_id: UUID, request: FeedbackRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> FeedbackResponse:
    version = await _get_version(slug, version_id, session)
    feedback = PageFeedback(version_id=version.id, section_id=request.section_id, rating=request.rating, comment=request.comment)
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return FeedbackResponse(id=feedback.id, version_id=feedback.version_id, section_id=feedback.section_id, rating=feedback.rating, comment=feedback.comment)


@app.post("/api/v1/pages/{slug}/retry", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def retry_generation(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> GenerationAccepted:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page or not page.job:
        raise HTTPException(status_code=404, detail="Page generation not found")
    job = page.job
    product = job.product
    skills = _json_list(job.skill_prompts)
    job.status = "queued"
    job.error_message = None
    await session.commit()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": {"product_name": product.name, "product_description": product.description, "target_audience": product.audience, "tone": product.tone, "benefits": product.benefits, "offer": product.offer, "cta": product.cta, "language": product.language, "market": product.market, "brand_identity": product.brand_identity, "visual_direction": product.visual_direction, "reference_urls": _json_list(product.reference_urls), "image_urls": _json_list(product.image_urls)}, "skills": skills})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        job.status = "failed"
        job.error_message = "Generation workflow unavailable"
        await session.commit()
        raise HTTPException(status_code=503, detail="Generation workflow unavailable") from exc
    job.status = "generating"
    await session.commit()
    return GenerationAccepted(job_id=job.id, status=job.status, slug=page.slug)


@app.post("/api/v1/pages/{slug}/versions/{version_id}/revise", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def revise_version(slug: str, version_id: UUID, request: RevisionRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> GenerationAccepted:
    version = await _get_version(slug, version_id, session)
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.id == version.page_id))
    feedback_query = select(PageFeedback).where(PageFeedback.version_id == version.id)
    if request.feedback_ids:
        feedback_query = feedback_query.where(PageFeedback.id.in_(request.feedback_ids))
    feedback = await session.scalars(feedback_query)
    feedback_items = [
        {"section": item.section_id, "rating": item.rating, "comment": item.comment}
        for item in feedback
    ]
    product = page.job.product
    skills = _json_list(page.job.skill_prompts)
    job = GenerationJob(product_id=product.id, status="queued", skill_prompts=json.dumps(skills))
    session.add(job)
    await session.commit()
    await session.refresh(job)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": {"product_name": product.name, "product_description": product.description, "target_audience": product.audience, "tone": product.tone, "benefits": product.benefits, "offer": product.offer, "cta": product.cta, "language": product.language, "market": product.market, "brand_identity": product.brand_identity, "visual_direction": product.visual_direction, "reference_urls": _json_list(product.reference_urls), "image_urls": _json_list(product.image_urls)}, "feedback": feedback_items, "skills": skills})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        job.status = "failed"
        job.error_message = "Generation workflow unavailable"
        await session.commit()
        raise HTTPException(status_code=503, detail="Generation workflow unavailable") from exc
    return GenerationAccepted(job_id=job.id, status=job.status, slug=slug)


@app.post("/api/v1/pages/{slug}/versions/{version_id}/publish")
async def publish_version(slug: str, version_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    page = await _get_page(slug, session)
    version = await session.scalar(select(LandingPageVersion).where(LandingPageVersion.id == version_id, LandingPageVersion.page_id == page.id))
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    errors = _json_list(version.validation_errors)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Version failed validation", "errors": errors})
    versions = await session.scalars(select(LandingPageVersion).where(LandingPageVersion.page_id == page.id))
    for published in versions:
        published.published_at = None
    version.published_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "published", "slug": page.slug, "version_id": str(version.id)}


@app.post("/api/v1/pages/{slug}/unpublish")
async def unpublish_page(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    page = await _get_page(slug, session)
    versions = await session.scalars(select(LandingPageVersion).where(LandingPageVersion.page_id == page.id, LandingPageVersion.published_at.is_not(None)))
    for version in versions:
        version.published_at = None
    await session.commit()
    return {"status": "unpublished", "slug": page.slug}


@app.post("/api/v1/internal/generations/{job_id}/publish/{version_id}", dependencies=[Depends(require_internal_token)])
async def publish_result(job_id: UUID, version_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    raise HTTPException(status_code=410, detail="Internal publication is disabled; use the authenticated page publication endpoint")


@app.get("/api/v1/pages/{slug}", response_class=HTMLResponse)
async def get_page(slug: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    query = select(LandingPageVersion).join(LandingPage).where(LandingPage.slug == slug, LandingPageVersion.published_at.is_not(None))
    version = await session.scalar(query)
    if not version:
        raise HTTPException(status_code=404, detail="Page not found")
    return HTMLResponse(version.html, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src https:; base-uri 'none'; frame-ancestors 'self'"})
