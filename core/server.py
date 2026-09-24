"""Flask Web Application & Multithreaded Streaming Server."""
import io
import os
import sys
import queue
import re
import mimetypes
import logging
import threading
import zipfile
from datetime import datetime
from typing import Callable, Optional, Tuple
from flask import Flask, request, jsonify, render_template, send_file, Response, abort, stream_with_context, make_response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.serving import make_server

from core.storage import StorageManager
from core.network import get_network_interfaces, get_best_ip, generate_qr_base64
from core.thumbnail import ThumbnailGenerator

# Suppress standard werkzeug request logs to prevent console flooding
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Chunk size used when piping zip data to the HTTP response stream
_ZIP_CHUNK = 65536  # 64 KB


class _PipeWriter(io.RawIOBase):
    """A writeable file-like object that feeds chunks into a queue.
    Used so ZipFile can write into it while the HTTP response generator
    reads from the other end — enabling true streaming without a temp file.
    """
    def __init__(self, q: queue.Queue):
        self._q = q

    def write(self, b):
        self._q.put(bytes(b))
        return len(b)

    def close(self):
        self._q.put(None)  # sentinel → EOF
        super().close()


def stream_zip(target_path: str):
    """Generator that yields zip bytes for a file or directory tree.

    A background thread runs ZipFile.write() while this generator
    reads the produced bytes from a queue, yielding them to Flask's
    streaming response so the browser sees data immediately.
    """
    q: queue.Queue = queue.Queue(maxsize=16)
    writer = _PipeWriter(q)

    def _build():
        try:
            with zipfile.ZipFile(writer, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                if os.path.isdir(target_path):
                    for root, _dirs, files in os.walk(target_path):
                        for fname in files:
                            full = os.path.join(root, fname)
                            arc = os.path.relpath(full, target_path)
                            try:
                                zf.write(full, arc)
                            except (PermissionError, OSError):
                                continue  # skip unreadable files silently
                else:
                    zf.write(target_path, os.path.basename(target_path))
        except Exception:
            pass
        finally:
            writer.close()

    t = threading.Thread(target=_build, daemon=True)
    t.start()

    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield chunk

    t.join()


def create_app(storage_mgr: StorageManager, log_callback: Optional[Callable[[str], None]] = None) -> Flask:
    # When frozen by PyInstaller, bundled read-only assets live in sys._MEIPASS.
    # In normal script mode they live two levels above this file (the project root).
    _bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_dir = os.path.join(_bundle_root, "web", "templates")
    static_dir   = os.path.join(_bundle_root, "web", "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    CORS(app)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50 GB max file upload
    # Never let browsers cache JS/CSS: a stale app.js would break new features
    # such as folder upload until the user hard-refreshes.
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


    thumb_gen = ThumbnailGenerator(os.path.join(storage_mgr.base_dir, ".cache", "thumbnails"))

    def record_activity(message: str, client_ip: Optional[str] = None):
        """Sends log messages to GUI or stdout."""
        ip = client_ip or (request.remote_addr if request else "Local")
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] [{ip}] {message}"
        if log_callback:
            log_callback(log_line)
        else:
            print(log_line)

    def is_authorized(root_id: str) -> bool:
        """Verifies if request has valid access for protected vault."""
        if root_id != "vault":
            return True
        token = request.headers.get("X-Vault-Token") or request.cookies.get("vault_token") or request.args.get("token")
        return storage_mgr.is_vault_token_valid(token)

    @app.route("/")
    def index():
        resp = make_response(render_template("index.html"))
        # Never cache the shell page: it must always serve the newest app.js/CSS
        # so devices pick up upload/folder UI changes immediately.
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/status")
    def api_status():
        host_ip = request.host.split(":")[0]
        port = storage_mgr.config.get("server_port", 5000)
        current_url = f"http://{get_best_ip()}:{port}"
        
        return jsonify({
            "status": "online",
            "server_name": storage_mgr.config.get("server_name", "Antigravity Share Hub"),
            "best_ip": get_best_ip(),
            "port": port,
            "interfaces": get_network_interfaces(),
            "qr_code": generate_qr_base64(current_url)
        })

    @app.route("/api/drives")
    def api_drives():
        token = request.headers.get("X-Vault-Token") or request.cookies.get("vault_token") or request.args.get("token")
        vault_unlocked = storage_mgr.is_vault_token_valid(token)
        
        roots = storage_mgr.get_all_storage_roots()
        for r in roots:
            if r["id"] == "vault":
                r["is_unlocked"] = vault_unlocked
                
        return jsonify({"roots": roots})

    @app.route("/api/files")
    def api_files():
        root_id = request.args.get("root", "public")
        sub_path = request.args.get("path", "")

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Private Vault is locked. Enter password to unlock.", "is_locked": True}), 401

        result = storage_mgr.list_directory(root_id, sub_path)
        if result is None:
            return jsonify({"error": "Directory not found or inaccessible"}), 404

        record_activity(f"Browsing {root_id}/{sub_path or 'root'}")
        return jsonify(result)

    def _safe_relative_path(upload_rel: str) -> Optional[str]:
        """Normalizes a client-supplied relative path and rejects traversal.

        Returns a safe, OS-neutral relative path (e.g. ``my/folder/file.txt``)
        or ``None`` when the path attempts to escape the upload root.
        """
        if not upload_rel:
            return None
        raw = upload_rel.replace("\\", "/").strip("/")
        if not raw or raw in (".", "..") or raw.startswith("..") or "://" in raw or "\x00" in raw:
            return None
        norm = os.path.normpath(raw)
        if not norm or norm == "." or norm.startswith("..") or os.path.isabs(norm):
            return None
        return norm.replace("\\", "/")

    @app.route("/api/upload", methods=["POST"])
    def api_upload():
        root_id = request.form.get("root", "public")
        sub_path = request.form.get("path", "")

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Vault locked. Unauthorized upload."}), 401

        target_dir = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_dir or not os.path.isdir(target_dir):
            return jsonify({"error": "Invalid upload target directory"}), 400

        resolved = storage_mgr.resolve_root_path(root_id)
        if not resolved or resolved[2]: # read_only is True
            return jsonify({"error": "This storage location is set to Read-Only by the admin."}), 403

        if 'files' not in request.files and 'file' not in request.files:
            return jsonify({"error": "No files received"}), 400

        uploaded_files = request.files.getlist('files')
        if not uploaded_files:
            uploaded_files = [request.files.get('file')]

        # Parallel list of relative paths (one per uploaded file) honoring folder structure.
        # Fall back to relying on the filenames themselves when not supplied.
        rel_paths = request.form.getlist('rel_path') or request.form.getlist('paths')

        saved_names = []
        total_saved = 0

        for idx, f in enumerate(uploaded_files):
            if not f or not f.filename:
                continue

            supplied_rel_path = rel_paths[idx] if idx < len(rel_paths) else None
            if supplied_rel_path:
                # Client supplied an explicit relative path (folder upload / single
                # file with structure). Reject outright if it attempts traversal.
                rel_path = _safe_relative_path(supplied_rel_path)
                if rel_path is None:
                    record_activity(f"Blocked unsafe upload path: {supplied_rel_path!r}")
                    continue
            else:
                # No relative path supplied: rely on the plain filename only.
                rel_path = _safe_relative_path(os.path.basename(f.filename))
                if rel_path is None:
                    continue

            folder_part, filename = os.path.split(rel_path)

            filename = secure_filename(filename)
            if not filename:
                filename = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Create the nested folder structure inside the target directory
            dest_dir = os.path.join(target_dir, folder_part) if folder_part else target_dir
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except (PermissionError, OSError):
                continue

            # Handle duplicate names gracefully at the leaf filename level
            dest_path = os.path.join(dest_dir, filename)
            base_n, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_dir, f"{base_n}_{counter}{ext}")
                counter += 1

            try:
                f.save(dest_path)
            except (PermissionError, OSError) as e:
                record_activity(f"Upload failed for '{rel_path or f.filename}': {e}")
                continue

            f_size = storage_mgr.format_size(os.path.getsize(dest_path))
            saved_rel = os.path.relpath(dest_path, target_dir).replace("\\", "/")
            saved_names.append(saved_rel)
            total_saved += 1
            record_activity(f"Uploaded '{saved_rel}' ({f_size}) to {root_id}/{sub_path}")

        return jsonify({
            "message": f"Successfully uploaded {total_saved} file(s)",
            "files": saved_names
        })

    @app.route("/api/download")
    def api_download():
        root_id = request.args.get("root", "public")
        sub_path = request.args.get("path", "")
        as_zip = request.args.get("zip", "false").lower() == "true"

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Private Vault is locked"}), 401

        target_path = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.exists(target_path):
            return jsonify({"error": "File or folder not found"}), 404

        if os.path.isdir(target_path) or as_zip:
            folder_name = os.path.basename(target_path.rstrip("/\\")) or root_id
            download_name = f"{folder_name}.zip"
            record_activity(f"Streaming ZIP download for '{folder_name}'")

            # Stream zip data directly to client — no temp file needed.
            # The browser receives the first bytes immediately and opens
            # the download dialog right away, even for very large folders.
            return Response(
                stream_with_context(stream_zip(target_path)),
                mimetype="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{download_name}"',
                    "X-Accel-Buffering": "no",   # disable nginx buffering if present
                    "Cache-Control": "no-cache",
                },
            )

        record_activity(f"Downloaded '{os.path.basename(target_path)}'")
        return send_file(target_path, as_attachment=True, download_name=os.path.basename(target_path))


    @app.route("/api/preview")
    def api_preview():
        root_id = request.args.get("root", "public")
        sub_path = request.args.get("path", "")

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Private Vault is locked"}), 401

        target_path = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.isfile(target_path):
            return jsonify({"error": "File not found"}), 404

        mime, _ = mimetypes.guess_type(target_path)
        if not mime:
            ext = os.path.splitext(target_path)[1].lower()
            if ext in {'.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.txt', '.log', '.csv'}:
                mime = "text/plain; charset=utf-8"
            else:
                mime = "application/octet-stream"

        # Werkzeug send_file supports HTTP 206 Partial Content (Range requests)
        # for smooth video/audio streaming on mobile and desktop
        return send_file(target_path, mimetype=mime, as_attachment=False, conditional=True)

    @app.route("/api/thumbnail")
    def api_thumbnail():
        root_id = request.args.get("root", "public")
        sub_path = request.args.get("path", "")

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Private Vault is locked"}), 401

        target_path = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.isfile(target_path):
            return jsonify({"error": "File not found"}), 404

        thumb_path = thumb_gen.generate_thumbnail(target_path)
        if thumb_path and os.path.exists(thumb_path):
            return send_file(thumb_path, mimetype="image/jpeg", as_attachment=False)

        # For formats the <img>/<picture> tags render natively, serve the original
        # file as the "thumbnail". Never hand a RAW HEIC/TIFF to the browser.
        ext = os.path.splitext(target_path)[1].lower()
        if ext in {'.svg', '.ico', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.avif', '.apng'}:
            return send_file(target_path)

        return jsonify({"error": "Thumbnail not available"}), 404

    @app.route("/api/auth/vault", methods=["POST"])
    def api_auth_vault():
        data = request.get_json(silent=True) or {}
        password = data.get("password", "")

        success, token = storage_mgr.verify_vault_password(password)
        if success:
            record_activity("Private Vault unlocked successfully")
            resp = jsonify({"success": True, "token": token, "message": "Vault unlocked"})
            return resp
        else:
            record_activity("Failed vault unlock attempt (Incorrect password)")
            return jsonify({"success": False, "error": "Incorrect Vault password"}), 403

    @app.route("/api/auth/lock", methods=["POST"])
    def api_auth_lock():
        token = request.headers.get("X-Vault-Token") or request.cookies.get("vault_token")
        storage_mgr.revoke_vault_token(token)
        record_activity("Private Vault locked")
        resp = jsonify({"success": True, "message": "Vault locked"})
        resp.delete_cookie("vault_token")
        return resp

    @app.route("/api/mkdir", methods=["POST"])
    def api_mkdir():
        data = request.get_json(silent=True) or {}
        root_id = data.get("root", "public")
        sub_path = data.get("path", "")
        folder_name = secure_filename(data.get("name", "").strip())

        if not folder_name:
            return jsonify({"error": "Folder name is required"}), 400

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Vault is locked"}), 401

        resolved = storage_mgr.resolve_root_path(root_id)
        if not resolved or resolved[2]:
            return jsonify({"error": "Target location is Read-Only"}), 403

        target_parent = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_parent or not os.path.isdir(target_parent):
            return jsonify({"error": "Invalid parent path"}), 400

        new_folder_path = os.path.join(target_parent, folder_name)
        if os.path.exists(new_folder_path):
            return jsonify({"error": "Folder already exists"}), 400

        os.makedirs(new_folder_path, exist_ok=True)
        record_activity(f"Created folder '{folder_name}' in {root_id}/{sub_path}")
        return jsonify({"success": True, "message": f"Folder '{folder_name}' created"})

    @app.route("/api/delete", methods=["POST"])
    def api_delete():
        data = request.get_json(silent=True) or {}
        root_id = data.get("root", "public")
        sub_path = data.get("path", "")

        if not sub_path:
            return jsonify({"error": "Cannot delete root directory"}), 400

        if root_id == "vault" and not is_authorized(root_id):
            return jsonify({"error": "Vault is locked"}), 401

        resolved = storage_mgr.resolve_root_path(root_id)
        if not resolved or resolved[2]:
            return jsonify({"error": "Target location is Read-Only"}), 403

        target_path = storage_mgr.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.exists(target_path):
            return jsonify({"error": "Item not found"}), 404

        try:
            if os.path.isdir(target_path):
                import shutil
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
            record_activity(f"Deleted '{os.path.basename(target_path)}' from {root_id}")
            return jsonify({"success": True, "message": "Item deleted successfully"})
        except Exception as e:
            return jsonify({"error": f"Failed to delete: {str(e)}"}), 500

    @app.route("/api/copy", methods=["POST"])
    def api_copy():
        data = request.get_json(silent=True) or {}
        src_root = data.get("src_root", "public")
        src_path = data.get("src_path", "")
        dest_root = data.get("dest_root", "")
        dest_path = data.get("dest_path", "")

        if not dest_root:
            return jsonify({"error": "Destination drive/root is required"}), 400

        if src_root == "vault" and not is_authorized(src_root):
            return jsonify({"error": "Source vault is locked"}), 401
        if dest_root == "vault" and not is_authorized(dest_root):
            return jsonify({"error": "Destination vault is locked"}), 401

        dest_resolved = storage_mgr.resolve_root_path(dest_root)
        if not dest_resolved:
            return jsonify({"error": "Destination drive not found or unplugged"}), 404
        if dest_resolved[2]:  # is_read_only is True
            return jsonify({"error": "Destination drive is set to Read-Only by admin"}), 403

        src_full = storage_mgr.get_safe_path(src_root, src_path)
        dest_parent = storage_mgr.get_safe_path(dest_root, dest_path)
        if not src_full or not os.path.exists(src_full):
            return jsonify({"error": "Source item not found"}), 404
        if not dest_parent or not os.path.isdir(dest_parent):
            return jsonify({"error": "Destination directory not found"}), 400

        import shutil
        filename = os.path.basename(src_full)
        dest_file = os.path.join(dest_parent, filename)
        
        # Handle duplicate filenames
        base_n, ext = os.path.splitext(filename)
        cnt = 1
        while os.path.exists(dest_file):
            dest_file = os.path.join(dest_parent, f"{base_n}_{cnt}{ext}")
            cnt += 1

        try:
            if os.path.isdir(src_full):
                shutil.copytree(src_full, dest_file)
            else:
                shutil.copy2(src_full, dest_file)
            f_size = storage_mgr.format_size(os.path.getsize(dest_file)) if os.path.isfile(dest_file) else "Folder"
            record_activity(f"Copied '{filename}' ({f_size}) from {src_root} to {dest_root}")
            return jsonify({
                "success": True,
                "message": f"Successfully copied '{filename}' to {dest_root}",
                "dest_file": os.path.basename(dest_file)
            })
        except Exception as e:
            return jsonify({"error": f"Failed to copy file: {str(e)}"}), 500

    return app

class ServerController:
    """Manages the background HTTP server thread and lifecycle."""

    def __init__(self, storage_mgr: StorageManager, log_callback: Optional[Callable[[str], None]] = None):
        self.storage_mgr = storage_mgr
        self.log_callback = log_callback
        self.app = create_app(storage_mgr, log_callback)
        self.server = None
        self.server_thread = None
        self.is_active = False
        self.host = "0.0.0.0"
        self.port = 5000

    def start(self, port: int = 5000, host: str = "0.0.0.0") -> Tuple[bool, str]:
        """Starts the server on the specified port and host."""
        if self.is_active:
            return True, f"Server is already running on port {self.port}"

        self.host = host
        self.port = int(port)
        self.storage_mgr.config["server_port"] = self.port
        self.storage_mgr.save_config()

        try:
            self.server = make_server(self.host, self.port, self.app, threaded=True)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.is_active = True
            
            lan_ip = get_best_ip()
            url = f"http://{lan_ip}:{self.port}"
            msg = f"Server started successfully at {url}"
            if self.log_callback:
                self.log_callback(f"[INFO] {msg}")
            return True, url
        except Exception as e:
            self.is_active = False
            return False, f"Failed to start server: {str(e)}"

    def stop(self) -> Tuple[bool, str]:
        """Shuts down the running server."""
        if not self.is_active or not self.server:
            return True, "Server is not running"

        try:
            self.server.shutdown()
            self.is_active = False
            if self.log_callback:
                self.log_callback("[INFO] Server stopped by administrator.")
            return True, "Server stopped successfully"
        except Exception as e:
            return False, f"Error stopping server: {str(e)}"

    def get_url(self, selected_ip: Optional[str] = None) -> str:
        ip = selected_ip or get_best_ip()
        return f"http://{ip}:{self.port}"
