"""First-run installer for Chautara Share Hub.

The frozen standalone ``.exe`` is a single self-contained file. The first time
it is run from somewhere that has no ``server_config.json`` beside it, a
step-by-step setup wizard is shown (like a normal software installer):

  Step 1  Welcome screen with the developer contact details.
  Step 2  Install location on the system drive (default ``C:\\Chautara_Share_Hub``).
  Step 3  Where the Public shared files should be stored (any drive/folder).
  Step 4  Where the Private Vault should be stored (any drive/folder).
  Step 5  Options (desktop + Start Menu shortcuts) and Ready-to-Install summary.
  Step 6  Real-time progress while the app installs, then a Finish screen.

It then copies itself into the install directory, writes ``server_config.json``
(with ``public_storage_path`` / ``vault_storage_path``), creates the Public and
Vault folders, drops the welcome files, creates Desktop and Start Menu
shortcuts, and finally starts the installed app.

Nothing is installed system-wide except the executable itself: no Python and no
libraries are required on the target PC.

Developer: Er. Santosh Thakur
Contact: +977-9804743283 | info@santoshthakur.info.np | www.santoshthakur.info.np
"""
import os
import sys
import json
import shutil
import subprocess
import threading
import tempfile
import winreg


APP_NAME = "Chautara_Share_Hub"
EXE_NAME = "Chautara_Share_Hub.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ChautaraShareHub"
APP_REG_KEY = r"Software\Chautara Share Hub"


def default_install_dir() -> str:
    """Return the standard Windows install folder (Program Files on the system drive).

    Falls back to ``C:\\Program Files\\Chautara Share Hub`` when the Program
    Files environment variable is not present.
    """
    program_files = os.environ.get("ProgramFiles") or r"C:\Program Files"
    return os.path.join(program_files, APP_NAME)


def default_public_dir() -> str:
    """Default writable location for Public shared files (Public Documents)."""
    public_root = os.environ.get("PUBLIC")
    if not public_root:
        public_root = os.path.join(os.environ.get("SystemDrive") or "C:", "Users", "Public")
    return os.path.join(public_root, "Documents", APP_NAME, "Public")


def default_vault_dir() -> str:
    """Default writable location for the Private Vault (Public Documents)."""
    public_root = os.environ.get("PUBLIC")
    if not public_root:
        public_root = os.path.join(os.environ.get("SystemDrive") or "C:", "Users", "Public")
    return os.path.join(public_root, "Documents", APP_NAME, "Vault")


def _required() -> bool:
    """True when the running copy is a frozen .exe with no config beside it."""
    return bool(getattr(sys, "frozen", False))


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def running_without_config() -> bool:
    """True if this exe is running from a location that is not yet set up."""
    base_dir = os.path.dirname(os.path.abspath(sys.executable))
    return not os.path.exists(os.path.join(base_dir, "server_config.json"))


def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _argv_quote(text) -> str:
    """Quotes a value so Windows' command-line parser (CommandLineToArgvW)
    reads it back byte-for-byte, even when the path ends in a backslash.

    A drive root like ``C:\\`` or ``D:\\`` must NOT be written as ``"C:\\"`` —
    the CRT parser treats the backslash as escaping the closing quote and then
    swallows the next argument. Doubling the trailing backslashes fixes it:
    ``"D:\\\\"`` parses back to ``D:\\``.
    """
    s = str(text)
    trailing = len(s) - len(s.rstrip("\\"))
    return '"' + s + "\\" * trailing + '"'


def write_welcome_files(public_dir: str, vault_dir: str):
    """Seeds the Public and Vault folders with helpful starter files."""
    os.makedirs(public_dir, exist_ok=True)
    os.makedirs(vault_dir, exist_ok=True)

    welcome_file = os.path.join(public_dir, "Welcome_to_Chautara_Share_Hub.txt")
    if not os.path.exists(welcome_file):
        with open(welcome_file, "w", encoding="utf-8") as f:
            f.write(
                "===========================================================\n"
                " Welcome to Chautara Share Hub!                            \n"
                " Shree Chautara Secondary School - Local File Sharing Hub  \n"
                "===========================================================\n\n"
                "Features:\n"
                "- 100% Offline: Works within your school Wi-Fi, LAN, or Hotspot without internet.\n"
                "- Cross-Device: Open the link or scan the QR code from any smartphone, tablet, or PC.\n"
                "- High-Speed Upload & Download: Drag and drop files to share them across devices.\n"
                "- Drive Sharing: Plug in a USB flash drive and share it across the school network.\n"
                "- Private Vault: Admin password-protected storage for confidential school documents.\n"
            )

    vault_welcome = os.path.join(vault_dir, "Private_Admin_Vault_Info.txt")
    if not os.path.exists(vault_welcome):
        with open(vault_welcome, "w", encoding="utf-8") as f:
            f.write(
                "CONFIDENTIAL PRIVATE VAULT - CHAUTARA SHARE HUB\n"
                "----------------------------------------------\n"
                "Only authorized staff who enter the master admin password can view or download\n"
                "files placed in this directory.\n\n"
                "You can change the master password anytime in the desktop GUI.\n"
            )


def _default_vault_hash() -> str:
    """SHA-256 of the default master password, matching core/storage.py."""
    import hashlib
    salt = "antigravity_lan_vault_salt"
    return hashlib.sha256((salt + "admin123").encode("utf-8")).hexdigest()


