# Liquid Commander

Liquid Commander is a fast, visually rich local file manager built with FastAPI and Jinja2. The single-page interface in `templates/index.html` mirrors the feel of a desktop command center while the FastAPI-powered `server.py` (root directory) exposes navigation, file metadata, and filesystem actions through REST endpoints.

## Highlights
- **Desktop-style explorer** powered by `templates/index.html` with a glassmorphism layout, breadcrumbs, batch actions, and optional trash view.
- **Filesystem insight** from `server.py` via `get_file_info`, disk-usage stats, guarded navigation (home/root defaults), and breadcrumb generation.
- **Full CRUD stack**: copy, move, rename, delete (with trash), zip/unzip, upload/download, and folder/file creation endpoints that operate on absolute paths and route responses through FastAPI forms and redirects.
- **Preview guardrails** that only serve text, PDF, image, or other whitelisted MIME types before handing data to the browser.
- **Trash protection** with `.liquid_commander_trash` storage, safe deletes, and a dedicated `/trash/empty` cleanup that respects the `PROTECTED_PATHS` set (`server.py`, templates, the trash folder itself, and the filesystem root).

## Requirements
- Python `3.10+` (or compatible) environment
- Dependencies listed in `requirements.txt`

## Setup
1. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the app
Start the server from the repo root:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```
Open `http://localhost:8000` to explore the UI, or use the REST endpoints directly.

## API endpoints
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Renders the main explorer UI with folders/files, disk stats, and breadcrumbs. |
| `/api/list` | GET | Returns JSON listing folders/files, breadcrumbs, and disk usage for a path. |
| `/copy`, `/move`, `/zip`, `/unzip`, `/create-folder`, `/create-file`, `/rename`, `/upload` | POST | Forms-based handlers for filesystem actions. |
| `/download/{filepath}` | GET | Streams a file download (directories are blocked). |
| `/api/batch-delete`, `/api/batch-copy`, `/api/batch-move` | POST | Bulk operations that leverage trash-safe deletes and standard copy/move logic. |
| `/trash/empty` | POST | Clears `.liquid_commander_trash` while skipping `PROTECTED_PATHS`. |

## Security considerations
1. `PROTECTED_PATHS` (see `server.py`) prevents deletion of the application directory, templates, and the trash folder itself.
2. Trash mode keeps deleted data in `~/.liquid_commander_trash` until `/trash/empty` is invoked, so accidental deletes can be recovered.
3. Preview endpoint whitelists MIME types to avoid leaking binary blobs that browsers can’t display safely.

## Customization
- Modify `templates/index.html` to change the UI theme, action layout, or additional controls.
- Extend `server.py` helper functions to add throttling, logging, or authentication if this will be exposed beyond a trusted local environment.

## Next steps
1. Add user authentication/authorization if this will ever be served beyond a secure LAN.
2. Connect a persistent config store (JSON/SQLite) to remember favorite folders or view filters.
3. Implement WebSocket notifications for long-running operations like copies/zips if you want real-time progress.
