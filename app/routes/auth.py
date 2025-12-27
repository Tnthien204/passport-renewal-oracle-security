from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_302_FOUND
import oracledb

from app.web.templates import templates
from app.core.config import ONLINE_APP_USER, ONLINE_APP_PASS
from app.core.db import make_conn
from app.utils.session import is_staff, role_of, redirect_err

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    if request.session.get("auth_type") == "citizen":
        return RedirectResponse("/citizen", status_code=HTTP_302_FOUND)
    if request.session.get("auth_type") == "staff":
        return RedirectResponse("/staff", status_code=HTTP_302_FOUND)
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)


# -----------------------------
# Citizen login (ONLINE_APP)
# -----------------------------
@router.post("/login/citizen")
def login_citizen(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    username = (username or "").strip().lower()
    password = (password or "")

    conn = make_conn(ONLINE_APP_USER, ONLINE_APP_PASS)
    try:
        cur = conn.cursor()
        ok = cur.var(oracledb.DB_TYPE_CHAR, size=1)
        cmnd = cur.var(oracledb.DB_TYPE_VARCHAR, size=50)

        cur.callproc("ADMIN.PROC_AUTH_USER", [username, password, ok, cmnd])
        cur.close()

        okv = (ok.getvalue() or "N").strip().upper()
        if okv != "Y":
            return redirect_err("/login", "Citizen login failed")

        request.session.clear()
        request.session["auth_type"] = "citizen"
        request.session["citizen_username"] = username
        request.session["citizen_cmnd"] = (cmnd.getvalue() or "").strip()
        return RedirectResponse("/citizen", status_code=HTTP_302_FOUND)

    except Exception as e:
        return redirect_err("/login", f"Citizen login error: {str(e)[:120]}")
    finally:
        conn.close()


# -----------------------------
# Register
# -----------------------------
@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    from app.utils.session import qparam
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "ok": qparam(request, "ok"), "err": qparam(request, "err")}
    )


@router.post("/register")
def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    cmnd: str = Form(...)
):
    from app.utils.session import redirect_ok

    username = (username or "").strip().lower()
    cmnd = (cmnd or "").strip()

    conn = make_conn(ONLINE_APP_USER, ONLINE_APP_PASS)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN ADMIN.PROC_CREATE_ACCOUNT(:u, :p, :c); END;", {
            "u": username, "p": password, "c": cmnd
        })
        conn.commit()
        cur.close()
        return redirect_ok("/login", "Registered successfully. Please login.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass

        msg = str(e)
        if "ORA-00001" in msg:
            return redirect_err("/register", "Username already exists")
        if "ORA-02291" in msg:
            return redirect_err("/register", "CMND not found in RESIDENT_PROFILE")
        if "ORA-01031" in msg:
            return redirect_err("/register", "ONLINE_APP has no EXECUTE on PROC_CREATE_ACCOUNT")
        return redirect_err("/register", f"Register failed: {msg[:140]}")
    finally:
        conn.close()


# -----------------------------
# Staff login (DB users)
# -----------------------------
@router.post("/login/staff")
def login_staff(
    request: Request,
    db_user: str = Form(...),
    db_pass: str = Form(...)
):
    db_user = (db_user or "").upper().strip()
    if not is_staff(db_user):
        return redirect_err("/login", "Invalid staff user")

    try:
        conn = make_conn(db_user, db_pass)
        conn.close()
    except Exception:
        return redirect_err("/login", "Staff login failed")

    request.session.clear()
    request.session["auth_type"] = "staff"
    request.session["db_user"] = db_user
    request.session["db_pass"] = db_pass
    request.session["role"] = role_of(db_user)
    return RedirectResponse("/staff", status_code=HTTP_302_FOUND)
