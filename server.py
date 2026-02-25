import os
import shutil
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
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

TRASH_DIR = Path.home() / ".liquid_commander_trash"
TRASH_DIR.mkdir(parents=True, exist_ok=True)

PROTECTED_PATHS = {
    BASE_DIR,
    SERVER_DIR,
    SERVER_DIR / "server.py",
    SERVER_DIR / "templates",
    TRASH_DIR
}

def ensure_trash_dir():
    TRASH_DIR.mkdir(parents=True, exist_ok=True)

def is_protected_path(path: Path):
    try:
        resolved = path.resolve()
    except Exception:
        return False
    return resolved in PROTECTED_PATHS

def is_in_trash(path: Path):
    try:
        resolved = path.resolve()
    except Exception:
        return False
    return resolved == TRASH_DIR or TRASH_DIR in resolved.parents

def move_to_trash(target: Path):
    ensure_trash_dir()
    try:
        resolved = target.resolve()
    except Exception:
        return False
    if not resolved.exists():
        return False

    dest = TRASH_DIR / resolved.name
    if dest.exists():
        suffix = datetime.now().strftime("%Y%m%d%H%M%S")
        dest = TRASH_DIR / f"{resolved.stem}_{suffix}{resolved.suffix}"

    shutil.move(str(resolved), str(dest))
    return True

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
                    info["size_bytes"] = stats.st_size
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

    if path:
        path = unquote(path)
    else:
        path = str(Path.home())
    
    target_dir = Path(path).resolve()
    
    if target_dir.exists() and not target_dir.is_dir():
        return RedirectResponse(url=f"/?path={quote(str(target_dir.parent))}")
        
    if not target_dir.exists():
        return RedirectResponse(url=f"/?path={home_path}")

    # Get disk usage
    usage = shutil.disk_usage(target_dir)
    disk_info = {
        "total": f"{usage.total / (1024**3):.1f} GB",
        "used": f"{usage.used / (1024**3):.1f} GB",
        "free": f"{usage.free / (1024**3):.1f} GB",
        "percent": (usage.used / usage.total) * 100
    }

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
        "trash_path": quote(str(TRASH_DIR)),
        "trash_path_raw": str(TRASH_DIR),
        "search_query": search,
        "mode": "normal",
        "breadcrumbs": parts,
        "disk_info": disk_info
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
    
    # Get disk usage
    usage = shutil.disk_usage(target_dir)
    disk_info = {
        "total": f"{usage.total / (1024**3):.1f} GB",
        "used": f"{usage.used / (1024**3):.1f} GB",
        "free": f"{usage.free / (1024**3):.1f} GB",
        "percent": (usage.used / usage.total) * 100
    }

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
        "breadcrumbs": parts,
        "disk_info": disk_info
    }

@app.post("/copy")
async def copy_item(path: str = Form(...), item_name: str = Form(...), dest_path: str = Form(...)):
    src = Path(unquote(path)) / item_name
    dest = Path(unquote(dest_path)) / item_name
    try:
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}

@app.post("/move")
async def move_item(path: str = Form(...), item_name: str = Form(...), dest_path: str = Form(...)):
    src = Path(unquote(path)) / item_name
    dest = Path(unquote(dest_path)) / item_name
    try:
        shutil.move(str(src), str(dest))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}

@app.post("/zip")
async def zip_item(path: str = Form(...), item_name: str = Form(...)):
    src = Path(unquote(path)) / item_name
    zip_path = src.with_suffix('.zip')
    try:
        if src.is_dir():
            shutil.make_archive(str(src), 'zip', src)
        else:
            import zipfile
            with zipfile.ZipFile(str(zip_path), 'w') as zipf:
                zipf.write(src, arcname=src.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}

@app.post("/unzip")
async def unzip_item(path: str = Form(...), item_name: str = Form(...)):
    src = Path(unquote(path)) / item_name
    dest = src.parent / src.stem
    try:
        shutil.unpack_archive(src, dest)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success"}

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
async def create_folder(path: str = Form(...), name: str = Form(...)):
    target_dir = Path(unquote(path)) / name
    try:
        target_dir.mkdir(exist_ok=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/?path={path}", status_code=303)

@app.post("/create-file")
async def create_file(path: str = Form(...), name: str = Form(...)):
    target_file = Path(unquote(path)) / name
    try:
        target_file.touch(exist_ok=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/?path={path}", status_code=303)

@app.post("/rename")
async def rename_item(path: str = Form(...), old_name: str = Form(...), new_name: str = Form(...)):
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

@app.post("/api/batch-delete")
async def batch_delete(path: str = Form(...), item_names: str = Form(...)):
    parent_dir = Path(unquote(path)).resolve()
    names = item_names.split(',')
    for name in names:
        target = parent_dir / name
        if not target.exists() or is_protected_path(target):
            continue
        try:
            if is_in_trash(target):
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            else:
                move_to_trash(target)
        except Exception:
            continue
    return {"status": "success"}

@app.post("/trash/empty")
async def empty_trash():
    ensure_trash_dir()
    for child in list(TRASH_DIR.iterdir()):
        if is_protected_path(child):
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except Exception:
            continue
    return {"status": "success"}

@app.post("/api/batch-copy")
async def batch_copy(path: str = Form(...), item_names: str = Form(...), dest_path: str = Form(...)):
    src_dir = Path(unquote(path)).resolve()
    dst_dir = Path(unquote(dest_path)).resolve()
    names = item_names.split(',')
    for name in names:
        src = src_dir / name
        dst = dst_dir / name
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            continue
    return {"status": "success"}

@app.post("/api/batch-move")
async def batch_move(path: str = Form(...), item_names: str = Form(...), dest_path: str = Form(...)):
    src_dir = Path(unquote(path)).resolve()
    dst_dir = Path(unquote(dest_path)).resolve()
    names = item_names.split(',')
    for name in names:
        src = src_dir / name
        dst = dst_dir / name
        try:
            shutil.move(str(src), str(dst))
        except Exception as e:
            continue
    return {"status": "success"}

@app.get("/delete/{filepath:path}")
async def delete_file(filepath: str):
    decoded_path = unquote(filepath)
    file_path = Path("/" + decoded_path.lstrip("/")).resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404)
    
    if is_protected_path(file_path):
        raise HTTPException(status_code=403, detail="Cannot delete critical files")

    parent_path = str(file_path.parent)
    if is_in_trash(file_path):
        if file_path.is_dir():
            shutil.rmtree(file_path)
        else:
            file_path.unlink()
    else:
        if not move_to_trash(file_path):
            raise HTTPException(status_code=400, detail="Failed to move item to Trash")
    return RedirectResponse(url=f"/?path={quote(parent_path)}", status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
