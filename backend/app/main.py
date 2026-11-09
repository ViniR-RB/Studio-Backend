from contextlib import asynccontextmanager
import os
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import re
import secrets
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import Cookie, Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import exists, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import engine, get_session
from app.models import Asset, Base, DesignSystem, GenerationJob, GenerationSkill, LandingPage, LandingPageVersion, PageFeedback, Product, Session, User
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
    DesignSystemCreate,
    DesignSystemSummary,
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
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS design_system_slug VARCHAR(120)",
            "ALTER TABLE design_systems ADD COLUMN IF NOT EXISTS tokens TEXT NOT NULL DEFAULT '{}'",
            "ALTER TABLE generation_jobs ALTER COLUMN status TYPE VARCHAR(32)",
            "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS skill_prompts TEXT",
            "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS skill_slugs TEXT",
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
            ("conversion-focused", "Conversão direta", "Hero e CTA orientados a conversão.", "Defina um único objetivo de conversão. Crie uma promessa clara acima da dobra, com benefício específico, demonstração do produto e CTA direto. Remova distrações e use microcopy para reduzir fricção. Não invente avaliações, números, escassez, garantias ou resultados."),
            ("mobile-first", "Mobile first", "Experiência otimizada para telas pequenas.", "Priorize leitura e CTA em mobile, com blocos curtos, controles grandes, contraste adequado e carregamento rápido. Evite layouts que exijam zoom ou rolagem horizontal."),
            ("premium-editorial", "Premium editorial", "Layout sofisticado e editorial.", "Use hierarquia tipográfica elegante, espaço generoso, composição visual consistente e aparência premium sem sacrificar clareza, acessibilidade ou velocidade."),
            ("accessibility-first", "Acessibilidade primeiro", "Estrutura inclusiva e utilizável por teclado e leitores de tela.", "Use HTML semântico, headings em ordem, labels claros, foco visível, alt text descritivo, contraste suficiente, alvos de toque confortáveis e movimento reduzido quando solicitado. Não comunique informação apenas por cor."),
            ("seo-performance", "SEO e performance", "Landing page rápida, indexável e tecnicamente organizada.", "Inclua title e meta description coerentes, um único H1, headings descritivos, URLs e links compreensíveis, imagens responsivas com dimensões definidas, lazy loading abaixo da dobra e CSS enxuto. Não faça keyword stuffing nem prometa métricas não medidas."),
            ("trust-proof", "Confiança verificável", "Evidências de confiança para páginas de vendas sem alegações inventadas.", "Construa confiança com evidências verificáveis: identidade do produto, especificações, compatibilidade, conteúdo da embalagem, política de troca, devolução, garantia, entrega, suporte e avaliações somente quando fornecidos por fonte confiável. Diferencie fato, benefício, opinião e informação pendente; associe cada claim à evidência disponível. Nunca fabrique depoimentos, selos, contagens, certificações, notas, antes/depois, autoridade, urgência ou segurança clínica. Se preço, entrega ou política não forem conhecidos, diga que precisam ser confirmados antes da compra."),
            ("prototype-social-proof", "Prova social de protótipo", "Cria uma simulação visual de prova social para testes, sempre identificada como fictícia e não publicada como evidência real.", "Para protótipos e testes internos, você pode criar um bloco visual de prova social com avatares genéricos ou imagens de banco/licenciadas, estrelas e uma contagem ilustrativa de avaliações. Isso é mockup, não prova real: rotule de forma visível como 'Demonstração', 'Dados fictícios' ou 'Exemplo de interface'; não use nomes reais, rostos apresentados como clientes, depoimentos atribuídos, avaliações supostamente verificadas, números que pareçam dados da loja, selos, logos ou resultados inventados. Não extraia rostos ou avaliações de terceiros para sugerir que compraram o produto. Prefira avatares abstratos ou stock com licença compatível e mantenha o bloco isolado do CTA. Antes de qualquer publicação, substitua todo o mockup por dados fornecidos por uma fonte verificável ou remova-o. Se o pedido não for explicitamente um protótipo, não gere esse bloco e sinalize a ausência de prova social."),
            ("product-page-landing", "Página de produto e landing page", "Estrutura páginas de produto e landing pages de e-commerce com dados verificáveis.", "Trate o briefing como contrato de conteúdo: preserve idioma, tom, identidade, imagens, links, preços, medidas, condições, benefícios e todos os números fornecidos; nunca invente claims, avaliações, escassez, estoque, garantia, descontos ou especificações. Gere um único index.html autocontido, com HTML semântico, title e meta description, um único H1 e esta ordem mínima quando houver conteúdo suficiente: header/navegação, hero com promessa e CTA principal, destaques ou métricas, benefícios, galeria/demonstração, especificações ou detalhes de uso, oferta, FAQ acessível com details/summary e respostas baseadas apenas no briefing, CTA final e rodapé. Não omita FAQ quando o briefing fornecer dúvidas, especificações ou condições que possam ser respondidas; se não houver fatos suficientes, não fabrique respostas e sinalize a lacuna. Todo número do briefing deve aparecer como texto visível no HTML inicial, com contraste suficiente, sem depender de JavaScript, sem opacity:0 permanente e sem ficar escondido por overflow, transform ou animação. Use apenas assets autorizados, normalize URLs multilinha, preserve alt text descritivo e valide que os seletores e imagens usados existem. Não habilite checkout, pagamento, captura de dados, analytics ou integrações por inferência. Priorize mobile, performance, teclado, foco, contraste e uso sem JavaScript; revise desktop e celular e sinalize qualquer dado ausente ou pendência concreta."),
            ("logo-svg-brand", "Logo em SVG", "Cria uma identidade visual de produto em SVG inline, reutilizável e acessível.", "Crie uma logo original para o produto quando não houver marca fornecida. Entregue o símbolo e o nome em SVG inline, sem imagens externas, fontes remotas, base64, filtros pesados ou dependências de JavaScript. Use viewBox explícito, proporções preservadas, paths simples, poucas cores e versões para fundo claro e escuro quando necessário. O SVG deve ser responsivo, legível em tamanhos pequeno e grande, ter role=img, aria-labelledby e title/desc acessíveis, e funcionar como link quando estiver no header. Separe símbolo e wordmark em grupos identificáveis, mantenha contraste suficiente e não use o nome, símbolo, tipografia ou trade dress de uma marca real sem autorização; se o briefing mencionar uma marca existente, preserve somente a identidade fornecida e não fabrique um redesign oficial. Não transforme a logo em texto invisível, não dependa de fontes instaladas e não aplique animação que prejudique reconhecimento. Se a logo precisar de motion, anime apenas traços ou uma entrada curta e mantenha o estado estático utilizável. Inclua uma alternativa textual e verifique que o SVG não contém scripts, eventos inline, URLs externas ou markup inválido."),
            ("anti-ai-slop-editorial", "Direção anti-AI slop", "Remove aparência genérica de template e cria uma direção editorial específica para cada produto.", "Trate a landing page como uma peça de direção de arte, não como um conjunto automático de blocos. Defina uma ideia visual central específica para o produto e uma assinatura reconhecível de composição, tipografia, cor, imagem e movimento. Evite o padrão intercambiável hero + três cards + métricas + galeria + CTA quando não houver motivo; remova seções redundantes e componentes decorativos sem função. Use copy concreta, curta e verificável: elimine adjetivos vazios e frases genéricas como revolucionário, experiência única, eleve sua rotina ou feito para você quando não acrescentarem informação. Não invente claims, reviews, números, autoridade, urgência, garantia ou prova social. Dê a cada imagem uma função narrativa, não repita a mesma imagem sem necessidade e preserve foco, crop, proporção e contexto. Crie hierarquia tipográfica deliberada, contraste de escala, ritmo de densidade e assimetria controlada; não use automaticamente gradientes, glassmorphism, glow, sombras, pills, ícones ou cards arredondados. Use uma única ação principal e reduza distrações. Motion deve reforçar narrativa, produto e profundidade: prefira uma linguagem consistente, entradas sequenciais pontuais, parallax suave e transições com propósito; não anime todos os elementos nem use bounce, blur ou efeitos chamativos sem função. Faça uma revisão anti-slop antes de concluir: pergunte se a página poderia pertencer a qualquer outro produto, qual elemento a torna específica, qual bloco pode ser removido e se a página continua clara sem JavaScript. Preserve acessibilidade, leitura, foco, teclado, mobile, performance e estado estático utilizável."),
            ("sales-page-structure", "Página de vendas", "Estrutura uma página de vendas clara, verificável e orientada à decisão sem inventar provas ou ofertas.", "Estruture a página como uma sequência de decisão, não como um catálogo de blocos. No primeiro viewport, mostre produto, promessa específica baseada no briefing, benefício principal, imagem relevante e uma única ação principal. Em seguida, reduza incerteza na ordem necessária: demonstre o produto em uso, explique benefícios ligados a características verificáveis, apresente especificações, compatibilidade, variantes e o que está incluído, informe preço e condições somente quando fornecidos, e deixe claros entrega, troca, devolução, garantia e suporte somente quando confirmados. Use prova social, avaliações, selos e comparativos apenas quando existirem fontes. Em protótipos explicitamente marcados como teste, pode incluir um mockup de prova social com avatares licenciados ou abstratos, estrelas e contagem ilustrativa, sempre rotulado de forma visível como demonstração/dados fictícios; nunca apresente isso como cliente real, avaliação verificada ou evidência da loja. Nunca invente autoridade, contagens ou resultados para publicação. Inclua FAQ para objeções reais sobre uso, compatibilidade, manutenção, entrega e compra, respondendo somente com fatos disponíveis; marque lacunas em vez de preencher com suposições. Repita o CTA em pontos de decisão sem criar CTAs concorrentes, mantendo rótulos consistentes e destino real. Dê ao usuário controle antes da ação: variantes, quantidade, imagens, detalhes essenciais, preço total conhecido e próximos passos devem estar claros. Diferencie descoberta, consideração e compra; não apresente checkout, pagamento ou captura de dados se a integração não existir. Use headings semânticos, leitura escaneável, contraste, foco, teclado, alt text, estados de erro e layout mobile. Para cada seção, defina objetivo, evidência e ação; remova qualquer seção que não reduza dúvida nem ajude a decidir. Antes de publicar, verifique que o conteúdo essencial está no HTML inicial, que números e condições não dependem de JavaScript, que imagens e links carregam e que a página continua compreensível sem motion."),
            ("sales-copy-framework", "Copy de vendas", "Escreve mensagens de venda específicas, claras e verificáveis para cada etapa da decisão.", "Escreva a copy como argumento de compra, não como slogan genérico. Organize promessa, problema ou contexto de uso, mecanismo ou característica confirmada, benefício concreto, evidência disponível, objeção e próximo passo. Use linguagem específica do produto e do público; prefira verbos e fatos a adjetivos. Diferencie característica, benefício, prova e condição comercial. Não invente dor, transformação, depoimento, comparação, resultado, urgência, preço, garantia ou autoridade. Quando faltar evidência, use uma formulação neutra e marque a informação como pendente. Mantenha uma promessa principal, subtítulos escaneáveis, CTA consistente e microcopy que explique o que acontece depois do clique. Corte repetições e frases que poderiam vender qualquer outro produto. Preserve idioma, tom, acessibilidade e clareza legal."),
            ("sales-objection-handling", "Objeções de compra", "Resolve dúvidas reais antes da compra sem pressão enganosa ou informações inventadas.", "Mapeie as objeções que o briefing e o produto permitem responder: serve para quem, como usar, o que acompanha, compatibilidade, variantes, tamanho ou volume, manutenção, segurança, entrega, troca, devolução, garantia, suporte e preço. Crie uma seção ou bloco somente quando houver resposta factual. Use FAQ acessível com details/summary ou estrutura equivalente; mantenha perguntas curtas e respostas diretas. Não invente políticas, prazos, avaliações, certificações, resultados, contraindicações ou garantias. Se a resposta não existir, diga que precisa ser confirmada e direcione para uma fonte real. Não esconda limitações, não use contadores, pop-ups agressivos ou urgência artificial. Depois de cada objeção resolvida, mantenha um único próximo passo coerente com a oferta."),
            ("sales-offer-clarity", "Oferta clara", "Apresenta oferta, preço e próximo passo com transparência e sem dark patterns.", "Apresente somente condições comerciais fornecidas e verificáveis: produto, variante, quantidade, preço, desconto, parcelamento, frete, prazo, estoque, garantia, troca, devolução e destino do CTA. Diferencie preço conhecido de informação pendente; nunca complete lacunas com valores ou promessas. Mostre o que está incluído e o que não está quando houver dados. Use rótulos consistentes, contraste suficiente e uma ação principal. Não use preço riscado falso, desconto inventado, escassez, urgência, renovação automática, captura de dados ou checkout se a integração não existir. A oferta deve permanecer compreensível no HTML inicial, no mobile, sem JavaScript e sem animação."),
            ("product-page-audit", "Auditoria de página de produto", "Revisa a página gerada contra critérios de compra, confiança, mobile e acessibilidade.", "Audite a página como uma página de produto orientada à compra, não como uma landing page genérica. Verifique, usando somente o HTML/CSS/briefing disponível: produto e benefício principal visíveis no primeiro viewport; buy box, preço, variantes, quantidade e CTA consistentes; imagens com função demonstrativa e alt text; especificações, compatibilidade e conteúdo da embalagem; frete, prazo, troca, devolução, garantia e suporte quando confirmados; FAQ para objeções reais; prova social e selos somente quando há fonte; experiência mobile, sticky CTA sem cobrir conteúdo, teclado, foco, contraste, headings, performance e uso sem JavaScript. Entregue no máximo 12 achados priorizados, cada um com evidência concreta, impacto na decisão, severidade, esforço e correção específica. Separe falhas observáveis de verificações manuais. Nunca invente dados, claims, avaliações, políticas, métricas ou recomendações de checkout; se algo não puder ser confirmado, marque como pendência."),
            ("gsap-scrolltrigger-fluid", "GSAP Scroll fluido", "Animações de landing pages com GSAP e ScrollTrigger, responsivas, performáticas e acessíveis.", "Implemente motion perceptível, elegante e funcional com GSAP 3 e ScrollTrigger. Carregue gsap e ScrollTrigger da mesma versão, registre uma vez com gsap.registerPlugin(ScrollTrigger) e confirme que ambos estão disponíveis antes de animar. Entregue pelo menos três comportamentos quando houver elementos correspondentes: entrada sequencial do hero, entrada escalonada de benefícios/cards, e parallax suave do produto ou mídia; adicione uma transição de oferta/FAQ sem impedir details/summary, foco, teclado ou leitura. Cada trigger deve apontar para um elemento existente; não esconda conteúdo essencial permanentemente: elementos devem ter estado inicial utilizável e animações devem terminar em estado visível. Use gsap.matchMedia() para desktop/mobile, invalidateOnRefresh:true para dimensões, ScrollTrigger.refresh() depois de imagens/fontes carregarem e ctx.revert() ou mm.revert() ao desmontar. Use scrub somente quando a relação com rolagem for clara, pin com parcimônia e nunca use markers na entrega. Mantenha as animações ativas independentemente de prefers-reduced-motion, sem return ou condição que interrompa a criação dos triggers. Não dependa de JavaScript para conteúdo essencial, não anime layout sem necessidade, preserve foco/teclado e use will-change somente durante a animação. Use URLs de CDN permitidas pela página, mantenha scripts inline sintaticamente válidos, sem marcadores de diff, e verifique desktop e mobile."),
        )
        for slug, name, description, prompt in skills:
            existing = await connection.scalar(select(GenerationSkill).where(GenerationSkill.slug == slug))
            values = {"name": name, "description": description, "prompt": prompt, "category": "motion" if slug == "gsap-scrolltrigger-fluid" else "commerce" if slug.startswith("sales-") or slug in {"product-page-audit", "prototype-social-proof"} else "design"}
            if not existing:
                await connection.execute(GenerationSkill.__table__.insert().values(slug=slug, **values))
            else:
                await connection.execute(GenerationSkill.__table__.update().where(GenerationSkill.slug == slug).values(**values))
        design_systems = (
            ("minimal-commerce", "Minimal Commerce", "Clean commerce layout with clear hierarchy and focused product conversion.", "Use a restrained neutral palette, one accent color, generous whitespace, crisp cards, clear product hierarchy and a single dominant CTA.", '{"colors":{"background":"#F8FAFC","surface":"#FFFFFF","text":"#0F172A","accent":"#2563EB"},"typography":{"fontFamily":"Inter, sans-serif","headingWeight":800,"bodyWeight":400},"radius":{"card":"16px","button":"12px"},"spacing":{"section":"64px","gap":"16px"}}', "commerce"),
            ("sales-commerce", "Sales Commerce", "White-background sales page system with a clear green primary purchase action.", "Use a sales-page visual language by default: white background, white surfaces, dark readable text, restrained borders, generous whitespace, product-first hierarchy and one primary green CTA for the real next step. Use #16A34A or a similar accessible green only for the main action, with a darker hover/focus state and visible text label. Do not turn an informational CTA into a purchase CTA. Keep the layout conventional and scannable: product and promise above the fold, benefits, demonstration/gallery, specifications, offer, objections/FAQ, proof and final CTA. Avoid dark backgrounds, neon accents, decorative gradients, excessive rounded cards and editorial experimentation unless the briefing explicitly requires a different brand identity. Preserve accessibility, mobile readability, keyboard focus and reduced motion.", '{"colors":{"background":"#FFFFFF","surface":"#FFFFFF","text":"#111827","muted":"#6B7280","accent":"#16A34A","accentHover":"#15803D","border":"#E5E7EB"},"typography":{"fontFamily":"Inter, sans-serif","headingWeight":800,"bodyWeight":400},"radius":{"card":"12px","button":"10px"},"spacing":{"section":"64px","gap":"20px"}}', "commerce"),
            ("neo-brutalist", "Neo Brutalist", "Bold high-contrast interface with expressive type and strong visual blocks.", "Use high contrast, thick borders, assertive typography, offset shadows and deliberate asymmetry. Keep controls accessible and the CTA obvious.", '{"colors":{"background":"#FFF7ED","surface":"#FFFFFF","text":"#111827","accent":"#F43F5E","border":"#111827"},"typography":{"fontFamily":"Arial, sans-serif","headingWeight":900,"bodyWeight":600},"radius":{"card":"0px","button":"0px"},"spacing":{"section":"48px","gap":"20px"}}', "expressive"),
            ("soft-wellness", "Soft Wellness", "Calm, warm and approachable system for beauty, self-care and lifestyle products.", "Use soft warm neutrals, gentle accent colors, rounded surfaces, comfortable spacing and calm microcopy. Avoid medical claims unless supplied.", '{"colors":{"background":"#FFFDF8","surface":"#FFFFFF","text":"#403A3A","accent":"#C08497","muted":"#8F7A80"},"typography":{"fontFamily":"DM Sans, sans-serif","headingWeight":700,"bodyWeight":400},"radius":{"card":"24px","button":"999px"},"spacing":{"section":"72px","gap":"20px"}}', "wellness"),
            ("dark-cinema", "Dark Cinema", "Immersive dark system for entertainment, gadgets and visual demonstrations.", "Use a dark surface, luminous accent, cinematic contrast, large visual hero and restrained motion. Keep text contrast and reduced-motion behavior accessible.", '{"colors":{"background":"#09090B","surface":"#18181B","text":"#FAFAFA","accent":"#A78BFA","muted":"#A1A1AA"},"typography":{"fontFamily":"Space Grotesk, sans-serif","headingWeight":800,"bodyWeight":400},"radius":{"card":"20px","button":"999px"},"spacing":{"section":"80px","gap":"24px"}}', "entertainment"),
            ("editorial-grid", "Editorial Grid", "Structured magazine-like system for content-rich product storytelling.", "Use a clear grid, strong typographic hierarchy, intentional whitespace and editorial rhythm. Never sacrifice mobile readability or conversion clarity.", '{"colors":{"background":"#F5F1EA","surface":"#FFFDF8","text":"#24211E","accent":"#B45309","line":"#D6CEC2"},"typography":{"fontFamily":"Georgia, serif","headingWeight":700,"bodyWeight":400},"radius":{"card":"4px","button":"4px"},"spacing":{"section":"96px","gap":"32px"}}', "content"),
        )
        for slug, name, description, prompt, tokens, category in design_systems:
            existing = await connection.scalar(select(DesignSystem).where(DesignSystem.slug == slug))
            if not existing:
                await connection.execute(DesignSystem.__table__.insert().values(slug=slug, name=name, description=description, prompt=prompt, tokens=tokens, category=category))
            elif existing:
                await connection.execute(DesignSystem.__table__.update().where(DesignSystem.id == existing).values(tokens=tokens))
    yield
    await engine.dispose()


