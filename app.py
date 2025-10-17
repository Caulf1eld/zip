import os, re, uvicorn
import os, uuid, pathlib
import json, pathlib
from fastapi.responses import JSONResponse
from typing import List, Optional
from pydantic import BaseModel
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from models import Base, Post
from auth import create_token, verify_token, verify_credentials
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
from pathlib import Path


ADMIN_TOKEN = "web3live"

DB_URL = "sqlite:///db.sqlite3"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base.metadata.create_all(engine)

app = FastAPI(title="web3live API")

# Папка для загрузок
UPLOAD_DIR = pathlib.Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Раздача загруженных файлов по /uploads/...
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ---------- Schemas ----------
class LoginIn(BaseModel):
    username: str
    password: str

import re

def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return s or "post"


class PostIn(BaseModel):
    title: str
    slug: Optional[str] = None
    cover_url: Optional[str] = ""
    excerpt: Optional[str] = ""
    content_html: str
    tags: Optional[str] = ""
    status: Optional[str] = "published"

    @field_validator("slug")
    @classmethod
    def make_slug(cls, v, values):
        if v: return v
        title = values.get("title","")
        s = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
        return s or "post"

class PostOut(BaseModel):
    id: int
    title: str
    slug: str
    cover_url: str
    excerpt: str
    content_html: str
    tags: str
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_orm_post(cls, p: Post):
        return cls(
            id=p.id, title=p.title, slug=p.slug, cover_url=p.cover_url or "",
            excerpt=p.excerpt or "", content_html=p.content_html, tags=p.tags or "",
            status=p.status, created_at=p.created_at.isoformat(), updated_at=p.updated_at.isoformat()
        )

# ---------- Auth ----------
@app.post("/auth/login")
def login(data: LoginIn):
    if not verify_credentials(data.username, data.password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    return {"token": create_token(data.username)}

# ---------- CRUD ----------
@app.get("/posts", response_model=List[PostOut])
def list_posts(status: Optional[str] = None):
    with SessionLocal() as s:
        stmt = select(Post).order_by(Post.created_at.desc())
        posts = s.execute(stmt).scalars().all()
        if status:
            posts = [p for p in posts if p.status == status]
        return [PostOut.from_orm_post(p) for p in posts]

@app.get("/posts/{slug}", response_model=PostOut)
def get_post(slug: str):
    with SessionLocal() as s:
        p = s.query(Post).filter(Post.slug == slug).first()
        if not p: raise HTTPException(status_code=404, detail="Not found")
        return PostOut.from_orm_post(p)

@app.post("/posts", response_model=PostOut)
def create_post(data: PostIn, _user=Depends(verify_token)):
    payload = data.model_dump()
    payload["slug"] = payload.get("slug") or slugify(payload.get("title", ""))
    with SessionLocal() as s:
        if s.query(Post).filter(Post.slug == payload["slug"]).first():
            raise HTTPException(status_code=400, detail="Slug already exists")
        p = Post(**payload)
        s.add(p); s.commit(); s.refresh(p)
        return PostOut.from_orm_post(p)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # Проверка расширения
    ext = pathlib.Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Allowed: {', '.join(ALLOWED_EXT)}")

    # Ограничение размера
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Уникальное имя
    name = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / name
    with open(path, "wb") as f:
        f.write(contents)

    # Публичный URL (локально)
    url = f"/uploads/{name}"
    return {"url": url, "filename": name}


@app.put("/posts/{post_id}", response_model=PostOut)
def update_post(post_id: int, data: PostIn, _user=Depends(verify_token)):
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        if not p: raise HTTPException(status_code=404, detail="Not found")
        payload = data.model_dump()
        payload["slug"] = payload.get("slug") or slugify(payload.get("title", p.title))
        for k, v in payload.items(): setattr(p, k, v)
        s.commit(); s.refresh(p)
        return PostOut.from_orm_post(p)


@app.delete("/posts/{post_id}")
def delete_post(post_id: int, _user=Depends(verify_token)):
    with SessionLocal() as s:
        p = s.get(Post, post_id)
        if not p: raise HTTPException(status_code=404, detail="Not found")
        s.delete(p); s.commit()
        return {"ok": True}

# ---------- CONFIG (JSON-файл для панели) ----------

CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"

# Если файла нет — создаём пустой шаблон
if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps({
        "spotlight": {
            "title": "TON: Рост экосистемы",
            "text": "Новые активные кошельки, mini-apps и кейсы интеграций Telegram Wallet.",
            "image": "/uploads/example.jpg",
            "cta_text": "Смотреть гайды",
            "cta_href": "https://web3live.ru"
        }
    }, ensure_ascii=False, indent=2), encoding="utf-8")



@app.get("/config")
def get_config():
    """Возвращает JSON-конфиг сайта (UTF-8)"""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return JSONResponse(content=data, media_type="application/json; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/config")
def update_config(new_data: dict, _user=Depends(verify_token)):
    """Обновляет JSON-конфиг (требуется авторизация)."""
    try:
        CONFIG_PATH.write_text(
            json.dumps(new_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
BASE_DIR = Path(__file__).resolve().parent.parent     # .../backend
SITE_DIR = BASE_DIR / "site"                          # .../backend/site

# ВАЖНО: это добавляем ПОСЛЕ всех @app.get(...) вашего API,
# чтобы API перехватывал /posts, /config и т.п.
app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")




if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