def _build_config(install_dir: str, public_dir: str, vault_dir: str) -> dict:
    """Builds the initial server_config.json contents for a fresh install."""
    return {
        "vault_password_hash": _default_vault_hash(),
        "allow_public_upload": True,
        "allow_public_delete": False,
        "allow_vault_upload": True,
        "allow_vault_delete": True,
        "shared_usb_drives": {},
        "server_port": 5000,
        "server_name": "Chautara Share Hub",
        "public_storage_path": os.path.abspath(public_dir),
        "vault_storage_path": os.path.abspath(vault_dir),
    }


def _write_config(install_dir: str, public_dir: str, vault_dir: str):
    config = _build_config(install_dir, public_dir, vault_dir)
    config_path = os.path.join(install_dir, "server_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return config_path


def _discover_shortcut_folders() -> dict:
    """Returns {"desktop": path, "start": programs_path} via comtypes or PowerShell."""
    folders = {}
    try:
        import comtypes.client
        shell = comtypes.client.CreateObject("WScript.Shell")
        folders["desktop"] = shell.SpecialFolders("Desktop")
        folders["start"] = os.path.join(shell.SpecialFolders("StartMenu"), "Programs")
        return folders
    except Exception:
        pass
    try:
        ps = "$s = New-Object -ComObject WScript.Shell;" \
             " $s.SpecialFolders('Desktop'); $s.SpecialFolders('StartMenu')"
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=20)
        lines = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]
        if len(lines) >= 1 and lines[0]:
            folders["desktop"] = lines[0]
        if len(lines) >= 2 and lines[1]:
            folders["start"] = os.path.join(lines[1], "Programs")
    except Exception:
        pass
    return folders


def _make_shortcut(folder: str, target_exe: str, workdir: str,
                   lnk_name: str = "Chautara Share Hub.lnk",
                   arguments: str = "") -> bool:
    """Creates a single .lnk shortcut. comtypes first, PowerShell fallback."""
    lnk_path = os.path.join(folder, lnk_name)
    try:
        os.makedirs(folder, exist_ok=True)
        import comtypes.client
        shell = comtypes.client.CreateObject("WScript.Shell")
        lnk = shell.CreateShortCut(lnk_path)
        lnk.TargetPath = os.path.abspath(target_exe)
        lnk.WorkingDirectory = workdir
        if arguments:
            lnk.Arguments = arguments
        lnk.Description = "Chautara Share Hub - Offline LAN File Sharing"
        lnk.WindowStyle = 1
        lnk.IconLocation = f"{os.path.abspath(target_exe)},0"
        lnk.Save()
        return os.path.exists(lnk_path)
    except Exception:
        pass
    try:
        def _q(s):
            return "'" + str(s).replace("'", "''") + "'"
        ps = ("$s = New-Object -ComObject WScript.Shell; "
              f"$l = $s.CreateShortcut({_q(lnk_path)}); "
              f"$l.TargetPath = {_q(os.path.abspath(target_exe))}; "
              f"$l.WorkingDirectory = {_q(workdir)}; "
              f"$l.Arguments = {_q(arguments)}; "
              "$l.Description = 'Chautara Share Hub - Offline LAN File Sharing'; "
              "$l.WindowStyle = 1; "
              f"$l.IconLocation = {_q(os.path.abspath(target_exe) + ',0')}; "
              "$l.Save()")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, timeout=30)
        return os.path.exists(lnk_path)
    except Exception:
        return False


def _create_shortcuts(target_exe: str, create_desktop: bool = True,
                      create_start_menu: bool = True) -> bool:
    """Creates Desktop and Start Menu shortcuts. Best-effort, returns success."""
    target_exe = os.path.abspath(target_exe)
    workdir = os.path.dirname(target_exe)
    folders = _discover_shortcut_folders()
    ok = False
    if create_desktop and folders.get("desktop"):
        ok = _make_shortcut(folders["desktop"], target_exe, workdir) or ok
    if create_start_menu and folders.get("start"):
        ok = _make_shortcut(folders["start"], target_exe, workdir) or ok
        ok = _make_shortcut(folders["start"], target_exe, workdir,
                            lnk_name="Uninstall Chautara Share Hub.lnk",
                            arguments="--uninstall") or ok
    return ok


def _create_desktop_shortcut(target_exe: str) -> bool:
    """Backward-compatible helper: desktop shortcut only."""
    return _create_shortcuts(target_exe, create_desktop=True, create_start_menu=False)


