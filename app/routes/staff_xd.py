# staff_xd.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from app.web.templates import templates
from app.utils.session import (
    require_login,
    qparam,
    redirect_err,
    redirect_ok,
    staff_conn,
    set_client_identifier,  # ✅ NEW
)

router = APIRouter(prefix="/staff/xd")


@router.get("", response_class=HTMLResponse)
def xd_queue(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "XD":
        return redirect_err("/login", "No permission")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:XD")

        cur = conn.cursor()
        cur.execute("""
            SELECT APP_NO, CMND, FULL_NAME,
                   XT_RESULT, XT_AT, XT_NOTE,
                   PASSPORT_NO, STATUS
              FROM ADMIN.PASSPORT_RENEWAL_APP
             ORDER BY XT_AT
        """)
        rows = cur.fetchall()
        cur.close()

        return templates.TemplateResponse("xd_queue.html", {
            "request": request,
            "rows": rows,
            "user": db_user,
            "ok": qparam(request, "ok"),
            "err": qparam(request, "err"),
        })
    except Exception as e:
        return templates.TemplateResponse("xd_queue.html", {
            "request": request,
            "rows": [],
            "user": request.session.get("db_user"),
            "ok": "",
            "err": f"DB error: {str(e)[:200]}",
        })
    finally:
        conn.close()


@router.post("/decide")
def xd_decide(
    request: Request,
    app_no: str = Form(...),
    decision: str = Form(...),
    note: str = Form("")
):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "XD":
        return redirect_err("/login", "No permission")

    decision = (decision or "").upper().strip()
    if decision not in {"APPROVE", "REJECT"}:
        return redirect_err("/staff/xd", "Invalid decision")

    app_no = (app_no or "").strip()
    if not app_no:
        return redirect_err("/staff/xd", "Missing APP_NO")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:XD")

        cur = conn.cursor()

        # ✅ call stored procedure instead of direct UPDATE
        # ADMIN.PROC_XD_DECIDE(p_app_no, p_decision, p_note)
        cur.callproc("ADMIN.PROC_XD_DECIDE", [app_no, decision, note])

        conn.commit()
        cur.close()
        return redirect_ok("/staff/xd", f"Updated {app_no}")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/staff/xd", f"Update failed: {str(e)[:180]}")
    finally:
        conn.close()
