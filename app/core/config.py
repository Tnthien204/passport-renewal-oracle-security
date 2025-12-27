import os
from dotenv import load_dotenv

load_dotenv()

ORACLE_DSN = os.getenv("ORACLE_DSN")
ONLINE_APP_USER = os.getenv("ONLINE_APP_USER")
ONLINE_APP_PASS = os.getenv("ONLINE_APP_PASS")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret")
