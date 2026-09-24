"""Main Application Entrypoint: Launches CustomTkinter GUI or Headless Server.

The frozen ``.exe`` doubles as a one-file installer:

  1. First run (no ``server_config.json`` beside the exe) opens a setup wizard
     that installs the app to the system drive (default ``C:\\Chautara_Share_Hub``)
     and asks where to store the Public shared files.
  2. Later runs just launch the app from the install directory.

No Python or libraries are needed on the target PC.
"""
import os
import sys
import argparse
import time

# Ensure stdout and stderr exist even when packaged with --noconsole
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _get_base_dir() -> str:
    """Return the writable base directory for config, storage, and logs.

    • Normal run  → directory containing app.py (i.e. the repo root)
    • Frozen exe  → directory that contains the .exe file, so the user's data
                    lives right next to the executable and survives updates.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller sets sys.executable to the .exe path
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chautara Share Hub - Offline LAN Storage & Vault")
    parser.add_argument("--headless", action="store_true", help="Run server without desktop GUI")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind server (default: 5000)")
    parser.add_argument("--setup", action="store_true", help="Force the setup wizard (reinstall)")
    parser.add_argument("--silent", action="store_true",
                        help="Install automatically without any dialog (uses --install-dir/--public-dir)")
    parser.add_argument("--no-shortcut", action="store_true",
                        help="Skip creating a desktop shortcut during silent install")
    parser.add_argument("--install-dir", default=None, help="Install folder (default: <SystemDrive>\\Chautara_Share_Hub)")
    parser.add_argument("--public-dir", default=None, help="Where to store Public shared files")
    parser.add_argument("--vault-dir", default=None, help="Where to store the Private Vault (optional)")
    return parser.parse_args()


def _handle_setup(args: argparse.Namespace):
    """Runs the installer stage. Returns True when this process should exit."""
    from core import setup_wizard

    # --- Fully silent/scripted install (used by auto-elevation too) ---
    if args.silent:
        install_dir = args.install_dir or setup_wizard.default_install_dir()
        public_dir = args.public_dir or os.path.join(install_dir, "Shared_Storage", "Public")
        vault_dir = args.vault_dir
        installed_exe = setup_wizard.perform_install(install_dir, public_dir, vault_dir,
                                                     create_shortcut=not args.no_shortcut)
        setup_wizard.relaunch(installed_exe, headless=args.headless, port=args.port)
        return True

    # --- Interactive wizard: only for the frozen exe, on first run (or --setup) ---
    frozen = getattr(sys, "frozen", False)
    if not frozen:
        return False  # dev mode: repo already has server_config.json
    if not args.setup and not setup_wizard.running_without_config():
        return False  # already installed/configured -> normal launch

    action, _path = setup_wizard.run_wizard(headless=args.headless, port=args.port)
    # installed/cancelled -> exit this temp copy; portable -> config was written
    # next to this exe, so continue launching normally.
    return action != "portable"


def main():
    args = _parse_args()

    if _handle_setup(args):
        sys.exit(0)

    base_dir = _get_base_dir()

    from core.storage import StorageManager
    from core.setup_wizard import write_welcome_files

    storage_mgr = StorageManager(base_dir)
    write_welcome_files(storage_mgr.public_dir, storage_mgr.vault_dir)

    if args.headless:
        from core.server import ServerController
        from core.network import get_best_ip

        server_ctrl = ServerController(storage_mgr)
        success, msg = server_ctrl.start(port=args.port)
        if success:
            print("=" * 60)
            print("  CHAUTARA SHARE HUB RUNNING (HEADLESS)")
            print(f"  Access URL: http://{get_best_ip()}:{args.port}")
            print(f"  Public Path: {storage_mgr.public_dir}")
            print(f"  Vault Path:  {storage_mgr.vault_dir}")
            print("  Press Ctrl+C to stop.")
            print("=" * 60)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                server_ctrl.stop()
                print("\nServer stopped.")
        else:
            print(f"Failed to start server: {msg}")
            sys.exit(1)
    else:
        # Launch CustomTkinter GUI
        from gui.app_gui import ModernAppGUI
        app = ModernAppGUI(base_dir)
        app.mainloop()


if __name__ == "__main__":
    main()