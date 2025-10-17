# backend/auth.py
import os
from typing import Optional
from fastapi import HTTPException, Header

# Можешь переопределять через переменные окружения
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")
ADMIN_TOKEN    = os.getenv("ADMIN_TOKEN", "web3live")  # тот же, что использует клиент

def verify_credentials(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def create_token(username: str) -> str:
    # Для MVP токен фиксированный — достаточно
    return ADMIN_TOKEN

def verify_token(Authorization: Optional[str] = Header(None)):
    if not Authorization or not Authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="No token")
    token = Authorization.split(" ", 1)[1].strip()
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Bad token")
    return {"user": ADMIN_USERNAME}
