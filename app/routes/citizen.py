# citizen.py
import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.web.templates import templates
from app.core.config import ONLINE_APP_USER, ONLINE_APP_PASS
from app.core.db import make_conn
from app.utils.session import (
    require_login,
    qparam,
    redirect_err,
    redirect_ok,
    set_app_ctx_cmnd,
    set_client_identifier,   # ✅ NEW
)

router = APIRouter(prefix="/citizen")


def _new_app_no() -> str:
    return str(uuid.uuid4())


@router.get("", response_class=HTMLResponse)
def citizen_dashboard(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("auth_type") != "citizen":
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    cmnd = request.session["citizen_cmnd"]
    username = request.session.get("citizen_username", "?")

    conn = make_conn(ONLINE_APP_USER, ONLINE_APP_PASS)
    try:
        # VPD needs context CMND
        set_app_ctx_cmnd(conn, cmnd)

        # ✅ NEW: set client identifier for audit/logging
        set_client_identifier(conn, f"CITIZEN:{username}|CMND:{cmnd}")

        cur = conn.cursor()
        # VPD already filters IS_DELETED='N' for ONLINE_APP
        cur.execute("""
            SELECT APP_NO, STATUS, SUBMITTED_AT, PASSPORT_NO,
                   XT_UNIT, XT_RESULT, XD_DECISION, NEW_EXPIRY_DATE
              FROM ADMIN.PASSPORT_RENEWAL_APP
             ORDER BY SUBMITTED_AT DESC
        """)
        rows = cur.fetchall()
        cur.close()

        return templates.TemplateResponse("citizen_dashboard.html", {
            "request": request,
            "rows": rows,
            "cmnd": cmnd,
            "username": username,
            "ok": qparam(request, "ok"),
            "err": qparam(request, "err"),
        })
    except Exception as e:
        return templates.TemplateResponse("citizen_dashboard.html", {
            "request": request,
            "rows": [],
            "cmnd": cmnd,
            "username": username,
            "ok": "",
            "err": f"DB error: {str(e)[:200]}",
        })
    finally:
        conn.close()


@router.get("/submit", response_class=HTMLResponse)
def citizen_submit_page(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("auth_type") != "citizen":
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    return templates.TemplateResponse("citizen_submit.html", {
        "request": request,
        "ok": qparam(request, "ok"),
        "err": qparam(request, "err"),
    })


@router.post("/submit")
def citizen_submit(
    request: Request,
    full_name: str = Form(...),
    permanent_address: str = Form(...),
    gender: str = Form(...),
    cmnd: str = Form(...),
    phone: str = Form(""),
    email: str = Form(""),
    passport_no: str = Form(...),
):
    r = require_login(request)
    if r:
        return r
    if request.session.get("auth_type") != "citizen":
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    if cmnd != request.session.get("citizen_cmnd"):
        return redirect_err("/citizen/submit", "CMND must match login")

    gender = (gender or "").upper().strip()
    if gender not in {"M", "F", "O"}:
        return redirect_err("/citizen/submit", "Invalid gender (M/F/O)")

    username = request.session.get("citizen_username", "?")

    conn = make_conn(ONLINE_APP_USER, ONLINE_APP_PASS)
    try:
        set_app_ctx_cmnd(conn, cmnd)

        # ✅ NEW: set client identifier for audit/logging
        set_client_identifier(conn, f"CITIZEN:{username}|CMND:{cmnd}")

        app_no = _new_app_no()
        cur = conn.cursor()

        # ✅ Call stored procedure instead of direct INSERT
        # ADMIN.PROC_SUBMIT_APP(
        #   p_app_no, p_submitter_username, p_full_name, p_address, p_gender,
        #   p_cmnd, p_phone, p_email, p_passport_no
        # )
        cur.callproc("ADMIN.PROC_SUBMIT_APP", [
            app_no,
            username,
            full_name.strip(),
            permanent_address.strip(),
            gender,
            cmnd.strip(),
            (phone or "").strip(),
            (email or "").strip(),
            passport_no.strip(),
        ])

        conn.commit()
        cur.close()
        return redirect_ok("/citizen", f"Submitted. APP_NO={app_no}")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        msg = str(e)[:180]
        if "ORA-20001" in msg:
            msg = "CMND not found in RESIDENT_PROFILE (cannot submit)."
        return redirect_err("/citizen/submit", f"Submit failed: {msg}")
    finally:
        conn.close()


@router.post("/delete")
def citizen_delete(
    request: Request,
    app_no: str = Form(...),
):
    r = require_login(request)
    if r:
        return r
    if request.session.get("auth_type") != "citizen":
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)

    cmnd = request.session["citizen_cmnd"]
    username = request.session.get("citizen_username", "?")

    app_no = (app_no or "").strip()
    if not app_no:
        return redirect_err("/citizen", "Missing APP_NO")

    conn = make_conn(ONLINE_APP_USER, ONLINE_APP_PASS)
    try:
        set_app_ctx_cmnd(conn, cmnd)

        # ✅ NEW: set client identifier for audit/logging
        set_client_identifier(conn, f"CITIZEN:{username}|CMND:{cmnd}")

        cur = conn.cursor()

        # ✅ Call procedure instead of direct UPDATE
        # ADMIN.PROC_CITIZEN_SOFT_DELETE(p_app_no)
        cur.callproc("ADMIN.PROC_CITIZEN_SOFT_DELETE", [app_no])

        conn.commit()
        cur.close()

        return redirect_ok("/citizen", f"Deleted (soft) {app_no}")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/citizen", f"Delete failed: {str(e)[:180]}")
    finally:
        conn.close()
