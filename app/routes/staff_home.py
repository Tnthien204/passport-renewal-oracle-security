from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.utils.session import require_login, redirect_err

router = APIRouter(prefix="/staff")


@router.get("", response_class=HTMLResponse)
def staff_home(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("auth_type") != "staff":
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    role = request.session.get("role")
    if role == "XT":
        return RedirectResponse("/staff/xt", status_code=HTTP_302_FOUND)
    if role == "XD":
        return RedirectResponse("/staff/xd", status_code=HTTP_302_FOUND)
    if role == "LT":
        return RedirectResponse("/staff/lt", status_code=HTTP_302_FOUND)
    if role in {"GS"}:
        return RedirectResponse("/staff/gs", status_code=HTTP_302_FOUND)
    if role == "ADMIN":
        return RedirectResponse("/admin", status_code=HTTP_302_FOUND)
    return redirect_err("/login", "Unknown role")
