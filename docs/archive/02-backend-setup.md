# Backend Setup Guide

## Project Structure

```
src/
├── __init__.py
├── main.py                 # FastAPI app entry point
├── api/
│   ├── __init__.py
│   ├── auth.py            # Login, signup, token refresh
│   ├── chat.py            # Chat streaming, knowledge bases
│   ├── knowledge_base.py   # CRUD for knowledge bases
│   ├── api_keys.py        # API key generation & revocation
│   ├── billing.py         # Stripe checkout, invoices
│   └── webhooks.py        # GitHub, Stripe events
├── core/
│   ├── __init__.py
│   ├── config.py          # Environment variables, settings
│   ├── database.py        # SQLAlchemy setup, session factory
│   ├── security.py        # JWT, API key, password hashing
│   └── middleware.py      # Auth verification, request tracking
├── models/
│   ├── __init__.py
│   └── database.py        # All SQLAlchemy models (Tenant, User, etc.)
├── services/
│   ├── __init__.py
│   ├── inference.py       # RAG + LLM streaming
│   ├── billing.py         # Token usage tracking, invoicing
│   ├── data_loader.py     # GitHub API, document ingestion
│   └── rag.py             # Vector DB queries, context retrieval
└── middleware/
    ├── __init__.py
    └── auth.py            # Request-level auth checks
```

## Step 1: Environment Configuration

**Create `.env` file** (copy from `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://saas_user:saas_password@db:5432/saas_prod
REDIS_URL=redis://redis:6379/0

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Stripe
STRIPE_SECRET_KEY=sk_live_51234567890
STRIPE_WEBHOOK_SECRET=whsec_1234567890

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here

# GPU Inference
MODEL_ID=meta-llama/Llama-2-70b-chat-hf
TENSOR_PARALLEL_SIZE=2
GPU_MEMORY_UTILIZATION=0.85

# Application
DEBUG=False
LOG_LEVEL=INFO
FRONTEND_URL=https://app.yourdomain.com
```

## Step 2: Core Configuration

**src/core/config.py**:

```python
from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL")
    redis_url: str = os.getenv("REDIS_URL")
    
    # JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Stripe
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    # Application
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    frontend_url: str = os.getenv("FRONTEND_URL")
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## Step 3: Database Setup

**src/core/database.py**:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()

async def init_db():
    """Create all tables on startup"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

async def get_db():
    """Dependency to inject DB session into endpoints"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

## Step 4: Models Definition

**src/models/database.py**:

See `CLAUDE.md` for full schema. Key tables:

```python
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum, Text, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base
import enum

class TierEnum(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True)
    email = Column(String(255), unique=True)
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    tier = Column(Enum(TierEnum), default=TierEnum.free)
    max_monthly_tokens = Column(Integer, default=100000)
    max_concurrent_requests = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True)
    
    users = relationship("User", back_populates="tenant")
    api_keys = relationship("APIKey", back_populates="tenant")
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), index=True)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="users")
```

## Step 5: Security & Auth

**src/core/security.py**:

```python
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from core.config import settings
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_jwt_token(user_id: str, tenant_id: str) -> str:
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
```

**src/core/middleware.py**:

```python
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthCredential
from core.security import verify_jwt_token
from core.database import AsyncSessionLocal, get_db
from sqlalchemy import select
from models.database import Tenant, User
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()

async def get_current_tenant(
    request: Request,
    credentials: HTTPAuthCredential = Depends(security),
    db = Depends(get_db)
) -> Tenant:
    """
    Extract tenant from JWT or API key.
    Sets request.state.tenant_id for downstream RLS.
    """
    token = credentials.credentials
    
    # Verify JWT
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Fetch tenant
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Tenant not found or inactive")
    
    # Set request context for RLS
    request.state.tenant_id = tenant_id
    request.state.user_id = payload.get("user_id")
    
    return tenant
```

## Step 6: API Routes

**src/api/auth.py** (Login/Signup):

```python
from fastapi import APIRouter, HTTPException, Depends
from core.database import get_db, AsyncSessionLocal
from core.security import hash_password, verify_password, create_jwt_token
from models.database import Tenant, User
from sqlalchemy import select
import uuid
import logging

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

@router.post("/signup")
async def signup(
    email: str,
    company_name: str,
    password: str,
    db = Depends(get_db)
):
    """Create new tenant account"""
    
    # Check if email already exists
    stmt = select(Tenant).where(Tenant.email == email)
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Create tenant
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=company_name,
        slug=company_name.lower().replace(" ", "-"),
        email=email,
        tier="free"
    )
    
    # Create admin user
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(password),
        role="admin"
    )
    
    db.add(tenant)
    db.add(user)
    await db.commit()
    
    logger.info(f"New tenant created: {company_name}")
    
    return {
        "tenant_id": tenant.id,
        "access_token": create_jwt_token(user.id, tenant.id),
        "token_type": "bearer"
    }

@router.post("/login")
async def login(
    email: str,
    password: str,
    db = Depends(get_db)
):
    """User login"""
    
    stmt = select(User).where(User.email == email)
    user = await db.execute(stmt)
    user = user.scalar_one_or_none()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    return {
        "access_token": create_jwt_token(user.id, user.tenant_id),
        "token_type": "bearer"
    }
```

## Step 7: FastAPI Application

**src/main.py**:

```python
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn
import os

from core.database import init_db, get_db
from core.config import settings
from core.middleware import get_current_tenant
from api import auth, chat, knowledge_base, billing, webhooks

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing SaaS platform...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="Portfolio AI SaaS",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com", "https://app.yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Routes
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(knowledge_base.router)
app.include_router(billing.router)
app.include_router(webhooks.router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
```

## Step 8: Database Migrations with Alembic

**Initialize Alembic**:

```bash
pip install alembic
alembic init alembic
```

**alembic/env.py** (snippet):

```python
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from alembic import context
from core.config import settings
from models.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()
```

**Create initial migration**:

```bash
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

## Step 9: Services Layer

**src/services/inference.py**:

```python
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class InferenceService:
    def __init__(self, tenant_id: str, engine):
        self.tenant_id = tenant_id
        self.engine = engine
    
    async def stream_rag_response(
        self,
        message: str,
        session
    ) -> AsyncGenerator[str, None]:
        """
        Stream RAG response to user.
        1. Retrieve context from Qdrant
        2. Stream from vLLM
        3. Track usage
        """
        try:
            context = await self.engine.get_context(message, self.tenant_id)
            
            async for token in self.engine.stream_chat(message, context):
                yield token
                
        except Exception as e:
            logger.error(f"Inference error for {self.tenant_id}: {e}")
            raise
```

## Running Locally

```bash
# 1. Start services
docker-compose up -d

# 2. Run migrations
docker exec portfolio-saas-api-1 alembic upgrade head

# 3. Test API
curl http://localhost:8000/health

# 4. Test signup
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","company_name":"Test Co","password":"pass123"}'

# 5. View logs
docker logs -f portfolio-saas-api-1
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Database connection failed | Check DATABASE_URL in .env, ensure PostgreSQL container is running |
| JWT decode error | Verify JWT_SECRET_KEY is set, token not expired |
| CORS errors | Add origin to allow_origins in FastAPI config |
| Port 8000 already in use | Kill process: `lsof -i :8000` → `kill -9 <PID>` |

---

**Next Steps**: Refer to `03-frontend-setup.md` for dashboard implementation.
