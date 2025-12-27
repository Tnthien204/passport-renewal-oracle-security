from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.web.templates import templates
from app.utils.session import (
    require_login,
    qparam,
    redirect_err,
    staff_conn,
    set_client_identifier,  # ✅ NEW
)

router = APIRouter(prefix="/staff/gs")


@router.get("", response_class=HTMLResponse)
def gs_logs(request: Request, q: str = ""):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") not in {"GS"}:
        return redirect_err("/login", "No permission")

    conn = staff_conn(request)
    try:
        # ✅ NEW: set client identifier for audit/logging
        db_user = request.session.get("db_user", "?")
        staff_username = request.session.get("staff_username", "?")
        set_client_identifier(conn, f"STAFF:{staff_username}|DB:{db_user}|ROLE:GS")

        cur = conn.cursor()
        if q:
            cur.execute(
                """
                SELECT LOG_AT, APP_NO, STEP_NAME, ACTION, ACTOR, NOTE
                  FROM ADMIN.PROCESS_LOG
                 WHERE APP_NO LIKE :q
                 ORDER BY LOG_AT DESC
                 FETCH FIRST 300 ROWS ONLY
                """,
                {"q": f"%{q}%"},
            )
        else:
            cur.execute(
                """
                SELECT LOG_AT, APP_NO, STEP_NAME, ACTION, ACTOR, NOTE
                  FROM ADMIN.PROCESS_LOG
                 ORDER BY LOG_AT DESC
                 FETCH FIRST 300 ROWS ONLY
                """
            )
        rows = cur.fetchall()
        cur.close()

        return templates.TemplateResponse(
            "gs_logs.html",
            {
                "request": request,
                "rows": rows,
                "user": db_user,
                "q": q,
                "ok": qparam(request, "ok"),
                "err": qparam(request, "err"),
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "gs_logs.html",
            {
                "request": request,
                "rows": [],
                "user": request.session.get("db_user"),
                "q": q,
                "ok": "",
                "err": f"DB error: {str(e)[:200]}",
            },
        )
    finally:
        conn.close()
