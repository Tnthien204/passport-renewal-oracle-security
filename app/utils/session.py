from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.core.db import make_conn


def is_staff(u: str) -> bool:
    u = (u or "").upper()
    return u.startswith("XT_") or u in {"XD_USER", "LT_USER", "GS_USER", "ADMIN"}


def role_of(u: str) -> str:
    u = (u or "").upper()
    if u.startswith("XT_"):
        return "XT"
    if u == "XD_USER":
        return "XD"
    if u == "LT_USER":
        return "LT"
    if u == "GS_USER":
        return "GS"
    if u == "ADMIN":
        return "ADMIN"
    return "UNKNOWN"


def require_login(request: Request):
    if not request.session.get("auth_type"):
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)
    return None


def qparam(request: Request, key: str, default: str = "") -> str:
    return request.query_params.get(key, default)


def redirect_err(url: str, msg: str):
    return RedirectResponse(f"{url}?err={msg.replace(' ', '+')}", status_code=HTTP_302_FOUND)


def redirect_ok(url: str, msg: str):
    return RedirectResponse(f"{url}?ok={msg.replace(' ', '+')}", status_code=HTTP_302_FOUND)


def set_app_ctx_cmnd(conn, cmnd: str):
    cur = conn.cursor()
    try:
        cur.execute("BEGIN ADMIN.PKG_APP_CTX.SET_CMND(:p); END;", {"p": cmnd})
    finally:
        cur.close()


def set_client_identifier(conn, client_id: str):
    """
    Set CLIENT_IDENTIFIER for auditing/logging.
    This value is visible in SYS_CONTEXT('USERENV','CLIENT_IDENTIFIER')
    and is captured by Unified Auditing / V$ views.
    """
    client_id = (client_id or "").strip()
    if not client_id:
        return
    # giữ an toàn độ dài (Oracle thường 64/128 tùy phiên bản/config)
    client_id = client_id[:128]

    cur = conn.cursor()
    try:
        cur.execute("BEGIN DBMS_SESSION.SET_IDENTIFIER(:x); END;", {"x": client_id})
    finally:
        cur.close()


def staff_conn(request: Request):
    return make_conn(request.session["db_user"], request.session["db_pass"])
