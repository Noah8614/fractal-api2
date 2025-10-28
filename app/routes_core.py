import os
from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
INDEX_PATH = os.path.join(TEMPLATES_DIR, "index.html")

@router.get("/")
async def index():
    if not os.path.exists(INDEX_PATH):
        return HTMLResponse("<h3>index.html not found in templates directory</h3>", status_code=404)
    return FileResponse(INDEX_PATH)