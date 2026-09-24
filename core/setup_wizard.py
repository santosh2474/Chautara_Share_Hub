"""First-run installer for Chautara Share Hub.

The frozen standalone ``.exe`` is a single self-contained file. The first time
it is run from somewhere that has no ``server_config.json`` beside it, the
setup wizard asks:

  • the install directory on the system drive (default ``C:\\Chautara_Share_Hub``)
  • where the Public shared files should be stored (can be any drive/folder)

It then copies itself into the install directory, writes ``server_config.json``
(with ``public_storage_path`` / ``vault_storage_path``), creates the Public and
Vault folders, drops the welcome files, creates a desktop shortcut, and finally
starts the installed app.

Nothing is installed system-wide except the executable itself: no Python and no
libraries are required on the target PC.
"""
import os
import sys
import json
import shutil
import subprocess


APP_NAME = "Chautara_Share_Hub"
EXE_NAME = "Chautara_Share_Hub.exe"


def default_install_dir() -> str:
    """Return ``<SystemDrive>\\Chautara_Share_Hub`` (falls back to C:\\)."""
    system_drive = os.environ.get("SystemDrive") or "C:"
    return os.path.join(system_drive, APP_NAME)


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


def _create_desktop_shortcut(target_exe: str) -> bool:
    """Creates a Desktop shortcut using WScript.Shell (comtypes). Best-effort."""
    try:
        import comtypes.client
        shell = comtypes.client.CreateObject("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")
        lnk = shell.CreateShortCut(os.path.join(desktop, "Chautara Share Hub.lnk"))
        lnk.TargetPath = os.path.abspath(target_exe)
        lnk.WorkingDirectory = os.path.dirname(os.path.abspath(target_exe))
        lnk.Description = "Chautara Share Hub - Offline LAN File Sharing"
        lnk.WindowStyle = 1
        lnk.Save()
        return True
    except Exception:
        return False


def perform_install(install_dir: str, public_dir: str, vault_dir: str = None,
                    create_shortcut: bool = True) -> str:
    """Copies the running exe, writes config + folders, returns installed exe path."""
    install_dir = os.path.abspath(install_dir)
    public_dir = os.path.abspath(public_dir)
    vault_dir = os.path.abspath(vault_dir or os.path.join(install_dir, "Shared_Storage", "Vault"))

    os.makedirs(install_dir, exist_ok=True)
    os.makedirs(public_dir, exist_ok=True)
    os.makedirs(vault_dir, exist_ok=True)

    installed_exe = os.path.join(install_dir, EXE_NAME)
    if is_frozen():
        source_exe = os.path.abspath(sys.executable)
        if os.path.abspath(source_exe).lower() != installed_exe.lower():
            shutil.copy2(source_exe, installed_exe)

    _write_config(install_dir, public_dir, vault_dir)
    write_welcome_files(public_dir, vault_dir)

    if create_shortcut and os.path.exists(installed_exe):
        _create_desktop_shortcut(installed_exe)

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
    cmd = f'--silent --install-dir "{install_dir}" --public-dir "{public_dir}"'
    if vault_dir:
        cmd += f' --vault-dir "{vault_dir}"'
    if headless:
        cmd += f" --headless --port {port}"
    exe = os.path.abspath(sys.executable)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, cmd, install_dir, 1)


