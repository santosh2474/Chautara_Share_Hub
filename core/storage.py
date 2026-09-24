"""Storage Manager for Public Shared Folder, Private Vault, and USB Drives."""
import os
import json
import hashlib
import secrets
import shutil
import zipfile
import mimetypes
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class StorageManager:
    """Manages files, permissions, and security across Public, Vault, and USB shares."""
    
    # Supported preview extensions
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico',
                  '.tiff', '.tif', '.heic', '.heif', '.avif', '.apng', '.jfif'}
    VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'}
    AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.aac', '.flac', '.m4a'}
    DOC_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.rtf'}
    CODE_EXTS = {'.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.sql', '.sh', '.bat', '.ps1', '.c', '.cpp', '.h', '.java', '.go', '.rs', '.php', '.md'}
    ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'}

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.config_path = os.path.join(self.base_dir, "server_config.json")
        self.storage_dir = os.path.join(self.base_dir, "Shared_Storage")
        self.public_dir = os.path.join(self.storage_dir, "Public")
        self.vault_dir = os.path.join(self.storage_dir, "Vault")
        
        # Active authenticated vault sessions {token: expiry_or_created}
        self.vault_sessions = set()
        
        # Config state
        self.config = {
            "vault_password_hash": self._hash_password("admin123"), # default master password
            "allow_public_upload": True,
            "allow_public_delete": False,
            "allow_vault_upload": True,
            "allow_vault_delete": True,
            "shared_usb_drives": {},  # {drive_key: {"mount": "E:\\", "label": "Sandisk", "read_only": False}}
            "server_port": 5000,
            "server_name": "Chautara Share Hub"
        }
        self.load_config()
        self._apply_storage_path_overrides()
        # Ensure the (possibly overridden) storage directories exist
        os.makedirs(self.public_dir, exist_ok=True)
        os.makedirs(self.vault_dir, exist_ok=True)

    def _apply_storage_path_overrides(self):
        """Honours optional public_storage_path / vault_storage_path config keys.

        These are written by the setup wizard (or manually) so the Public share
        can live anywhere on disk (e.g. D:\\School_Files) while config, vault and
        the app itself stay in the install directory.
        """
        pub = self.config.get("public_storage_path")
        if pub:
            self.public_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(str(pub))))
        vault = self.config.get("vault_storage_path")
        if vault:
            self.vault_dir = os.path.abspath(os.path.expandvars(os.path.expanduser(str(vault))))

    def _hash_password(self, password: str) -> str:
        """Computes SHA-256 hash with salt for secure storage."""
        salt = "antigravity_lan_vault_salt"
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def load_config(self):
        """Loads configuration from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        """Saves current configuration to JSON file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def set_vault_password(self, new_password: str):
        """Updates the vault master password and invalidates prior sessions."""
        self.config["vault_password_hash"] = self._hash_password(new_password)
        self.vault_sessions.clear()
        self.save_config()

    def verify_vault_password(self, password: str) -> Tuple[bool, Optional[str]]:
        """Verifies master password. If valid, generates and returns a session token."""
        entered_hash = self._hash_password(password)
        if secrets.compare_digest(entered_hash, self.config["vault_password_hash"]):
            token = secrets.token_urlsafe(32)
            self.vault_sessions.add(token)
            return True, token
        return False, None

    def is_vault_token_valid(self, token: Optional[str]) -> bool:
        """Validates an authenticated vault session token."""
        if not token:
            return False
        return token in self.vault_sessions

    def revoke_vault_token(self, token: Optional[str]):
        """Logs out / locks a session."""
        if token and token in self.vault_sessions:
            self.vault_sessions.remove(token)

    def set_usb_share(self, drive_mount: str, label: str, enabled: bool, read_only: bool = False):
        """Toggles sharing for an external USB drive."""
        key = drive_mount.replace(":", "").replace("\\", "").replace("/", "").lower()
        if not key:
            key = f"usb_{hash(drive_mount)}"
        
        if enabled:
            self.config["shared_usb_drives"][key] = {
                "mount": drive_mount,
                "label": label,
                "read_only": read_only
            }
        else:
            self.config["shared_usb_drives"].pop(key, None)
        self.save_config()

    def get_all_storage_roots(self) -> List[Dict]:
        """Returns list of accessible storage roots (Public, Vault, USB Drives)."""
        roots = [
            {
                "id": "public",
                "name": "Public Shared Folder",
                "type": "public",
                "description": "Accessible to everyone on network",
                "is_protected": False,
                "read_only": not self.config.get("allow_public_upload", True),
                "icon": "folder-shared"
            },
            {
                "id": "vault",
                "name": "Private Vault",
                "type": "vault",
                "description": "Password-protected admin folder",
                "is_protected": True,
                "read_only": not self.config.get("allow_vault_upload", True),
                "icon": "shield-lock"
            }
        ]

        # Add shared USB / External drives
        for key, info in self.config.get("shared_usb_drives", {}).items():
            if os.path.exists(info["mount"]):
                is_ro = info.get("read_only", False)
                roots.append({
                    "id": f"usb_{key}",
                    "name": f"USB: {info['label']} ({info['mount'].rstrip(chr(92))})",
                    "type": "usb",
                    "description": f"External drive ({'Read-only' if is_ro else 'Uploads Allowed'})",
                    "is_protected": False,
                    "read_only": is_ro,
                    "icon": "usb-drive"
                })

        return roots

    def resolve_root_path(self, root_id: str) -> Optional[Tuple[str, bool, bool]]:
        """
        Resolves root_id to (absolute_base_path, is_protected, is_read_only).
        Returns None if root_id is invalid or drive unplugged.
        """
        if root_id == "public":
            return self.public_dir, False, not self.config.get("allow_public_upload", True)
        elif root_id == "vault":
            return self.vault_dir, True, not self.config.get("allow_vault_upload", True)
        elif root_id.startswith("usb_"):
            usb_key = root_id[4:]
            usb_info = self.config.get("shared_usb_drives", {}).get(usb_key)
            if usb_info and os.path.exists(usb_info["mount"]):
                return os.path.abspath(usb_info["mount"]), False, usb_info.get("read_only", False)
        return None

    def get_safe_path(self, root_id: str, sub_path: str = "") -> Optional[str]:
        """
        Resolves a safe absolute path ensuring it does not escape root boundaries.
        Prevents path traversal vulnerabilities.
        """
        resolved = self.resolve_root_path(root_id)
        if not resolved:
            return None
        base_dir, _, _ = resolved

        # Sanitize sub_path
        clean_sub = os.path.normpath(sub_path.lstrip("/\\"))
        if clean_sub in ("", "."):
            target_path = base_dir
        else:
            target_path = os.path.abspath(os.path.join(base_dir, clean_sub))

        # Security check: Target must stay within base_dir
        try:
            common = os.path.commonpath([base_dir, target_path])
            if os.path.abspath(common) == os.path.abspath(base_dir):
                return target_path
        except (ValueError, OSError):
            return None
        return None

    def format_size(self, num_bytes: int) -> str:
        """Formats byte count into human-readable string."""
        if num_bytes is None or num_bytes < 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:3.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} PB"

    def categorize_file(self, filename: str) -> Tuple[str, bool]:
        """Determines category and whether file is in-browser previewable."""
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.IMAGE_EXTS:
            return "image", True
        elif ext in self.VIDEO_EXTS:
            return "video", True
        elif ext in self.AUDIO_EXTS:
            return "audio", True
        elif ext in self.DOC_EXTS:
            return "document", (ext in {'.pdf', '.txt', '.csv'})
        elif ext in self.CODE_EXTS:
            return "code", True
        elif ext in self.ARCHIVE_EXTS:
            return "archive", False
        return "other", False

    def list_directory(self, root_id: str, sub_path: str = "") -> Optional[Dict]:
        """Lists files and folders inside a given root and subpath."""
        target_path = self.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.exists(target_path) or not os.path.isdir(target_path):
            return None

        resolved = self.resolve_root_path(root_id)
        if not resolved:
            return None
        base_dir, is_protected, is_read_only = resolved

        # Clean relative path for breadcrumbs
        rel_path = os.path.relpath(target_path, base_dir)
        if rel_path == ".":
            rel_path = ""
        else:
            rel_path = rel_path.replace("\\", "/")

        items = []
        try:
            with os.scandir(target_path) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat()
                        is_dir = entry.is_dir()
                        item_rel = os.path.join(rel_path, entry.name).replace("\\", "/") if rel_path else entry.name
                        mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        
                        if is_dir:
                            items.append({
                                "name": entry.name,
                                "is_dir": True,
                                "path": item_rel,
                                "size_bytes": 0,
                                "size_str": "Folder",
                                "category": "folder",
                                "previewable": False,
                                "modified": mod_time,
                                "ext": ""
                            })
                        else:
                            cat, previewable = self.categorize_file(entry.name)
                            ext = os.path.splitext(entry.name)[1].lower()
                            has_thumb = (cat in {"image", "video"}) or (ext in {'.pdf', '.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.csv', '.log'})
                            items.append({
                                "name": entry.name,
                                "is_dir": False,
                                "path": item_rel,
                                "size_bytes": stat.st_size,
                                "size_str": self.format_size(stat.st_size),
                                "category": cat,
                                "previewable": previewable,
                                "has_thumbnail": has_thumb,
                                "modified": mod_time,
                                "ext": ext
                            })
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            return None

        # Sort: folders first, then files alphabetically
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        # Build breadcrumb trail
        breadcrumbs = [{"name": "Root", "path": ""}]
        if rel_path:
            parts = rel_path.split("/")
            cum_path = ""
            for part in parts:
                cum_path = f"{cum_path}/{part}" if cum_path else part
                breadcrumbs.append({"name": part, "path": cum_path})

        return {
            "root_id": root_id,
            "current_path": rel_path,
            "breadcrumbs": breadcrumbs,
            "items": items,
            "read_only": is_read_only,
            "total_items": len(items)
        }

    def create_zip_archive(self, root_id: str, sub_path: str = "") -> Optional[str]:
        """Creates a temporary zip archive of a directory or file and returns zip filepath."""
        target_path = self.get_safe_path(root_id, sub_path)
        if not target_path or not os.path.exists(target_path):
            return None

        temp_dir = os.path.join(self.base_dir, "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        
        zip_filename = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}.zip"
        zip_filepath = os.path.join(temp_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isdir(target_path):
                for root, _, files in os.walk(target_path):
                    for file in files:
                        full_fpath = os.path.join(root, file)
                        arcname = os.path.relpath(full_fpath, target_path)
                        zipf.write(full_fpath, arcname)
            else:
                zipf.write(target_path, os.path.basename(target_path))

        return zip_filepath
