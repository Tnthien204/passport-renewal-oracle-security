from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_302_FOUND

from app.web.templates import templates
from app.utils.session import require_login, qparam, redirect_err, staff_conn

router = APIRouter(prefix="/admin")

MAX_ROWS = 200


def _ensure_admin(request: Request):
    r = require_login(request)
    if r:
        return r
    if request.session.get("role") != "ADMIN":
        return redirect_err("/login", "No permission")
    return None


def _redirect_ok(url: str):
    return RedirectResponse(url=url, status_code=HTTP_302_FOUND)


@router.get("", response_class=HTMLResponse)
def admin_home(request: Request, r_q: str = "", p_q: str = ""):
    deny = _ensure_admin(request)
    if deny:
        return deny

    conn = staff_conn(request)
    try:
        cur = conn.cursor()

        # --- RESIDENT_PROFILE list ---
        if r_q:
            cur.execute(f"""
                SELECT CMND, FULL_NAME, GENDER, PERMANENT_ADDRESS, DISTRICT_CODE
                  FROM ADMIN.RESIDENT_PROFILE
                 WHERE CMND LIKE :q
                    OR UPPER(FULL_NAME) LIKE UPPER(:q)
                 ORDER BY CMND
                 FETCH FIRST {MAX_ROWS} ROWS ONLY
            """, {"q": f"%{r_q.strip()}%"})
        else:
            cur.execute(f"""
                SELECT CMND, FULL_NAME, GENDER, PERMANENT_ADDRESS, DISTRICT_CODE
                  FROM ADMIN.RESIDENT_PROFILE
                 ORDER BY CMND
                 FETCH FIRST {MAX_ROWS} ROWS ONLY
            """)
        residents = cur.fetchall()

        # --- PASSPORT list ---
        if p_q:
            cur.execute(f"""
                SELECT PASSPORT_NO, OWNER_CMND, ISSUE_DATE, EXPIRY_DATE
                  FROM ADMIN.PASSPORT
                 WHERE PASSPORT_NO LIKE :q
                    OR OWNER_CMND LIKE :q
                 ORDER BY PASSPORT_NO
                 FETCH FIRST {MAX_ROWS} ROWS ONLY
            """, {"q": f"%{p_q.strip()}%"})
        else:
            cur.execute(f"""
                SELECT PASSPORT_NO, OWNER_CMND, ISSUE_DATE, EXPIRY_DATE
                  FROM ADMIN.PASSPORT
                 ORDER BY PASSPORT_NO
                 FETCH FIRST {MAX_ROWS} ROWS ONLY
            """)
        passports = cur.fetchall()

        cur.close()

        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": request.session.get("db_user"),
            "ok": qparam(request, "ok"),
            "err": qparam(request, "err"),
            "r_q": r_q,
            "p_q": p_q,
            "residents": residents,
            "passports": passports,
            "max_rows": MAX_ROWS,
        })
    except Exception as e:
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": request.session.get("db_user"),
            "ok": "",
            "err": f"DB error: {str(e)[:200]}",
            "r_q": r_q,
            "p_q": p_q,
            "residents": [],
            "passports": [],
            "max_rows": MAX_ROWS,
        })
    finally:
        conn.close()


@router.post("/resident", response_class=HTMLResponse)
def admin_add_resident(
    request: Request,
    cmnd: str = Form(...),
    full_name: str = Form(...),
    gender: str = Form(...),
    permanent_address: str = Form(...),
    district_code: str = Form(...),
):
    deny = _ensure_admin(request)
    if deny:
        return deny

    cmnd = cmnd.strip()
    full_name = full_name.strip()
    gender = gender.strip().upper()
    permanent_address = permanent_address.strip()
    district_code = district_code.strip().upper()

    if gender not in {"M", "F", "O"}:
        return redirect_err("/admin", "Gender must be M/F/O")
    if not district_code.startswith("Q"):
        return redirect_err("/admin", "DISTRICT_CODE must look like Q1..Q12")

    conn = staff_conn(request)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ADMIN.RESIDENT_PROFILE
              (CMND, FULL_NAME, GENDER, PERMANENT_ADDRESS, DISTRICT_CODE)
            VALUES
              (:cmnd, :full_name, :gender, :addr, :district)
        """, {
            "cmnd": cmnd,
            "full_name": full_name,
            "gender": gender,
            "addr": permanent_address,
            "district": district_code,
        })
        conn.commit()
        cur.close()
        return _redirect_ok("/admin?ok=Resident+inserted")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/admin", f"DB error: {str(e)[:200]}")
    finally:
        conn.close()


@router.post("/passport", response_class=HTMLResponse)
def admin_add_passport(
    request: Request,
    passport_no: str = Form(...),
    owner_cmnd: str = Form(...),
    issue_date: str = Form(...),   # yyyy-mm-dd
    expiry_date: str = Form(...),  # yyyy-mm-dd
):
    deny = _ensure_admin(request)
    if deny:
        return deny

    passport_no = passport_no.strip()
    owner_cmnd = owner_cmnd.strip()
    issue_date = issue_date.strip()
    expiry_date = expiry_date.strip()

    if not passport_no:
        return redirect_err("/admin", "PASSPORT_NO is required")
    if not owner_cmnd:
        return redirect_err("/admin", "OWNER_CMND is required")

    conn = staff_conn(request)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ADMIN.PASSPORT
              (PASSPORT_NO, OWNER_CMND, ISSUE_DATE, EXPIRY_DATE)
            VALUES
              (:pp, :cmnd, TO_DATE(:issue,'YYYY-MM-DD'), TO_DATE(:exp,'YYYY-MM-DD'))
        """, {
            "pp": passport_no,
            "cmnd": owner_cmnd,
            "issue": issue_date,
            "exp": expiry_date,
        })
        conn.commit()
        cur.close()
        return _redirect_ok("/admin?ok=Passport+inserted")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return redirect_err("/admin", f"DB error: {str(e)[:200]}")
    finally:
        conn.close()
