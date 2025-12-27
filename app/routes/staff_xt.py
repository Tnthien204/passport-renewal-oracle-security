# staff_xt.py
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

router = APIRouter(prefix="/staff/xt")


@router.get("", response_class=HTMLResponse)
def xt_queue(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "XT":
        return redirect_err("/login", "No permission")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:XT")

        cur = conn.cursor()
        cur.execute("""
            SELECT APP_NO, CMND, FULL_NAME, STATUS, SUBMITTED_AT, XT_RESULT, XT_NOTE, PASSPORT_NO
              FROM ADMIN.PASSPORT_RENEWAL_APP
             ORDER BY SUBMITTED_AT
        """)
        rows = cur.fetchall()
        cur.close()

        return templates.TemplateResponse("xt_queue.html", {
            "request": request,
            "rows": rows,
            "user": db_user,
            "ok": qparam(request, "ok"),
            "err": qparam(request, "err"),
        })
    except Exception as e:
        return templates.TemplateResponse("xt_queue.html", {
            "request": request,
            "rows": [],
            "user": request.session.get("db_user"),
            "ok": "",
            "err": f"DB error: {str(e)[:200]}",
        })
    finally:
        conn.close()


@router.get("/detail", response_class=HTMLResponse)
def xt_detail(request: Request, app_no: str = ""):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "XT":
        return redirect_err("/login", "No permission")

    app_no = (app_no or "").strip()
    if not app_no:
        return redirect_err("/staff/xt", "Missing APP_NO")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:XT")

        cur = conn.cursor()

        cur.execute("""
            SELECT APP_NO, CMND, FULL_NAME, GENDER, PERMANENT_ADDRESS, PASSPORT_NO,
                   SUBMITTED_AT, STATUS, XT_RESULT, XT_NOTE
              FROM ADMIN.PASSPORT_RENEWAL_APP
             WHERE APP_NO = :a
        """, {"a": app_no})
        app_row = cur.fetchone()
        if not app_row:
            cur.close()
            return redirect_err("/staff/xt", "APP_NO not in your VPD scope")

        cmnd = app_row[1]
        passport_no = app_row[5]

        cur.execute("""
            SELECT CMND, FULL_NAME, GENDER, PERMANENT_ADDRESS, DISTRICT_CODE
              FROM ADMIN.RESIDENT_PROFILE
             WHERE CMND = :c
        """, {"c": cmnd})
        res_row = cur.fetchone()

        cur.execute("""
            SELECT PASSPORT_NO, OWNER_CMND, ISSUE_DATE, EXPIRY_DATE
              FROM ADMIN.PASSPORT
             WHERE PASSPORT_NO = :p
        """, {"p": passport_no})
        pass_row = cur.fetchone()

        cur.close()

        def _norm(s):
            return (s or "").strip()

        diffs = {
            "full_name": (res_row is not None) and (_norm(app_row[2]).lower() != _norm(res_row[1]).lower()),
            "gender":    (res_row is not None) and (_norm(app_row[3]).upper() != _norm(res_row[2]).upper()),
            "address":   (res_row is not None) and (_norm(app_row[4]).lower() != _norm(res_row[3]).lower()),
            "passport":  (pass_row is not None) and (_norm(app_row[5]) != _norm(pass_row[0])),
        }

        return templates.TemplateResponse("xt_detail.html", {
            "request": request,
            "user": db_user,
            "app": app_row,
            "resident": res_row,
            "passport": pass_row,
            "diffs": diffs,
            "ok": qparam(request, "ok"),
            "err": qparam(request, "err"),
        })
    except Exception as e:
        return redirect_err("/staff/xt", f"Detail error: {str(e)[:180]}")
    finally:
        conn.close()


@router.post("/verify")
def xt_verify(
    request: Request,
    app_no: str = Form(...),
    result: str = Form(...),
    note: str = Form("")
):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "XT":
        return redirect_err("/login", "No permission")

    result = (result or "").upper().strip()
    if result not in {"PASS", "FAIL"}:
        return redirect_err("/staff/xt", "Invalid result")

    app_no = (app_no or "").strip()
    if not app_no:
        return redirect_err("/staff/xt", "Missing APP_NO")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:XT")

        cur = conn.cursor()

        # ✅ call stored procedure instead of direct UPDATE
        # ADMIN.PROC_XT_VERIFY(p_app_no, p_result, p_note)
        cur.callproc("ADMIN.PROC_XT_VERIFY", [app_no, result, note])

        conn.commit()
        cur.close()
        return redirect_ok("/staff/xt", f"Updated {app_no}")

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/staff/xt", f"Update failed: {str(e)[:180]}")
    finally:
        conn.close()
