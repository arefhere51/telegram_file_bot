import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from config import settings
from database import (
    init_db,
    get_file,
    list_files,
    count_files,
    total_size,
    increment_download,
    soft_delete,
    hard_delete,
)

init_db()

app = FastAPI(title="Telegram File Bot Panel", docs_url=None, redoc_url=None)

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
security = HTTPBasic()


def require_panel_auth(credentials: HTTPBasicCredentials = Depends(security)):
    if not settings.PANEL_USERNAME or not settings.PANEL_PASSWORD:
        raise HTTPException(status_code=503, detail="Panel login is not configured")
    user_ok = secrets.compare_digest(credentials.username.encode(), settings.PANEL_USERNAME.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), settings.PANEL_PASSWORD.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})



def human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def format_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _auth: None = Depends(require_panel_auth)):
    files = list_files(limit=200)
    stats = {
        "count": count_files(),
        "total_size": human_size(total_size()),
        "total_size_raw": total_size(),
    }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "files": files,
            "stats": stats,
            "human_size": human_size,
            "format_time": format_time,
            "public_base": settings.PUBLIC_BASE_URL.rstrip("/"),
        },
    )


@app.get("/d/{file_id}")
async def download_file(file_id: str):
    info = get_file(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    stored_name = info["stored_name"]
    if Path(stored_name).name != stored_name:
        raise HTTPException(status_code=400, detail="Invalid stored file name")
    path = settings.files_path / stored_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on disk")

    increment_download(file_id)

    return FileResponse(
        path=path,
        filename=info["original_name"],
        media_type=info.get("mime_type") or "application/octet-stream",
    )


@app.post("/delete/{file_id}")
async def delete_file(file_id: str, request: Request, _auth: None = Depends(require_panel_auth)):
    origin = request.headers.get("origin")
    expected_origin = settings.PUBLIC_BASE_URL.rstrip("/")
    if not origin or origin.rstrip("/") != expected_origin:
        raise HTTPException(status_code=403, detail="Cross-origin request blocked")
    info = get_file(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    stored = hard_delete(file_id)
    if stored:
        if Path(stored).name != stored:
            raise HTTPException(status_code=400, detail="Invalid stored file name")
        path = settings.files_path / stored
        if path.exists() and path.is_file():
            try:
                path.unlink()
            except Exception:
                pass

    return RedirectResponse(url="/", status_code=303)


@app.get("/health")
async def health():
    return {"status": "ok", "files": count_files()}