# ---------------------------------------------------------------------------
# Windows registration (Control Panel / Settings > Apps list)
# ---------------------------------------------------------------------------
def _registry_roots_for_write():
    """Preferred registry roots to write to (HKLM first when elevated)."""
    if is_admin():
        return [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    return [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]


def _delete_registry_keys(root) -> None:
    for subkey in (UNINSTALL_KEY, APP_REG_KEY):
        try:
            winreg.DeleteKeyEx(root, subkey, 0, winreg.KEY_ALL_ACCESS)
        except OSError:
            try:
                winreg.DeleteKey(root, subkey)
            except OSError:
                pass


def _register_in_control_panel(installed_exe: str, public_dir: str = "",
                               vault_dir: str = "") -> bool:
    """Writes registry keys so Windows Settings/Control Panel lists the app."""
    installed_exe = os.path.abspath(installed_exe)
    install_dir = os.path.dirname(installed_exe)
    try:
        size_kb = int(os.path.getsize(installed_exe) / 1024)
    except OSError:
        size_kb = 0

    values = [
        ("DisplayName", winreg.REG_SZ, "Chautara Share Hub"),
        ("DisplayVersion", winreg.REG_SZ, "1.0.0"),
        ("Publisher", winreg.REG_SZ, "Er. Santosh Thakur"),
        ("DisplayIcon", winreg.REG_SZ, f'"{installed_exe}",0'),
        ("InstallLocation", winreg.REG_SZ, install_dir),
        ("UninstallString", winreg.REG_SZ, f'"{installed_exe}" --uninstall'),
        ("QuietUninstallString", winreg.REG_SZ, f'"{installed_exe}" --uninstall --yes --delete-data'),
        ("URLInfoAbout", winreg.REG_SZ, "https://www.santoshthakur.info.np"),
        ("HelpLink", winreg.REG_SZ, "https://www.santoshthakur.info.np"),
        ("Contact", winreg.REG_SZ, "+977-9804743283"),
        ("Comments", winreg.REG_SZ, "Offline LAN File Sharing & Security Vault by Er. Santosh Thakur"),
        ("EstimatedSize", winreg.REG_DWORD, size_kb),
        ("NoModify", winreg.REG_DWORD, 1),
        ("NoRepair", winreg.REG_DWORD, 1),
    ]
    app_values = [
        ("InstallPath", winreg.REG_SZ, install_dir),
        ("ExePath", winreg.REG_SZ, installed_exe),
        ("PublicPath", winreg.REG_SZ, public_dir),
        ("VaultPath", winreg.REG_SZ, vault_dir),
    ]

    written_root = None
    for root in _registry_roots_for_write():
        try:
            key = winreg.CreateKeyEx(root, UNINSTALL_KEY, 0, winreg.KEY_SET_VALUE)
            for name, kind, data in values:
                winreg.SetValueEx(key, name, 0, kind, data)
            winreg.CloseKey(key)

            akey = winreg.CreateKeyEx(root, APP_REG_KEY, 0, winreg.KEY_SET_VALUE)
            for name, kind, data in app_values:
                winreg.SetValueEx(akey, name, 0, kind, data)
            winreg.CloseKey(akey)
            written_root = root
            break
        except OSError:
            continue

    if written_root is not None:
        # Remove any duplicate entry from the other root to avoid two entries.
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            if root is not written_root:
                _delete_registry_keys(root)
        return True
    return False


def unregister_from_control_panel() -> None:
    """Removes the app from Windows Settings/Control Panel (all roots)."""
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        _delete_registry_keys(root)


def _registry_install_dir() -> str:
    """Reads InstallPath written at install time (empty when not installed)."""
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(root, APP_REG_KEY, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if val:
                return str(val)
        except OSError:
            continue
    return ""


def _registry_hklm_installed() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY, 0, winreg.KEY_READ)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def _registry_storage_dirs(install_dir: str):
    """Reads public/vault paths from the registry, falling back to config."""
    public_dir = vault_dir = ""
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            key = winreg.OpenKey(root, APP_REG_KEY, 0, winreg.KEY_READ)
            try:
                public_dir, _ = winreg.QueryValueEx(key, "PublicPath")
            except OSError:
                pass
            try:
                vault_dir, _ = winreg.QueryValueEx(key, "VaultPath")
            except OSError:
                pass
            winreg.CloseKey(key)
            if public_dir and vault_dir:
                break
        except OSError:
            continue

    cfg_path = os.path.join(install_dir, "server_config.json")
    if (not public_dir or not vault_dir) and os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            public_dir = public_dir or cfg.get("public_storage_path", "")
            vault_dir = vault_dir or cfg.get("vault_storage_path", "")
        except Exception:
            pass

    if not public_dir:
        public_dir = default_public_dir()
    if not vault_dir:
        vault_dir = default_vault_dir()
    return public_dir, vault_dir


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------
def _find_running_instances():
    """Returns other processes running the same executable (excludes self)."""
    me = os.getpid()
    my_exe = os.path.abspath(sys.executable).lower()
    found = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "exe"]):
            try:
                if proc.info["pid"] == me:
                    continue
                exe = proc.info.get("exe") or ""
                if exe and os.path.abspath(exe).lower() == my_exe:
                    found.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return found


def _remove_all_shortcuts() -> None:
    folders = _discover_shortcut_folders()
    names = ["Chautara Share Hub.lnk", "Uninstall Chautara Share Hub.lnk"]
    targets = []
    if folders.get("desktop"):
        targets.append(folders["desktop"])
    if folders.get("start"):
        targets.append(folders["start"])
    for folder in targets:
        for name in names:
            try:
                path = os.path.join(folder, name)
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


def _can_write(path: str) -> bool:
    try:
        test = os.path.join(path, ".write_test_tmp")
        with open(test, "w", encoding="utf-8"):
            pass
        os.remove(test)
        return True
    except Exception:
        return False


