from datetime import datetime, date

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

router = APIRouter(prefix="/staff/lt")


def _parse_iso_date(s: str) -> date:
    """
    Expect 'YYYY-MM-DD' (browser <input type="date"> submits this).
    Return python date to bind safely into Oracle DATE (avoid ORA-01861).
    """
    s = (s or "").strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("Invalid date format. Use YYYY-MM-DD (input type=date).")


@router.get("", response_class=HTMLResponse)
def lt_queue(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "LT":
        return redirect_err("/login", "No permission")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:LT")

        cur = conn.cursor()

        # ✅ LT đọc qua VIEW (không đọc trực tiếp bảng có PII)
        cur.execute(
            """
            SELECT a.APP_NO,
                   a.PASSPORT_NO,
                   a.XD_DECISION,
                   a.XD_AT,
                   p.EXPIRY_DATE AS OLD_EXPIRY
              FROM ADMIN.VW_LT_RENEWAL_APP a
              JOIN ADMIN.VW_LT_PASSPORT   p
                ON p.PASSPORT_NO = a.PASSPORT_NO
             ORDER BY a.XD_AT NULLS LAST
            """
        )
        rows = cur.fetchall()
        cur.close()

        return templates.TemplateResponse(
            "lt_queue.html",
            {
                "request": request,
                "rows": rows,
                "user": db_user,
                "ok": qparam(request, "ok"),
                "err": qparam(request, "err"),
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "lt_queue.html",
            {
                "request": request,
                "rows": [],
                "user": request.session.get("db_user"),
                "ok": "",
                "err": f"DB error: {str(e)[:200]}",
            },
        )
    finally:
        conn.close()


@router.post("/update")
def lt_update(
    request: Request,
    app_no: str = Form(...),
    new_expiry_date: str = Form(...),
):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "LT":
        return redirect_err("/login", "No permission")

    app_no = (app_no or "").strip()
    if not app_no:
        return redirect_err("/staff/lt", "Missing APP_NO")

    # ✅ Parse date in Python -> bind as DATE (fix ORA-01861)
    try:
        new_exp_date = _parse_iso_date(new_expiry_date)
    except ValueError as ve:
        return redirect_err("/staff/lt", str(ve))

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:LT")

        cur = conn.cursor()

        # ✅ Check nhanh: APP có trong danh sách LT thấy + phải APPROVE
        cur.execute(
            """
            SELECT 1
              FROM ADMIN.VW_LT_RENEWAL_APP
             WHERE APP_NO = :a
               AND XD_DECISION = 'APPROVE'
            """,
            {"a": app_no},
        )
        ok = cur.fetchone()
        if not ok:
            cur.close()
            return redirect_err("/staff/lt", "APP_NO not in your scope (must be XD_DONE & APPROVE)")

        # ✅ Gọi procedure:
        #   ADMIN.PROC_LT_COMPLETE(p_app_no IN VARCHAR2, p_new_exp IN DATE)
        cur.callproc("ADMIN.PROC_LT_COMPLETE", [app_no, new_exp_date])

        conn.commit()
        cur.close()

        return redirect_ok("/staff/lt", f"Completed {app_no} (Passport updated)")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/staff/lt", f"Update failed: {str(e)[:180]}")
    finally:
        conn.close()
