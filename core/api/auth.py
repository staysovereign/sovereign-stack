from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from core import auth
from core.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

_MIN_LEN = 6


class PasswordIn(BaseModel):
    password: str


class ChangeIn(BaseModel):
    current_password: str
    new_password: str


@router.get("/status")
async def status_(authorization: str | None = Header(default=None)):
    """Unauthenticated: tells the UI whether a password is set and whether this
    client's token is currently valid — so it can show Setup, Login, or the app."""
    async with get_db() as db:
        configured = bool(await auth.get_password_hash(db))
    token = auth.bearer_from_header(authorization)
    return {"configured": configured, "authenticated": auth.check_token(token)}


@router.post("/setup")
async def setup(body: PasswordIn):
    """First-run: set the password. Only allowed when none is configured yet."""
    async with get_db() as db:
        if await auth.get_password_hash(db):
            raise HTTPException(status.HTTP_409_CONFLICT, "Password already set")
        if len(body.password) < _MIN_LEN:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Password must be at least {_MIN_LEN} characters")
        await auth.set_password_hash(db, auth.hash_password(body.password))
    return {"token": auth.issue_token()}


@router.post("/login")
async def login(body: PasswordIn):
    async with get_db() as db:
        stored = await auth.get_password_hash(db)
    if not auth.verify_password(body.password, stored):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")
    return {"token": auth.issue_token()}


@router.post("/change")
async def change(body: ChangeIn, authorization: str | None = Header(default=None)):
    if not auth.check_token(auth.bearer_from_header(authorization)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    async with get_db() as db:
        stored = await auth.get_password_hash(db)
        if not auth.verify_password(body.current_password, stored):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
        if len(body.new_password) < _MIN_LEN:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Password must be at least {_MIN_LEN} characters")
        await auth.set_password_hash(db, auth.hash_password(body.new_password))
    auth.revoke_all()  # invalidate every existing session…
    return {"token": auth.issue_token()}  # …but keep this client signed in


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)):
    auth.revoke_token(auth.bearer_from_header(authorization))
    return {"status": "ok"}
