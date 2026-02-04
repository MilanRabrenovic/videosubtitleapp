"""Authentication routes."""

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import AUTH_COOKIE_NAME, TEMPLATES_DIR
from app.services.auth import authenticate_user, create_session, create_user, destroy_session, get_auth_context

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/login")
def login_form(request: Request) -> Any:
    auth = get_auth_context(request)
    if auth.user:
        return RedirectResponse(url="/upload", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form("")) -> Any:
    user_id = authenticate_user(email, password)
    if not user_id:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
        )
    token = create_session(user_id)
    response = RedirectResponse(url="/upload", status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
    )
    return response


@router.get("/signup")
def signup_form(request: Request) -> Any:
    auth = get_auth_context(request)
    if auth.user:
        return RedirectResponse(url="/upload", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})


@router.post("/signup")
def signup(request: Request, email: str = Form(""), password: str = Form("")) -> Any:
    user_id = create_user(email, password)
    if not user_id:
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Unable to create account. Try a different email."},
        )
    token = create_session(user_id)
    response = RedirectResponse(url="/upload", status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
    )
    return response


@router.post("/logout")
def logout(request: Request) -> Any:
    auth = get_auth_context(request)
    response = RedirectResponse(url="/login", status_code=303)
    if auth.token:
        destroy_session(auth.token)
        response.delete_cookie(AUTH_COOKIE_NAME)
    return response
