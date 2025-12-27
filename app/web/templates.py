from pathlib import Path
from fastapi.templating import Jinja2Templates

# tuyệt đối để chạy ở đâu cũng đúng
APP_DIR = Path(__file__).resolve().parents[1]  # .../app
TEMPLATES_DIR = APP_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