logger = logging.getLogger("landing_page_api")
app = FastAPI(title="Landing Page Generator", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = await request.body()
    logger.warning(
        "request_validation_error method=%s path=%s errors=%s body=%s",
        request.method,
        request.url.path,
        exc.errors(),
        body[:2000].decode("utf-8", errors="replace"),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


UPLOAD_DIR = Path("assets")
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


def _delete_uploaded_images(image_urls: list[str]) -> None:
    prefix = "/api/v1/assets/images/"
    for url in image_urls:
        if not url.startswith(prefix):
            continue
        target = UPLOAD_DIR / Path(url.removeprefix(prefix)).name
        if target.is_file():
            target.unlink()


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
    return errors, warnings


def _page_response(html: str) -> tuple[str, dict[str, str]]:
    nonce = secrets.token_urlsafe(24)
    html = re.sub(
        r"<script(?![^>]*\\bsrc=)(?P<attrs>[^>]*)>",
        lambda match: f'<script{match.group("attrs")} nonce="{nonce}">',
        html,
        flags=re.IGNORECASE,
    )
    csp = "; ".join(
        (
            "default-src 'none'",
            "base-uri 'none'",
            "frame-ancestors 'self'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com 'nonce-" + nonce + "'",
            "font-src 'self' https://fonts.gstatic.com data:",
            "img-src 'self' https: data:",
        )
    )
    return html, {"Content-Security-Policy": csp}


def _json_list(value: str | None) -> list[str]:
    return json.loads(value) if value else []


def _url_list(value: str | None) -> list[str]:
    return [item.strip() for value in _json_list(value) for item in str(value).splitlines() if item.strip()]


def _product_payload(product: Product) -> dict[str, object]:
    return {
        "product_name": product.name,
        "product_description": product.description,
        "target_audience": product.audience,
        "tone": product.tone,
        "benefits": product.benefits,
        "offer": product.offer,
        "cta": product.cta,
        "language": product.language,
        "market": product.market,
        "brand_identity": product.brand_identity,
        "visual_direction": product.visual_direction,
        "reference_urls": _url_list(product.reference_urls),
        "image_urls": _url_list(product.image_urls),
    }


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
async def upload_image(file: UploadFile = File(...), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict[str, str]:
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
    session.add(Asset(filename=target.name, path=str(target), url=path, content_type=file.content_type, size_bytes=len(content)))
    await session.commit()
    return {"url": path, "public_url": path, "internal_url": f"http://api:8000{path}", "content_type": file.content_type}


@app.delete("/api/v1/assets/images/{filename}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(filename: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> None:
    asset = await session.scalar(select(Asset).where(Asset.filename == Path(filename).name))
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    target = UPLOAD_DIR / asset.filename
    if target.is_file():
        target.unlink()
    await session.delete(asset)
    await session.commit()


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


@app.get("/api/v1/design-systems", response_model=list[DesignSystemSummary])
async def list_design_systems(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[DesignSystemSummary]:
    systems = await session.scalars(select(DesignSystem).order_by(DesignSystem.category, DesignSystem.name))
    return [DesignSystemSummary(id=item.id, slug=item.slug, name=item.name, description=item.description, category=item.category, tokens=json.loads(item.tokens or "{}")) for item in systems]


@app.post("/api/v1/design-systems", response_model=DesignSystemSummary, status_code=status.HTTP_201_CREATED)
async def create_design_system(request: DesignSystemCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> DesignSystemSummary:
    if await session.scalar(select(DesignSystem).where(DesignSystem.slug == request.slug)):
        raise HTTPException(status_code=409, detail="Design system slug already exists")
    system = DesignSystem(**request.model_dump())
    session.add(system)
    await session.commit()
    await session.refresh(system)
    return DesignSystemSummary(id=system.id, slug=system.slug, name=system.name, description=system.description, category=system.category)


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


async def _generation_provider_available() -> bool:
    # Codex uses its persisted login/session; the API intentionally does not read an API key.
    return settings.codex_enabled and os.getenv("CODEX_AUTH_READY", "false").lower() == "true"


@app.post("/api/v1/generations", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    request: GenerationRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> GenerationAccepted:
    if not await _generation_provider_available():
        raise HTTPException(status_code=503, detail="Codex generation unavailable: configure Codex authentication and quota before creating a page")
    if idempotency_key:
        existing = await session.scalar(select(GenerationJob).where(GenerationJob.idempotency_key == idempotency_key))
        if existing:
            return GenerationAccepted(job_id=existing.id, status=existing.status, slug="")
    base_slug = re.sub(r"[^a-z0-9]+", "-", request.product_name.lower()).strip("-")
    slug = base_slug or f"page-{uuid4().hex[:8]}"
    suffix = 2
    while await session.scalar(select(LandingPage.id).where(LandingPage.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    product = Product(name=request.product_name, description=request.product_description, audience=request.target_audience, tone=request.tone, benefits=request.benefits, offer=request.offer, cta=request.cta, language=request.language, market=request.market, brand_identity=request.brand_identity, visual_direction=request.visual_direction, reference_urls=json.dumps(request.reference_urls), image_urls=json.dumps(request.image_urls))
    skills = await session.scalars(select(GenerationSkill).where(GenerationSkill.slug.in_(request.skill_slugs)))
    skill_prompts = [skill.prompt for skill in skills]
    design_system = await session.scalar(select(DesignSystem).where(DesignSystem.slug == request.design_system_slug)) if request.design_system_slug else None
    if request.design_system_slug and not design_system:
        raise HTTPException(status_code=422, detail="Design system not found")
    product.design_system_slug = design_system.slug if design_system else None
    if design_system:
        skill_prompts.append(f"Design system: {design_system.prompt}")
    job = GenerationJob(product=product, idempotency_key=idempotency_key, status="queued", skill_prompts=json.dumps(skill_prompts), skill_slugs=json.dumps(request.skill_slugs))
    page = LandingPage(job=job, slug=slug)
    session.add(job)
    session.add(page)
    await session.commit()
    await session.refresh(job)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": request.model_dump(), "skills": skill_prompts, "design_system": design_system.prompt if design_system else None})
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


@app.delete("/api/v1/pages/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> None:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    job = page.job
    product = job.product
    await session.delete(page)
    await session.delete(job)
    await session.delete(product)
    await session.commit()


@app.get("/api/v1/pages/{slug}/briefing", response_model=BriefingResponse)
async def get_briefing(slug: str, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> BriefingResponse:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    product = page.job.product
    skill_slugs = _json_list(page.job.skill_slugs)
    return BriefingResponse(job_id=page.job.id, status=page.job.status, product_name=product.name, product_description=product.description, target_audience=product.audience, benefits=product.benefits, offer=product.offer, cta=product.cta, language=product.language, market=product.market, tone=product.tone, brand_identity=product.brand_identity, visual_direction=product.visual_direction, reference_urls=_json_list(product.reference_urls), image_urls=_url_list(product.image_urls), skill_slugs=skill_slugs, design_system_slug=product.design_system_slug)


@app.put("/api/v1/pages/{slug}/briefing", response_model=BriefingResponse)
async def update_briefing(slug: str, request: BriefingUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> BriefingResponse:
    page = await session.scalar(select(LandingPage).options(selectinload(LandingPage.job).selectinload(GenerationJob.product)).where(LandingPage.slug == slug))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    product = page.job.product
    for field in ("product_name", "product_description", "target_audience", "benefits", "offer", "cta", "tone", "visual_direction"):
        setattr(product, {"product_name": "name", "product_description": "description", "target_audience": "audience"}.get(field, field), getattr(request, field))
    if request.reference_urls is not None:
        product.reference_urls = json.dumps(request.reference_urls)
    if request.image_urls is not None:
        product.image_urls = json.dumps(request.image_urls)
    skill_slugs = request.skill_slugs if request.skill_slugs is not None else []
    skills = await session.scalars(select(GenerationSkill).where(GenerationSkill.slug.in_(skill_slugs)))
    system = await session.scalar(select(DesignSystem).where(DesignSystem.slug == request.design_system_slug)) if request.design_system_slug else None
    if request.design_system_slug and not system:
        raise HTTPException(status_code=422, detail="Design system not found")
    product.design_system_slug = system.slug if system else None
    prompts = [skill.prompt for skill in skills]
    if system:
        prompts.append(f"Design system: {system.prompt}")
    page.job.skill_prompts = json.dumps(prompts)
    page.job.skill_slugs = json.dumps(skill_slugs)
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
    html, headers = _page_response(version.html)
    return HTMLResponse(html, headers=headers)


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
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": _product_payload(product), "skills": skills})
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
    job = page.job
    skills = _json_list(job.skill_prompts)
    job.status = "queued"
    job.error_message = None
    await session.commit()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(settings.n8n_webhook_url, json={"job_id": str(job.id), "product": _product_payload(product), "feedback": feedback_items, "skills": skills})
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
    errors = [error for error in _json_list(version.validation_errors) if error != "HTML contains unresolved placeholders"]
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
    html, headers = _page_response(version.html)
    return HTMLResponse(html, headers=headers)