def _delete_install_dir_later(install_dir: str) -> None:
    """Detached cmd waits for this exe to exit, then removes the install folder."""
    try:
        bat = os.path.join(tempfile.gettempdir(), "chautara_uninstall_tmp.bat")
        content = (
            "@echo off\r\n"
            "ping -n 5 127.0.0.1 >nul\r\n"
            f'if exist "{install_dir}" rmdir /s /q "{install_dir}"\r\n'
            'del /f /q "%~f0"\r\n'
        )
        with open(bat, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.Popen(["cmd", "/c", bat],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         close_fds=True)
    except Exception:
        pass


def _show_uninstall_dialog():
    """Small confirmation window. Returns 'yes', 'yes_delete' or None."""
    try:
        import customtkinter as ctk
    except Exception:
        return None

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    result = {"choice": None}

    class UninstallDlg(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Uninstall Chautara Share Hub")
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w, h = 580, 380
            self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
            self.resizable(False, False)

            ctk.CTkLabel(self, text="Uninstall Chautara Share Hub",
                         font=("Segoe UI", 18, "bold")).pack(pady=(24, 6))
            ctk.CTkLabel(
                self,
                text="This will remove the application, its shortcuts and the\n"
                     "Control Panel entry from this computer.",
                font=("Segoe UI", 12), justify="center"
            ).pack(pady=(0, 14))

            info = ctk.CTkFrame(self, corner_radius=10)
            info.pack(fill="x", padx=36)
            public_dir, vault_dir = _registry_storage_dirs(
                _registry_install_dir() or os.path.dirname(os.path.abspath(sys.executable)))
            ctk.CTkLabel(info, text=f"Public files: {public_dir}", font=("Segoe UI", 11),
                         justify="left").pack(anchor="w", padx=14, pady=(10, 3))
            ctk.CTkLabel(info, text=f"Vault: {vault_dir}", font=("Segoe UI", 11),
                         justify="left").pack(anchor="w", padx=14, pady=(0, 10))

            self.del_var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(self, text="Also delete the Public & Vault files",
                            variable=self.del_var, font=("Segoe UI", 12)
                            ).pack(anchor="w", padx=40, pady=(14, 0))

            btns = ctk.CTkFrame(self, fg_color="transparent")
            btns.pack(fill="x", padx=36, pady=(22, 10))
            ctk.CTkButton(btns, text="Uninstall", width=150, height=38,
                          fg_color="#ef4444", hover_color="#dc2626",
                          font=("Segoe UI", 13, "bold"),
                          command=self._do_uninstall).pack(side="left", expand=True, fill="x")
            ctk.CTkButton(btns, text="Cancel", width=130, height=38,
                          fg_color=("gray60", "gray30"),
                          font=("Segoe UI", 13),
                          command=self.destroy).pack(side="left", expand=True, fill="x", padx=(10, 0))

            ctk.CTkLabel(self,
                         text="Developed By: Er. Santosh Thakur  |  www.santoshthakur.info.np",
                         font=("Segoe UI", 9), text_color=("gray45", "gray70")
                         ).pack(side="bottom", pady=(6, 10))

        def _do_uninstall(self):
            result["choice"] = "yes_delete" if self.del_var.get() else "yes"
            self.destroy()

    dlg = UninstallDlg()
    dlg.mainloop()
    return result["choice"]


def _relaunch_elevated_uninstall(delete_data: bool) -> bool:
    """Re-runs this exe as administrator to finish the uninstall."""
    import ctypes
    exe = os.path.abspath(sys.executable)
    cmd = "--uninstall --yes" + (" --delete-data" if delete_data else "")
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, cmd,
                                             os.path.dirname(exe), 1)
    return (rc or 0) > 32


def _perform_uninstall(install_dir: str, public_dir: str, vault_dir: str,
                       delete_data: bool) -> None:
    """Registry + shortcuts + optional data removal, then schedules folder delete."""
    reg_install = _registry_install_dir()

    unregister_from_control_panel()
    _remove_all_shortcuts()

    if delete_data:
        for d in (public_dir, vault_dir):
            if d and os.path.isdir(d):
                try:
                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

    # Only ever remove a folder that the installer itself registered.
    if reg_install and os.path.isdir(reg_install):
        if os.path.abspath(reg_install).lower() == os.path.abspath(install_dir).lower():
            _delete_install_dir_later(reg_install)
        else:
            try:
                shutil.rmtree(reg_install, ignore_errors=True)
            except Exception:
                pass


def run_uninstall(ask: bool = True, delete_data: bool = False,
                  silent: bool = False) -> bool:
    """Full uninstall flow. Returns True when this process should exit.

    Interactive by default: confirmation dialog, closes running copies, elevates
    when needed, removes registry/shortcuts/data, then deletes the install folder.
    """
    from tkinter import messagebox

    install_dir = _registry_install_dir() or os.path.dirname(os.path.abspath(sys.executable))
    public_dir, vault_dir = _registry_storage_dirs(install_dir)

    # --- Close running copies of the app first ---
    running = _find_running_instances()
    if running:
        if silent:
            for proc in running:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        else:
            if not messagebox.askyesno(
                    "Application is Running",
                    "Chautara Share Hub is currently running.\n"
                    "It must be closed before uninstalling.\n\n"
                    "Close it now and continue?"):
                return False
            for proc in running:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        running = _find_running_instances()
        if running:
            messagebox.showerror(
                "Cannot Uninstall",
                "Could not close the running application.\nPlease close it manually and try again.")
            return False

    # --- Confirmation dialog ---
    if ask and not silent:
        choice = _show_uninstall_dialog()
        if choice is None:
            return False
        delete_data = (choice == "yes_delete")

    # --- Elevate when the install folder or HKLM keys need admin rights ---
    need_admin = (not is_admin()) and (_registry_hklm_installed() or not _can_write(install_dir))
    if need_admin:
        if silent:
            messagebox.showerror(
                "Administrator Required",
                "Administrator permission is required to uninstall this application.")
            return False
        if not _relaunch_elevated_uninstall(delete_data):
            messagebox.showerror(
                "Uninstall Cancelled",
                "Administrator permission is required to uninstall this application.")
            return False
        return True

    _perform_uninstall(install_dir, public_dir, vault_dir, delete_data)

    if not silent:
        messagebox.showinfo(
            "Uninstall Complete",
            "Chautara Share Hub has been uninstalled successfully."
            + ("" if delete_data else "\n\nYour Public and Vault files were kept."))
    return True


def perform_install(install_dir: str, public_dir: str, vault_dir: str = None,
                    create_shortcut: bool = True, create_start_menu: bool = True,
                    progress=None) -> str:
    """Copies the running exe, writes config + folders, returns installed exe path.

    ``progress`` may be a callable receiving a human-readable stage string.
    """
    install_dir = os.path.abspath(install_dir)
    public_dir = os.path.abspath(public_dir)
    vault_dir = os.path.abspath(vault_dir or default_vault_dir())

    def _report(stage):
        if progress:
            try:
                progress(stage)
            except Exception:
                pass

    _report("Creating installation folders...")
    os.makedirs(install_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)
    os.makedirs(vault_dir, exist_ok=True)

    installed_exe = os.path.join(install_dir, EXE_NAME)
    if is_frozen():
        source_exe = os.path.abspath(sys.executable)
        if os.path.abspath(source_exe).lower() != installed_exe.lower():
            _report("Copying program files...")
            shutil.copy2(source_exe, installed_exe)

    _report("Writing configuration...")
    _write_config(install_dir, public_dir, vault_dir)
    _report("Creating Public & Vault folders...")
    write_welcome_files(public_dir, vault_dir)

    if os.path.exists(installed_exe):
        _report("Creating shortcuts...")
        _create_shortcuts(installed_exe,
                          create_desktop=create_shortcut,
                          create_start_menu=create_start_menu)

    _report("Registering in Windows...")
    _register_in_control_panel(installed_exe, public_dir, vault_dir)

    _report("Installation complete.")
    return installed_exe


def relaunch(installed_exe: str, headless: bool = False, port: int = 5000):
    """Starts the installed app and lets this (temporary) copy exit."""
    cmd = [os.path.abspath(installed_exe)]
    if headless:
        cmd += ["--headless", "--port", str(port)]
    try:
        if getattr(sys, "frozen", False):
            subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(installed_exe)))
        else:
            subprocess.Popen(cmd)
    except Exception:
        pass