def run_wizard(install_dir_default: str = None, public_dir_default: str = None,
               force: bool = True, headless: bool = False, port: int = 5000):
    """Shows the interactive setup window.

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
    public_dir_default = public_dir_default or os.path.join(install_dir_default, "Shared_Storage", "Public")

    outcome = {"value": None, "path": None}

    class Wizard(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Chautara Share Hub - Setup")
            self.geometry("720x560")
            self.resizable(False, False)

            self.install_var = ctk.StringVar(value=install_dir_default)
            self.public_var = ctk.StringVar(value=public_dir_default)
            self.shortcut_var = ctk.BooleanVar(value=True)

            self._build_ui()

        def _build_ui(self):
            ctk.CTkLabel(
                self, text="Chautara Share Hub  -  First Run Setup",
                font=("Segoe UI", 20, "bold")
            ).pack(pady=(22, 4))
            ctk.CTkLabel(
                self, text="Everything is already included in this single file.\n"
                           "Choose where to install and where to keep the Public files.",
                text_color=("gray40", "gray75"), font=("Segoe UI", 12)
            ).pack(pady=(0, 16))

            frame = ctk.CTkFrame(self, corner_radius=12)
            frame.pack(fill="x", padx=40, pady=4)

            ctk.CTkLabel(frame, text="Install Folder (on this PC):", anchor="w",
                         font=("Segoe UI", 13, "bold")).pack(fill="x", padx=16, pady=(14, 2))
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", padx=16)
            self.install_entry = ctk.CTkEntry(row, textvariable=self.install_var)
            self.install_entry.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="Browse...", width=80, command=self._browse_install).pack(side="left", padx=(8, 0))

            ctk.CTkLabel(frame, text="Public Shared Files Folder:", anchor="w",
                         font=("Segoe UI", 13, "bold")).pack(fill="x", padx=16, pady=(16, 2))
            row2 = ctk.CTkFrame(frame, fg_color="transparent")
            row2.pack(fill="x", padx=16)
            self.public_entry = ctk.CTkEntry(row2, textvariable=self.public_var)
            self.public_entry.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row2, text="Browse...", width=80, command=self._browse_public).pack(side="left", padx=(8, 0))

            ctk.CTkLabel(
                frame,
                text="\u2022 Private Vault storage is created automatically inside the Install Folder.\n"
                     "\u2022 No Python or libraries are needed on this PC.",
                text_color=("gray45", "gray70"), font=("Segoe UI", 11),
                justify="left"
            ).pack(fill="x", padx=16, pady=(16, 4))

            ctk.CTkCheckBox(frame, text="Create a desktop shortcut", variable=self.shortcut_var,
                            font=("Segoe UI", 12)).pack(anchor="w", padx=16, pady=(4, 14))

            btnrow = ctk.CTkFrame(self, fg_color="transparent")
            btnrow.pack(fill="x", padx=40, pady=(18, 10))

            ctk.CTkButton(btnrow, text="Install & Start", height=40,
                          font=("Segoe UI", 14, "bold"), command=self._do_install).pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkButton(btnrow, text="Run Portable (this folder)", height=40,
                          font=("Segoe UI", 13), fg_color=("gray70", "gray30"),
                          command=self._do_portable).pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkButton(btnrow, text="Exit", height=40, font=("Segoe UI", 13),
                          fg_color=("gray55", "gray25"), command=self.destroy).pack(side="left", expand=True, fill="x", padx=4)

        def _browse_install(self):
            d = filedialog.askdirectory(title="Select Install Folder")
            if d:
                self.install_var.set(d)
                if self.public_var.get() == "" or (
                    self._default_public().lower() == os.path.normpath(self.public_var.get()).lower()
                ):
                    self.public_var.set(os.path.join(d, "Shared_Storage", "Public"))

        def _default_public(self):
            return os.path.join(self.install_var.get() or default_install_dir(), "Shared_Storage", "Public")

        def _browse_public(self):
            d = filedialog.askdirectory(title="Where should Public shared files be stored?")
            if d:
                self.public_var.set(d)

        def _run_install(self):
            install_dir = os.path.abspath(self.install_var.get().strip() or default_install_dir())
            public_dir = os.path.abspath(self.public_var.get().strip() or os.path.join(install_dir, "Shared_Storage", "Public"))
            try:
                installed_exe = perform_install(install_dir, public_dir,
                                                create_shortcut=self.shortcut_var.get())
            except PermissionError:
                if is_admin():
                    messagebox.showerror("Permission Denied",
                                         "Cannot create/write in the chosen Install Folder:\n" + install_dir)
                    return "error"
                relaunch_elevated(install_dir, public_dir, headless=headless, port=port)
                self.destroy()
                outcome["value"] = "installed"
                outcome["path"] = "elevated"
                return "installed"
            except Exception as e:
                messagebox.showerror("Setup Failed", f"Could not install:\n{e}")
                return "error"
            relaunch(installed_exe, headless=headless, port=port)
            self.destroy()
            outcome["value"] = "installed"
            outcome["path"] = installed_exe
            return "installed"

        def _do_install(self):
            self.after(50, lambda: self._run_install())

        def _do_portable(self):
            public_dir = os.path.abspath(self.public_var.get().strip() or
                                         os.path.join(default_install_dir(), "Shared_Storage", "Public"))
            base_dir = os.path.dirname(os.path.abspath(sys.executable))
            vault_dir = os.path.join(base_dir, "Shared_Storage", "Vault")
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