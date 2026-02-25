import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from datetime import datetime
import mimetypes
from urllib.parse import quote, unquote
import getpass
import platform
import socket

app = FastAPI()

# Configuration: Serve files from the root of the filesystem
BASE_DIR = Path("/").resolve()
SERVER_DIR = Path(__file__).parent.resolve()

templates = Jinja2Templates(directory=str(SERVER_DIR / "templates"))

def get_file_info(current_dir: Path, search_query: str = "", show_hidden: bool = False):
    folders = []
    files = []
    try:
        items = sorted(list(current_dir.iterdir()), key=lambda x: x.name.lower())
        for path in items:
            if path == SERVER_DIR / 'venv' or path == SERVER_DIR / '__pycache__':
                continue
            
            # Filter hidden files if requested
            if not show_hidden and path.name.startswith('.'):
                continue
            
            if search_query and search_query.lower() not in path.name.lower():
                continue

            try:
                stats = path.stat()
                mtime = datetime.fromtimestamp(stats.st_mtime).strftime('%b %d, %Y')
                safe_path = quote(str(path.resolve()))
                
                info = {
                    "name": path.name,
                    "rel_path": str(path.resolve()),
                    "safe_path": safe_path,
                    "mtime": mtime,
                    "is_dir": path.is_dir()
                }

                if path.is_dir():
                    try:
                        info["item_count"] = sum(1 for _ in path.iterdir() if not _.name.startswith('.'))
                    except:
                        info["item_count"] = 0
                    folders.append(info)
                else:
                    mime_type, _ = mimetypes.guess_type(path)
                    info["size"] = f"{stats.st_size / (1024*1024):.2f} MB"
                    info["ext"] = path.suffix.lower().lstrip('.')
                    info["mime"] = mime_type or "application/octet-stream"
                    
                    if info["mime"].startswith("image/"): info["type"] = "image"
                    elif info["mime"].startswith("video/"): info["type"] = "video"
                    elif info["mime"].startswith("audio/"): info["type"] = "audio"
                    elif info["ext"] in ["pdf"]: info["type"] = "pdf"
                    elif info["ext"] in ["zip", "rar", "7z", "tar", "gz"]: info["type"] = "archive"
                    elif info["ext"] in ["py", "js", "html", "css", "json", "md", "txt", "sh"]: info["type"] = "code"
                    else: info["type"] = "file"
                    
                    files.append(info)
            except Exception:
                continue
    except Exception:
        pass
            
    return {"folders": folders, "files": files}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, path: str = None, search: str = "", mode: str = "normal"):
    device_name = socket.gethostname() or platform.node() or "Local Disk"
    user_name = getpass.getuser().capitalize()
    home_path = quote(str(Path.home()))
    root_path = quote("/")

    if mode == "recents":
        recents = []
        try:
            home = Path.home()
            scan_paths = [home, home / "Downloads", home / "Documents", home / "Desktop"]
            for p in scan_paths:
                if p.exists():
                    for item in p.iterdir():
                        if item.is_file() and not item.name.startswith('.'):
                            stats = item.stat()
                            recents.append({
                                "name": item.name,
                                "safe_path": quote(str(item.resolve())),
                                "mtime": datetime.fromtimestamp(stats.st_mtime).strftime('%b %d, %Y'),
                                "size": f"{stats.st_size / (1024*1024):.2f} MB",
                                "type": "file", 
                                "is_dir": False,
                                "raw_mtime": stats.st_mtime
                            })
            recents = sorted(recents, key=lambda x: x["raw_mtime"], reverse=True)[:30]
        except:
            pass
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "folders": [],
            "files": recents,
            "current_name": "Recents",
            "current_path": "Recents",
            "safe_current_path": "",
            "user_name": user_name,
            "device_name": device_name,
            "home_path": home_path,
            "root_path": root_path,
            "mode": "recents",
            "breadcrumbs": []
        })

    if path:
        path = unquote(path)
    else:
        path = str(Path.home())
    
    target_dir = Path(path).resolve()
    
    if target_dir.exists() and not target_dir.is_dir():
        return RedirectResponse(url=f"/?path={quote(str(target_dir.parent))}")
        
    if not target_dir.exists():
        return RedirectResponse(url=f"/?path={home_path}")

    data = get_file_info(target_dir, search)
    
    # Build breadcrumbs
    parts = []
    curr = target_dir
    while True:
        parts.insert(0, {"name": curr.name or "Root", "path": quote(str(curr))})
        if curr == curr.parent: break
        curr = curr.parent

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "folders": data["folders"],
        "files": data["files"],
        "current_path": str(target_dir),
        "safe_current_path": quote(str(target_dir)),
        "current_name": target_dir.name if target_dir.name else "Root",
        "user_name": user_name,
        "device_name": device_name,
        "home_path": home_path,
        "root_path": root_path,
        "search_query": search,
        "mode": "normal",
        "breadcrumbs": parts
    })

