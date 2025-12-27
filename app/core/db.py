import oracledb
from .config import ORACLE_DSN

oracledb.defaults.fetch_lobs = False

def make_conn(user: str, password: str):
    return oracledb.connect(user=user, password=password, dsn=ORACLE_DSN)
