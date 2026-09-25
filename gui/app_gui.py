"""Modern CustomTkinter GUI Desktop Dashboard for Network Share & Vault."""
import os
import sys
import webbrowser
import threading
from datetime import datetime
import customtkinter as ctk
from PIL import Image

from core.network import get_network_interfaces, get_best_ip, generate_qr_image, is_port_available
from core.storage import StorageManager
from core.usb_detector import scan_drives
from core.server import ServerController

# Set default theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ModernAppGUI(ctk.CTk):
    """Admin Control Panel for Network File Sharing & Security Vault."""

    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        self.title("Chautara Share Hub - LAN Hub & Security Vault")
        self.geometry("980x700")
        self.minsize(880, 620)

        # Core Engines
        self.storage_mgr = StorageManager(self.base_dir)
        self.server_ctrl = ServerController(self.storage_mgr, log_callback=self.thread_safe_log)

        # State Variables
        self.interfaces = get_network_interfaces()
        self.selected_ip = ctk.StringVar(value=get_best_ip())
        self.port_var = ctk.StringVar(value=str(self.storage_mgr.config.get("server_port", 5000)))
        self.server_url_var = ctk.StringVar(value="Server Stopped")
        self.server_status_var = ctk.StringVar(value="OFFLINE")
        self.allow_pub_upload_var = ctk.BooleanVar(value=self.storage_mgr.config.get("allow_public_upload", True))
        self.allow_vault_upload_var = ctk.BooleanVar(value=self.storage_mgr.config.get("allow_vault_upload", True))

        # Build UI Layout
        self._create_layout()

        # Update initial states
        self._update_url_label()
        self._update_qr_code()
        self.refresh_usb_list()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_layout(self):
        # Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Sidebar Navigation
        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Logo / Brand
        _asset_root = getattr(sys, "_MEIPASS", self.base_dir)
        logo_path = os.path.join(_asset_root, "web", "static", "img", "chautara_logo.jpg")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(self.base_dir, "web", "static", "img", "chautara_logo.jpg")
        if os.path.exists(logo_path):
            try:
                pil_logo = Image.open(logo_path).convert("RGB")
                self.sidebar_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(76, 76))
                self.logo_img_label = ctk.CTkLabel(self.sidebar, text="", image=self.sidebar_logo_img)
                self.logo_img_label.grid(row=0, column=0, padx=20, pady=(16, 6))
            except Exception:
                pass

        self.logo_label = ctk.CTkLabel(
            self.sidebar,
            text="Chautara Share Hub",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.logo_label.grid(row=1, column=0, padx=10, pady=(0, 2))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar,
            text="School LAN & Vault",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.subtitle_label.grid(row=2, column=0, padx=20, pady=(0, 16))

        # Nav Buttons
        self.btn_nav_dashboard = ctk.CTkButton(
            self.sidebar, text="Dashboard", command=lambda: self.switch_tab("dashboard"),
            fg_color="#1f538d", height=36
        )
        self.btn_nav_dashboard.grid(row=3, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_usb = ctk.CTkButton(
            self.sidebar, text="USB Drives", command=lambda: self.switch_tab("usb"),
            fg_color="transparent", text_color=("gray10", "gray90"), height=36
        )
        self.btn_nav_usb.grid(row=4, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_vault = ctk.CTkButton(
            self.sidebar, text="Folders & Vault", command=lambda: self.switch_tab("vault"),
            fg_color="transparent", text_color=("gray10", "gray90"), height=36
        )
        self.btn_nav_vault.grid(row=5, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_logs = ctk.CTkButton(
            self.sidebar, text="Activity Logs", command=lambda: self.switch_tab("logs"),
            fg_color="transparent", text_color=("gray10", "gray90"), height=36
        )
        self.btn_nav_logs.grid(row=6, column=0, padx=15, pady=6, sticky="new")

        # Sidebar Footer
        self.theme_switch = ctk.CTkSwitch(
            self.sidebar, text="Dark Mode", command=self.toggle_theme
        )
        self.theme_switch.select()
        self.theme_switch.grid(row=7, column=0, padx=20, pady=(20, 2), sticky="s")

        self.developer_label = ctk.CTkLabel(
            self.sidebar,
            text="Developed By: Er. Santosh Thakur\n"
                 "Contact No.: +977-9804743283\n"
                 "Mail Id.: info@santoshthakur.info.np",
            font=ctk.CTkFont(size=9),
            text_color="gray",
            justify="center"
        )
        self.developer_label.grid(row=8, column=0, padx=10, pady=(0, 4), sticky="s")

        self.website_label = ctk.CTkLabel(
            self.sidebar,
            text="www.santoshthakur.info.np",
            font=ctk.CTkFont(size=9, underline=True),
            text_color="#38bdf8",
            cursor="hand2",
            justify="center"
        )
        self.website_label.grid(row=9, column=0, padx=10, pady=(0, 8), sticky="s")
        self.website_label.bind("<Button-1>",
                                lambda e: webbrowser.open("https://www.santoshthakur.info.np"))

        # Main Content Container
        self.content_area = ctk.CTkFrame(self, corner_radius=12)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        # Tab Frames
        self.tabs = {
            "dashboard": self._create_dashboard_tab(),
            "usb": self._create_usb_tab(),
            "vault": self._create_vault_tab(),
            "logs": self._create_logs_tab()
        }

        self.switch_tab("dashboard")

    def switch_tab(self, tab_key: str):
        """Switches active frame in the content area."""
        for name, frame in self.tabs.items():
            frame.grid_forget()

        self.tabs[tab_key].grid(row=0, column=0, sticky="nsew")

        # Update button highlights
        buttons = {
            "dashboard": self.btn_nav_dashboard,
            "usb": self.btn_nav_usb,
            "vault": self.btn_nav_vault,
            "logs": self.btn_nav_logs
        }
        for name, btn in buttons.items():
            if name == tab_key:
                btn.configure(fg_color="#1f538d", text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    # -------------------------------------------------------------
    # TAB 1: DASHBOARD
    # -------------------------------------------------------------
    def _create_dashboard_tab(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(2, weight=1)

        # Top Banner: Status & Toggle
        banner = ctk.CTkFrame(frame, corner_radius=10)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        banner.grid_columnconfigure(1, weight=1)

        self.status_badge = ctk.CTkLabel(
            banner, text="● SERVER OFFLINE",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ef4444"
        )
        self.status_badge.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.btn_toggle_server = ctk.CTkButton(
            banner, text="Start Server", command=self.toggle_server,
            fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(size=14, weight="bold"),
            width=140, height=38
        )
        self.btn_toggle_server.grid(row=0, column=2, padx=20, pady=15, sticky="e")

        # Left Column: Network Settings & URL Links
        settings_card = ctk.CTkFrame(frame, corner_radius=10)
        settings_card.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 12))
        settings_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            settings_card, text="Network Configuration",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 12), sticky="w")

        # Network Adapter / IP
        ctk.CTkLabel(settings_card, text="Network IP:").grid(row=1, column=0, padx=16, pady=8, sticky="w")
        ip_options = [f"{iface['ip']} ({iface['name']})" for iface in self.interfaces]
        self.ip_menu = ctk.CTkOptionMenu(
            settings_card, values=ip_options, command=self.on_ip_selected
        )
        self.ip_menu.grid(row=1, column=1, padx=16, pady=8, sticky="ew")

        # Port
        ctk.CTkLabel(settings_card, text="Port:").grid(row=2, column=0, padx=16, pady=8, sticky="w")
        self.port_entry = ctk.CTkEntry(settings_card, textvariable=self.port_var, width=100)
        self.port_entry.grid(row=2, column=1, padx=16, pady=8, sticky="w")
        self.port_entry.bind("<KeyRelease>", lambda e: self.on_port_changed())

        # Live Link
        ctk.CTkLabel(settings_card, text="Access Link:").grid(row=3, column=0, padx=16, pady=12, sticky="w")
        self.url_display = ctk.CTkEntry(
            settings_card, textvariable=self.server_url_var, state="readonly"
        )
        self.url_display.grid(row=3, column=1, padx=16, pady=12, sticky="ew")

        # Action Buttons for URL
        btn_box = ctk.CTkFrame(settings_card, fg_color="transparent")
        btn_box.grid(row=4, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        btn_box.grid_columnconfigure((0, 1), weight=1)

        self.btn_copy_url = ctk.CTkButton(
            btn_box, text="Copy Link", command=self.copy_server_url,
            fg_color="#334155", hover_color="#475569"
        )
        self.btn_copy_url.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.btn_open_browser = ctk.CTkButton(
            btn_box, text="Open in Browser", command=self.open_in_browser,
            fg_color="#0284c7", hover_color="#0369a1"
        )
        self.btn_open_browser.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # Right Column: QR Code Card
        qr_card = ctk.CTkFrame(frame, corner_radius=10)
        qr_card.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        qr_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            qr_card, text="Mobile Quick Connect",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(16, 6))

        ctk.CTkLabel(
            qr_card, text="Scan with smartphone camera to connect",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=1, column=0, padx=16, pady=(0, 10))

        self.qr_label = ctk.CTkLabel(qr_card, text="")
        self.qr_label.grid(row=2, column=0, padx=16, pady=10)

        # Bottom Mini Log Area
        bottom_frame = ctk.CTkFrame(frame, corner_radius=10)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            bottom_frame, text="Live Activity Feed",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(10, 4), sticky="w")

        self.mini_log = ctk.CTkTextbox(bottom_frame, height=130)
        self.mini_log.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="nsew")

        return frame

    # -------------------------------------------------------------
    # TAB 2: USB DRIVES & EXTERNAL STORAGE
    # -------------------------------------------------------------
    def _create_usb_tab(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="External USB & Storage Sharing",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Scan Drives", command=self.refresh_usb_list,
            width=120
        ).grid(row=0, column=1, sticky="e")

        self.usb_scroll_frame = ctk.CTkScrollableFrame(frame, corner_radius=10)
        self.usb_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.usb_scroll_frame.grid_columnconfigure(0, weight=1)

        return frame

    def refresh_usb_list(self):
        """Scans system drives and populates the USB Sharing tab."""
        for widget in self.usb_scroll_frame.winfo_children():
            widget.destroy()

        drives = scan_drives()
        if not drives:
            ctk.CTkLabel(
                self.usb_scroll_frame, text="No drives detected.",
                font=ctk.CTkFont(size=14), text_color="gray"
            ).pack(pady=40)
            return

        shared_drives = self.storage_mgr.config.get("shared_usb_drives", {})

        for d in drives:
            card = ctk.CTkFrame(self.usb_scroll_frame, corner_radius=8)
            card.pack(fill="x", padx=6, pady=6)
            card.grid_columnconfigure(1, weight=1)

            # Icon & Title
            icon_tag = " [USB]" if d["is_removable"] else (" [SYS]" if d["is_system"] else " [DISK]")
            title_text = f"{d['mountpoint']} - {d['label']}{icon_tag}"
            
            ctk.CTkLabel(
                card, text=title_text,
                font=ctk.CTkFont(size=14, weight="bold")
            ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 2), sticky="w")

            # Capacity details
            sub_text = f"Capacity: {d['used_str']} used / {d['total_str']} total ({d['free_str']} free)"
            ctk.CTkLabel(
                card, text=sub_text,
                font=ctk.CTkFont(size=12), text_color="gray"
            ).grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")

            # Controls Box
            controls = ctk.CTkFrame(card, fg_color="transparent")
            controls.grid(row=2, column=0, columnspan=2, padx=14, pady=(4, 10), sticky="ew")
            controls.grid_columnconfigure(2, weight=1)

            key = d["mountpoint"].replace(":", "").replace("\\", "").replace("/", "").lower()
            is_shared = key in shared_drives
            allow_upload = not shared_drives.get(key, {}).get("read_only", False) if is_shared else True

            share_switch = ctk.CTkSwitch(
                controls, text="Share on Network",
                command=lambda d_info=d: self.on_toggle_drive_share(d_info)
            )
            if is_shared:
                share_switch.select()
            share_switch.grid(row=0, column=0, padx=(0, 16), sticky="w")

            upload_switch = ctk.CTkSwitch(
                controls, text="Allow File Uploads",
                command=lambda d_info=d: self.on_toggle_drive_upload(d_info)
            )
            if allow_upload:
                upload_switch.select()
            upload_switch.grid(row=0, column=1, padx=10, sticky="w")

            # Open in explorer
            ctk.CTkButton(
                controls, text="Open Drive", width=90, height=28,
                fg_color="#334155", hover_color="#475569",
                command=lambda p=d["mountpoint"]: self.open_folder_in_os(p)
            ).grid(row=0, column=3, padx=(10, 0), sticky="e")

    def on_toggle_drive_share(self, d_info: dict):
        key = d_info["mountpoint"].replace(":", "").replace("\\", "").replace("/", "").lower()
        shared_drives = self.storage_mgr.config.get("shared_usb_drives", {})
        now_shared = key in shared_drives
        
        # When enabling, default read_only=False so users can upload files to drives
        self.storage_mgr.set_usb_share(
            drive_mount=d_info["mountpoint"],
            label=d_info["label"],
            enabled=not now_shared,
            read_only=False
        )
        self.thread_safe_log(f"[CONFIG] USB Drive {d_info['mountpoint']} sharing: {not now_shared} (Uploads: Enabled)")
        self.refresh_usb_list()

    def on_toggle_drive_upload(self, d_info: dict):
        key = d_info["mountpoint"].replace(":", "").replace("\\", "").replace("/", "").lower()
        shared_drives = self.storage_mgr.config.get("shared_usb_drives", {})
        if key in shared_drives:
            current_ro = shared_drives[key].get("read_only", False)
            self.storage_mgr.set_usb_share(
                drive_mount=d_info["mountpoint"],
                label=d_info["label"],
                enabled=True,
                read_only=not current_ro
            )
            self.thread_safe_log(f"[CONFIG] USB Drive {d_info['mountpoint']} allow uploads: {current_ro}")

    # -------------------------------------------------------------
    # TAB 3: FOLDERS & SECURITY VAULT
    # -------------------------------------------------------------
    def _create_vault_tab(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        # Public Folder Config
        pub_card = ctk.CTkFrame(frame, corner_radius=10)
        pub_card.pack(fill="x", padx=12, pady=12)
        pub_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            pub_card, text="Public Shared Folder",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 6), sticky="w")

        ctk.CTkLabel(pub_card, text=f"Path: {self.storage_mgr.public_dir}").grid(
            row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w"
        )

        ctk.CTkCheckBox(
            pub_card, text="Allow network users to upload files to Public folder",
            variable=self.allow_pub_upload_var, command=self.on_pub_upload_changed
        ).grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            pub_card, text="Open in Windows Explorer", width=160,
            command=lambda: self.open_folder_in_os(self.storage_mgr.public_dir)
        ).grid(row=2, column=1, padx=16, pady=(0, 14), sticky="e")

        # Private Vault Config
        vault_card = ctk.CTkFrame(frame, corner_radius=10)
        vault_card.pack(fill="x", padx=12, pady=(0, 12))
        vault_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            vault_card, text="Private Security Vault",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 6), sticky="w")

        ctk.CTkLabel(vault_card, text=f"Path: {self.storage_mgr.vault_dir}").grid(
            row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w"
        )

        ctk.CTkLabel(
            vault_card, text="Admin Master Password:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=2, column=0, padx=16, pady=8, sticky="w")

        pw_box = ctk.CTkFrame(vault_card, fg_color="transparent")
        pw_box.grid(row=2, column=1, padx=16, pady=8, sticky="ew")
        pw_box.grid_columnconfigure(0, weight=1)

        self.vault_pw_entry = ctk.CTkEntry(pw_box, placeholder_text="Enter new master password", show="*")
        self.vault_pw_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        ctk.CTkButton(
            pw_box, text="Save Password", width=120, command=self.save_vault_password
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkCheckBox(
            vault_card, text="Allow authenticated users to upload files to Vault",
            variable=self.allow_vault_upload_var, command=self.on_vault_upload_changed
        ).grid(row=3, column=0, padx=16, pady=(10, 16), sticky="w")

        ctk.CTkButton(
            vault_card, text="Open Vault in Explorer", width=160,
            command=lambda: self.open_folder_in_os(self.storage_mgr.vault_dir)
        ).grid(row=3, column=1, padx=16, pady=(10, 16), sticky="e")

        return frame

    def on_pub_upload_changed(self):
        self.storage_mgr.config["allow_public_upload"] = self.allow_pub_upload_var.get()
        self.storage_mgr.save_config()
        self.thread_safe_log(f"[CONFIG] Public uploads: {self.allow_pub_upload_var.get()}")

    def on_vault_upload_changed(self):
        self.storage_mgr.config["allow_vault_upload"] = self.allow_vault_upload_var.get()
        self.storage_mgr.save_config()
        self.thread_safe_log(f"[CONFIG] Vault uploads: {self.allow_vault_upload_var.get()}")

    def save_vault_password(self):
        new_pw = self.vault_pw_entry.get().strip()
        if not new_pw:
            self.thread_safe_log("[WARNING] Password cannot be empty.")
            return
        self.storage_mgr.set_vault_password(new_pw)
        self.vault_pw_entry.delete(0, "end")
        self.thread_safe_log("[SECURITY] Vault master password updated successfully.")

    # -------------------------------------------------------------
    # TAB 4: LIVE ACTIVITY LOGS
    # -------------------------------------------------------------
    def _create_logs_tab(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Detailed Activity & Transfer Logs",
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="Clear Logs", width=100, command=self.clear_logs
        ).grid(row=0, column=1, sticky="e")

        self.full_log = ctk.CTkTextbox(frame)
        self.full_log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        return frame

    def clear_logs(self):
        self.full_log.delete("1.0", "end")
        self.mini_log.delete("1.0", "end")

    # -------------------------------------------------------------
    # Server & Event Handlers
    # -------------------------------------------------------------
    def toggle_server(self):
        if self.server_ctrl.is_active:
            # Stop
            success, msg = self.server_ctrl.stop()
            self.status_badge.configure(text="● SERVER OFFLINE", text_color="#ef4444")
            self.btn_toggle_server.configure(text="Start Server", fg_color="#10b981", hover_color="#059669")
            self.server_url_var.set("Server Stopped")
        else:
            # Start
            port = int(self.port_var.get())
            if not is_port_available(port):
                self.thread_safe_log(f"[ERROR] Port {port} is already in use by another application.")
                return

            success, msg = self.server_ctrl.start(port=port)
            if success:
                self.status_badge.configure(text="● SERVER LIVE", text_color="#10b981")
                self.btn_toggle_server.configure(text="Stop Server", fg_color="#ef4444", hover_color="#dc2626")
                self._update_url_label()
                self._update_qr_code()
            else:
                self.thread_safe_log(f"[ERROR] {msg}")

    def on_ip_selected(self, choice: str):
        # Extract IP from '192.168.1.15 (Wi-Fi)'
        ip = choice.split(" ")[0]
        self.selected_ip.set(ip)
        self._update_url_label()
        self._update_qr_code()

    def on_port_changed(self):
        self._update_url_label()
        self._update_qr_code()

    def _update_url_label(self):
        ip = self.selected_ip.get()
        port = self.port_var.get()
        if self.server_ctrl.is_active:
            url = f"http://{ip}:{port}"
            self.server_url_var.set(url)
        else:
            self.server_url_var.set("Server Stopped")

    def _update_qr_code(self):
        ip = self.selected_ip.get()
        port = self.port_var.get()
        url = f"http://{ip}:{port}"
        try:
            pil_img = generate_qr_image(url, box_size=5, border=1)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(170, 170))
            self.qr_label.configure(image=ctk_img)
            self.qr_label.image = ctk_img
        except Exception as e:
            print(f"Error rendering QR image: {e}")

    def copy_server_url(self):
        url = self.server_url_var.get()
        if "http" in url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.thread_safe_log(f"[INFO] Copied {url} to clipboard.")

    def open_in_browser(self):
        url = self.server_url_var.get()
        if "http" in url:
            webbrowser.open(url)

    def open_folder_in_os(self, folder_path: str):
        if os.path.exists(folder_path):
            os.startfile(folder_path)

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

    def thread_safe_log(self, text: str):
        """Dispatches log insertion to the Tkinter main thread."""
        self.after(0, self._append_log, text)

    def _append_log(self, text: str):
        line = text.strip() + "\n"
        if hasattr(self, 'mini_log'):
            self.mini_log.insert("end", line)
            self.mini_log.see("end")
        if hasattr(self, 'full_log'):
            self.full_log.insert("end", line)
            self.full_log.see("end")

    def on_close(self):
        """Cleanup server on exit."""
        if self.server_ctrl.is_active:
            self.server_ctrl.stop()
        self.destroy()
        sys.exit(0)