@app.get("/api/list")
async def api_list(path: str = None, search: str = "", show_hidden: bool = False):
    if not path or path == "undefined":
        path = str(Path.home())
    else:
        path = unquote(path)
    
    target_dir = Path(path).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        target_dir = Path.home()

    data = get_file_info(target_dir, search, show_hidden)
    
    parts = []
    curr = target_dir
    while True:
        parts.insert(0, {"name": curr.name or "Root", "path": str(curr)})
        if curr == curr.parent: break
        curr = curr.parent

    return {
        "name": target_dir.name or "Root",
        "path": str(target_dir),
        "safe_path": quote(str(target_dir)),
        "folders": data["folders"],
        "files": data["files"],
        "breadcrumbs": parts
    }

@app.get("/preview/{filepath:path}")
async def preview_file(filepath: str):
    file_path = Path("/" + filepath.lstrip("/")).resolve()
    if not file_path.exists() or file_path.is_dir():
        raise HTTPException(status_code=404)
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type and (mime_type.startswith("image/") or mime_type.startswith("text/") or mime_type == "application/pdf"):
        return FileResponse(file_path)
    
    if file_path.suffix in [".py", ".js", ".html", ".css", ".json", ".md", ".sh"]:
        return FileResponse(file_path, media_type="text/plain")
        
    raise HTTPException(status_code=400, detail="Preview not supported for this file type")

@app.post("/create-folder")
async def create_folder(path: str, name: str):
    target_dir = Path(unquote(path)) / name
    try:
        target_dir.mkdir(exist_ok=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/?path={path}", status_code=303)

@app.post("/create-file")
async def create_file(path: str, name: str):
    target_file = Path(unquote(path)) / name
    try:
        target_file.touch(exist_ok=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/?path={path}", status_code=303)

@app.post("/rename")
async def rename_item(path: str, old_name: str, new_name: str):
    base = Path(unquote(path))
    old_path = base / old_name
    new_path = base / new_name
    try:
        old_path.rename(new_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/?path={path}", status_code=303)

@app.post("/upload")
async def upload_file(path: str, file: UploadFile = File(...)):
    target_dir = Path(unquote(path)).resolve()
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory")
        
    file_path = target_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return RedirectResponse(url=f"/?path={quote(str(target_dir))}", status_code=303)

@app.get("/download/{filepath:path}")
async def download_file(filepath: str):
    file_path = Path("/" + filepath.lstrip("/")).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404)
    if file_path.is_dir():
        raise HTTPException(status_code=400, detail="Cannot download a directory")
    return FileResponse(path=file_path, filename=file_path.name)

@app.get("/delete/{filepath:path}")
async def delete_file(filepath: str):
    file_path = Path("/" + filepath.lstrip("/")).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404)
    
    if file_path == BASE_DIR or file_path == SERVER_DIR or file_path == SERVER_DIR / "server.py" or file_path == SERVER_DIR / "templates":
        raise HTTPException(status_code=403, detail="Cannot delete critical files")

    parent_path = str(file_path.parent)
    if file_path.is_dir():
        shutil.rmtree(file_path)
    else:
        file_path.unlink()
    return RedirectResponse(url=f"/?path={quote(parent_path)}", status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