def relaunch_elevated(install_dir: str, public_dir: str, vault_dir: str = None,
                      headless: bool = False, port: int = 5000):
    """Re-runs this exe as administrator to finish an install silently."""
    import ctypes
    cmd = f'--silent --install-dir {_argv_quote(install_dir)} --public-dir {_argv_quote(public_dir)}'
    if vault_dir:
        cmd += f' --vault-dir {_argv_quote(vault_dir)}'
    if headless:
        cmd += f" --headless --port {port}"
    exe = os.path.abspath(sys.executable)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, cmd, install_dir, 1)


def run_wizard(install_dir_default: str = None, public_dir_default: str = None,
               force: bool = True, headless: bool = False, port: int = 5000):
    """Shows the interactive step-by-step setup window.

    Returns one of:
      ``("installed", installed_exe_path)`` -> app relaunched, caller may exit
      ``("portable", None)``                -> caller should start normally here
      ``(None, None)``                      -> cancelled
    """
    try:
        import customtkinter as ctk
        from tkinter import filedialog, messagebox
    except Exception:
        # GUI toolkit unavailable -> nothing sensible to show.
        return None, None

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    install_dir_default = install_dir_default or default_install_dir()
    public_dir_default = public_dir_default or default_public_dir()
    vault_dir_default = default_vault_dir()

    outcome = {"value": None, "path": None}
    CREDIT = ("Developed By: Er. Santosh Thakur   |   Contact No.: +977-9804743283\n"
              "Mail Id.: info@santoshthakur.info.np   |   Website: www.santoshthakur.info.np")

    class Wizard(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Chautara Share Hub Setup")
            self.resizable(True, True)
            self.minsize(600, 480)
            self._apply_initial_geometry()

            self._wrap_labels = []

            self._geometry_ready = False
            self.bind("<Configure>", self._on_resize)
            self.protocol("WM_DELETE_WINDOW", self._on_close)

            self.current_step = 0
            self.total_steps = 5
            self.installing = False

            self.install_var = ctk.StringVar(value=install_dir_default)
            self.public_var = ctk.StringVar(value=public_dir_default)
            self.vault_var = ctk.StringVar(value=vault_dir_default)
            self.shortcut_var = ctk.BooleanVar(value=True)
            self.startmenu_var = ctk.BooleanVar(value=True)

            self._build_shell()
            self._build_steps()
            self._show_step(0)

        # ---------------------------------------------------------- shell
        def _apply_initial_geometry(self):
            try:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
            except Exception:
                sw, sh = 1366, 768
            width = max(620, min(760, int(sw * 0.6)))
            height = max(520, min(620, int(sh * 0.72)))
            self.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")

        def _on_resize(self, event):
            if event.widget is not self:
                return
            wrap = max(320, event.width - 130)
            for label in self._wrap_labels:
                try:
                    label.configure(wraplength=wrap)
                except Exception:
                    pass

        def _make_wrap_label(self, parent, text, **kwargs):
            kwargs.setdefault("font", ("Segoe UI", 12))
            kwargs.setdefault("justify", "left")
            kwargs.setdefault("wraplength", max(320, self.winfo_width() - 130))
            label = ctk.CTkLabel(parent, text=text, **kwargs)
            self._wrap_labels.append(label)
            return label

        def _build_shell(self):
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=30, pady=(20, 0))

            self.title_label = ctk.CTkLabel(header, text="Chautara Share Hub Setup",
                                            font=("Segoe UI", 20, "bold"))
            self.title_label.pack(anchor="w")
            self.step_label = ctk.CTkLabel(header, text="", font=("Segoe UI", 11),
                                           text_color="gray")
            self.step_label.pack(anchor="w", pady=(2, 0))

            self.body = ctk.CTkScrollableFrame(self, corner_radius=12)
            self.body.pack(fill="both", expand=True, padx=30, pady=(14, 8))

            nav = ctk.CTkFrame(self, fg_color="transparent")
            nav.pack(fill="x", padx=30, pady=(0, 4))

            self.btn_cancel = ctk.CTkButton(nav, text="Cancel", width=92,
                                            fg_color=("gray55", "gray25"), command=self.destroy)
            self.btn_cancel.pack(side="right")

            self.btn_next = ctk.CTkButton(nav, text="Next >", width=110,
                                          font=("Segoe UI", 13, "bold"), command=self._next)
            self.btn_next.pack(side="right", padx=8)

            self.btn_back = ctk.CTkButton(nav, text="< Back", width=92,
                                          fg_color=("gray70", "gray30"), command=self._back)
            self.btn_back.pack(side="right", padx=(0, 8))

            ctk.CTkLabel(self, text=CREDIT, font=("Segoe UI", 9),
                         text_color=("gray45", "gray70"), justify="center"
                         ).pack(pady=(4, 10))

        # ---------------------------------------------------------- steps
        def _build_steps(self):
            self.step_frames = [
                self._build_welcome_step(),
                self._build_folder_step(
                    "Choose Install Location",
                    "Setup will install the program files of Chautara Share Hub in the\n"
                    "folder below. To install in a different folder, click Browse.",
                    self.install_var, "Select Install Folder",
                    "Tip: The default folder is on the system drive of this computer."),
                self._build_folder_step(
                    "Choose Public Shared Files Folder",
                    "Network users will upload and download files from this folder.\n"
                    "You can store it on any drive of this computer.",
                    self.public_var, "Where should Public shared files be stored?",
                    "Tip: Pick a large drive so all students & staff can share files."),
                self._build_folder_step(
                    "Choose Private Vault Folder",
                    "Confidential files protected by the admin password go here.\n"
                    "You can store it on any drive of this computer.",
                    self.vault_var, "Where should the Private Vault be stored?",
                    "Tip: The Vault is password-protected inside the application."),
                self._build_options_step(),
                self._build_progress_step(),
                self._build_done_step(),
            ]
            for f in self.step_frames:
                f.pack_forget()

        def _build_welcome_step(self):
            f = ctk.CTkFrame(self.body, fg_color="transparent")

            ctk.CTkLabel(f, text="Welcome to Chautara Share Hub Setup",
                         font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(4, 8))
            self._make_wrap_label(
                f, "This wizard will install Chautara Share Hub on your computer.\n"
                   "Click Next to continue or Cancel to exit Setup."
            ).pack(anchor="w")

            box = ctk.CTkFrame(f, corner_radius=10)
            box.pack(fill="x", pady=(16, 0))
            ctk.CTkLabel(box, text="This installer will:", font=("Segoe UI", 13, "bold")
                         ).pack(anchor="w", padx=16, pady=(12, 4))
            for line in (
                f"• Install the app on your computer (default: {default_install_dir()}).",
                "• Ask where to store Public shared files (any drive).",
                "• Ask where to store the Private Vault (any drive).",
                "• Create Desktop and Start Menu shortcuts.",
                "• Register the app in Windows so you can uninstall it "
                "from the Control Panel / Settings.",
                "• No Python or extra software is needed, everything is in one file.",
            ):
                self._make_wrap_label(box, line, font=("Segoe UI", 11)
                                      ).pack(anchor="w", padx=16, pady=2)

            dev = ctk.CTkFrame(f, corner_radius=10)
            dev.pack(fill="x", pady=(14, 0))
            ctk.CTkLabel(dev, text="Developer", font=("Segoe UI", 13, "bold")
                         ).pack(anchor="w", padx=16, pady=(10, 2))
            ctk.CTkLabel(dev, text=CREDIT.replace("   |   ", "\n"), font=("Segoe UI", 11),
                         justify="left", text_color=("gray20", "gray85")
                         ).pack(anchor="w", padx=16, pady=(0, 10))
            return f

        def _build_folder_step(self, title, desc, var, dialog_title, hint):
            f = ctk.CTkFrame(self.body, fg_color="transparent")

            ctk.CTkLabel(f, text=title, font=("Segoe UI", 17, "bold")
                         ).pack(anchor="w", pady=(4, 6))
            self._make_wrap_label(f, desc).pack(anchor="w", pady=(0, 14))

            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(0, 8))
            row.grid_columnconfigure(0, weight=1)

            entry = ctk.CTkEntry(row, textvariable=var, height=34)
            entry.grid(row=0, column=0, sticky="ew")

            def browse():
                d = filedialog.askdirectory(title=dialog_title)
                if d:
                    var.set(d)

            ctk.CTkButton(row, text="Browse...", width=110, command=browse
                          ).grid(row=0, column=1, padx=(8, 0))

            ctk.CTkLabel(f, text=hint, font=("Segoe UI", 11), text_color="gray",
                         justify="left", wraplength=max(320, self.winfo_width() - 130)
                         ).pack(anchor="w", pady=(14, 0))
            return f

        def _build_options_step(self):
            f = ctk.CTkFrame(self.body, fg_color="transparent")

            ctk.CTkLabel(f, text="Ready to Install", font=("Segoe UI", 17, "bold")
                         ).pack(anchor="w", pady=(4, 6))
            self._make_wrap_label(
                f, "Setup is now ready to begin installing Chautara Share Hub "
                   "on your computer. Review the settings below."
            ).pack(anchor="w", pady=(0, 14))

            summary = ctk.CTkFrame(f, corner_radius=10)
            summary.pack(fill="x", pady=(0, 16))
            self.summary_install = ctk.CTkLabel(summary, text="", font=("Segoe UI", 12),
                                                justify="left", anchor="w",
                                                wraplength=max(320, self.winfo_width() - 130))
            self.summary_install.pack(anchor="w", padx=16, pady=(12, 3))
            self.summary_public = ctk.CTkLabel(summary, text="", font=("Segoe UI", 12),
                                               justify="left", anchor="w",
                                               wraplength=max(320, self.winfo_width() - 130))
            self.summary_public.pack(anchor="w", padx=16, pady=3)
            self.summary_vault = ctk.CTkLabel(summary, text="", font=("Segoe UI", 12),
                                              justify="left", anchor="w",
                                              wraplength=max(320, self.winfo_width() - 130))
            self.summary_vault.pack(anchor="w", padx=16, pady=(3, 12))

            self._wrap_labels += [self.summary_install, self.summary_public, self.summary_vault]

            ctk.CTkCheckBox(f, text="Create a Desktop shortcut", variable=self.shortcut_var,
                            font=("Segoe UI", 12)).pack(anchor="w")
            ctk.CTkCheckBox(f, text="Create a Start Menu shortcut", variable=self.startmenu_var,
                            font=("Segoe UI", 12)).pack(anchor="w", pady=(4, 16))

            ctk.CTkButton(f, text="Run without installing (Portable mode)", fg_color="transparent",
                          text_color=("gray30", "gray70"), height=28,
                          command=self._do_portable).pack(side="bottom", anchor="w")
            return f

        def _refresh_summary(self):
            self.summary_install.configure(
                text="Program folder:\n    " + os.path.abspath(self.install_var.get().strip() or default_install_dir()))
            self.summary_public.configure(
                text="Public shared files:\n    " + os.path.abspath(self.public_var.get().strip() or default_public_dir()))
            self.summary_vault.configure(
                text="Private Vault:\n    " + os.path.abspath(self.vault_var.get().strip() or default_vault_dir()))

        def _build_progress_step(self):
            f = ctk.CTkFrame(self.body, fg_color="transparent")
            inner = ctk.CTkFrame(f, corner_radius=12)
            inner.pack(fill="both", expand=True, pady=50, padx=10)

            ctk.CTkLabel(inner, text="Installing Chautara Share Hub...",
                         font=("Segoe UI", 16, "bold")).pack(pady=(34, 10))
            self.status_label = ctk.CTkLabel(inner, text="Preparing installation...",
                                             font=("Segoe UI", 12), text_color="gray")
            self.status_label.pack(pady=6)
            self.progressbar = ctk.CTkProgressBar(inner)
            self.progressbar.pack(pady=(20, 12), fill="x", padx=30)
            self.progressbar.set(0)
            self._make_wrap_label(
                inner, "Please wait while Setup installs the files on your computer.",
                font=("Segoe UI", 11), text_color=("gray45", "gray70"), justify="center"
            ).pack(pady=(0, 34))
            return f

        def _build_done_step(self):
            f = ctk.CTkFrame(self.body, fg_color="transparent")

            ctk.CTkLabel(f, text="\u2713  Installation Complete",
                         font=("Segoe UI", 20, "bold"), text_color="#10b981"
                         ).pack(anchor="w", pady=(6, 8))
            self._make_wrap_label(
                f, "Chautara Share Hub has been installed successfully.\n"
                   "The app will start and a shortcut has been placed on your Desktop."
            ).pack(anchor="w")
            self.done_detail = ctk.CTkLabel(f, text="", font=("Segoe UI", 12), text_color="gray",
                                            justify="left",
                                            wraplength=max(320, self.winfo_width() - 130))
            self.done_detail.pack(anchor="w", pady=(12, 0))
            self._wrap_labels.append(self.done_detail)
            ctk.CTkButton(f, text="Finish", width=140, height=38,
                          font=("Segoe UI", 13, "bold"), command=self._finish
                          ).pack(anchor="e", pady=(28, 0))
            return f

        # ---------------------------------------------------------- navigation
        def _show_step(self, idx):
            self.current_step = idx
            for frame in self.step_frames:
                frame.pack_forget()
            self.step_frames[idx].pack(fill="both", expand=True, padx=20, pady=16)

            if idx == 4:
                self._refresh_summary()

            if idx <= 4:
                self.step_label.configure(text=f"Step {idx + 1} of {self.total_steps}")
                self.btn_back.configure(state="normal" if idx > 0 else "disabled")
                self.btn_next.configure(text="Install" if idx == 4 else "Next >", state="normal")
                self.btn_cancel.configure(state="normal", text="Cancel")
            elif idx == 5:
                self.step_label.configure(text="Installing...")
                self.btn_back.configure(state="disabled")
                self.btn_next.configure(state="disabled")
                self.btn_cancel.configure(state="disabled")
            else:
                self.step_label.configure(text="Setup completed")
                self.btn_back.configure(state="disabled")
                self.btn_next.configure(state="normal", text="Finish")
                self.btn_cancel.configure(state="disabled")

        def _validate(self):
            if self.current_step in (1, 2, 3):
                var = {1: self.install_var, 2: self.public_var, 3: self.vault_var}[self.current_step]
                val = var.get().strip()
                if not val:
                    messagebox.showwarning("Missing Folder",
                                           "Please choose a folder or type a path before continuing.")
                    return False
                return True
            return True

        def _next(self):
            if self.current_step == 5:
                return
            if self.current_step == 6:
                self._finish()
                return
            if not self._validate():
                return

            if self.current_step == 4:
                self._start_install()
                return
            self._show_step(self.current_step + 1)

        def _back(self):
            if 0 < self.current_step <= 4:
                self._show_step(self.current_step - 1)

        def _on_close(self):
            if self.installing:
                return
            self.destroy()

        # ---------------------------------------------------------- install
        def _start_install(self):
            self.install_dir = os.path.abspath(self.install_var.get().strip() or default_install_dir())
            self.public_dir = os.path.abspath(self.public_var.get().strip() or default_public_dir())
            self.vault_dir = os.path.abspath(self.vault_var.get().strip() or default_vault_dir())
            self.installing = True
            self._show_step(5)
            try:
                self.progressbar.configure(mode="indeterminate")
                self.progressbar.start()
            except Exception:
                pass
            threading.Thread(target=self._install_worker, daemon=True).start()

        def _install_worker(self):
            def report(msg):
                try:
                    self.after(0, lambda m=msg: self.status_label.configure(text=m))
                except Exception:
                    pass
            try:
                installed_exe = perform_install(
                    self.install_dir, self.public_dir, self.vault_dir,
                    create_shortcut=self.shortcut_var.get(),
                    create_start_menu=self.startmenu_var.get(),
                    progress=report)
                outcome["value"] = "installed"
                outcome["path"] = installed_exe
                self.after(0, self._install_success)
            except PermissionError:
                self.after(0, self._install_permission_error)
            except Exception as e:
                self.after(0, lambda err=e: self._install_failed(err))

        def _install_permission_error(self):
            self.installing = False
            try:
                self.progressbar.stop()
            except Exception:
                pass
            if is_admin():
                messagebox.showerror("Permission Denied",
                                     "Cannot create/write in the chosen Install Folder:\n" +
                                     self.install_dir)
                self._show_step(4)
                return
            relaunch_elevated(self.install_dir, self.public_dir, self.vault_dir,
                              headless=headless, port=port)
            outcome["value"] = "installed"
            outcome["path"] = "elevated"
            self.destroy()

        def _install_failed(self, err):
            self.installing = False
            try:
                self.progressbar.stop()
            except Exception:
                pass
            messagebox.showerror("Setup Failed", f"Could not install:\n{err}")
            self._show_step(4)

        def _install_success(self):
            self.installing = False
            try:
                self.progressbar.stop()
                self.progressbar.set(1)
            except Exception:
                pass
            self.done_detail.configure(
                text="Installed to:\n    " + os.path.abspath(outcome["path"]))
            self._show_step(6)

        def _finish(self):
            if outcome["value"] == "installed" and outcome["path"] not in (None, "elevated"):
                relaunch(outcome["path"], headless=headless, port=port)
            self.destroy()

        def _do_portable(self):
            public_dir = os.path.abspath(self.public_var.get().strip() or default_public_dir())
            vault_dir = os.path.abspath(self.vault_var.get().strip() or default_vault_dir())
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
            try:
                _write_config(base_dir, public_dir, vault_dir)
                write_welcome_files(public_dir, vault_dir)
            except Exception as e:
                messagebox.showerror("Portable Setup Failed", f"Could not write config:\n{e}")
                return
            self.destroy()
            outcome["value"] = "portable"

    app = Wizard()
    app.mainloop()
    return outcome["value"], outcome["path"]


