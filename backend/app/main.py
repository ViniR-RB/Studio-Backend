from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4
import httpx
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import engine, get_session
from app.models import Base, GenerationJob, LandingPage, LandingPageVersion, Product, Session, User
from app.schemas import CurrentUser, GenerationAccepted, GenerationRequest, GenerationResult, GenerationStatus, LoginRequest, PageSummary


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Landing Page Generator", lifespan=lifespan)
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/v1/pages", response_model=list[PageSummary])
async def list_pages(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[PageSummary]:
    rows = await session.execute(select(LandingPage, GenerationJob).join(GenerationJob).order_by(GenerationJob.created_at.desc()))
    return [PageSummary(id=page.id, slug=page.slug, status=job.status, created_at=job.created_at.isoformat() if job.created_at else None) for page, job in rows]


@app.post("/api/v1/generations", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    request: GenerationRequest,
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> GenerationAccepted:
    if idempotency_key:
        existing = await session.scalar(select(GenerationJob).where(GenerationJob.idempotency_key == idempotency_key))
        if existing:
            return GenerationAccepted(job_id=existing.id, status=existing.status)
    product = Product(name=request.product_name, description=request.product_description, audience=request.target_audience, tone=request.tone)
    job = GenerationJob(product=product, idempotency_key=idempotency_key)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": request.model_dump()})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        job.status = "failed"
        job.error_message = "Generation workflow unavailable"
        await session.commit()
        raise HTTPException(status_code=503, detail="Generation workflow unavailable") from exc
    return GenerationAccepted(job_id=job.id, status=job.status)


@app.get("/api/v1/generations/{job_id}", response_model=GenerationStatus)
async def get_generation(job_id: UUID, session: AsyncSession = Depends(get_session)) -> GenerationStatus:
    job = await session.scalar(select(GenerationJob).options(selectinload(GenerationJob.page)).where(GenerationJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    slug = job.page.slug if job.page else None
    return GenerationStatus(job_id=job.id, status=job.status, error=job.error_message, slug=slug)


@app.post("/api/v1/internal/generations/{job_id}/result", dependencies=[Depends(require_internal_token)])
async def save_result(job_id: UUID, result: GenerationResult, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    job = await session.scalar(
        select(GenerationJob).options(selectinload(GenerationJob.page)).where(GenerationJob.id == job_id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    html = result.html
    checksum = hashlib.sha256(html.encode()).hexdigest()
    page = job.page
    if not page:
        page = LandingPage(job=job, slug=result.slug)
        session.add(page)
        await session.flush()
    latest = await session.scalar(select(LandingPageVersion).where(LandingPageVersion.page_id == page.id).order_by(LandingPageVersion.version_number.desc()))
    version = LandingPageVersion(page=page, version_number=(latest.version_number + 1 if latest else 1), html=html, checksum=checksum)
    session.add(version)
    job.status = "succeeded"
    job.error_message = None
    await session.commit()
    return {"status": job.status, "version_id": str(version.id)}


@app.post("/api/v1/internal/generations/{job_id}/publish/{version_id}", dependencies=[Depends(require_internal_token)])
async def publish_result(job_id: UUID, version_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    job = await session.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.page).selectinload(LandingPage.versions))
        .where(GenerationJob.id == job_id)
    )
    version = await session.scalar(select(LandingPageVersion).where(LandingPageVersion.id == version_id))
    if not job or not version or not job.page or version.page_id != job.page.id:
        raise HTTPException(status_code=404, detail="Generation version not found")
    for published in job.page.versions:
        published.published_at = None
    from datetime import datetime, timezone
    version.published_at = datetime.now(timezone.utc)
    job.status = "published"
    await session.commit()
    return {"status": job.status, "slug": job.page.slug}


@app.get("/api/v1/pages/{slug}", response_class=HTMLResponse)
async def get_page(slug: str, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    query = select(LandingPageVersion).join(LandingPage).where(LandingPage.slug == slug, LandingPageVersion.published_at.is_not(None))
    version = await session.scalar(query)
    if not version:
        raise HTTPException(status_code=404, detail="Page not found")
    return HTMLResponse(version.html, headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src https:; base-uri 'none'; frame-ancestors 'self'"})
