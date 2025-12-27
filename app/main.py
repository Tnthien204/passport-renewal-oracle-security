from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SESSION_SECRET
from app.routes.auth import router as auth_router
from app.routes.citizen import router as citizen_router
from app.routes.staff_home import router as staff_home_router
from app.routes.staff_xt import router as staff_xt_router
from app.routes.staff_xd import router as staff_xd_router
from app.routes.staff_lt import router as staff_lt_router
from app.routes.staff_gs import router as staff_gs_router
from app.routes.admin import router as admin_router
app = FastAPI(title="Passport Web (Oracle VPD + OLS + Realm)")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.include_router(auth_router)
app.include_router(citizen_router)
app.include_router(staff_home_router)
app.include_router(staff_xt_router)
app.include_router(staff_xd_router)
app.include_router(staff_lt_router)
app.include_router(staff_gs_router)
app.include_router(admin_router)