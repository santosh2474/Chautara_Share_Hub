# Chautara Share Hub 🏫🌐🔒

<div align="center">
  <img src="web/static/img/chautara_logo.jpg" alt="Shree Chautara Secondary School Logo" width="130" style="border-radius: 12px; margin-bottom: 12px;" />
  <h3>श्री चौतारा माध्यमिक विद्यालय (१-१२)</h3>
  <p><strong>सुनकोशी गाउँपालिका-५, डाँडाखर्क, ओखलढुङ्गा, कोशी प्रदेश, नेपाल</strong></p>
  <p><em>Local Network Offline File Sharing & Security Vault System</em></p>
</div>

---

A modern, responsive, high-speed file sharing system built in Python for cross-device local network transfers. Connects Windows PCs, Macs, Linux, iPhones, iPads, and Android phones across your local Wi-Fi, Ethernet, or Mobile Hotspot with **zero internet required**.

---

## 🌟 Key Highlights

- **🖥️ Attractive Admin Desktop GUI**: Built using **CustomTkinter** with a modern dark/light card interface and school branding.
- **📱 Instant Mobile Camera Connect**: Generates a high-definition **QR Code** directly inside the desktop dashboard. Mobile users can simply scan the QR code to connect immediately without typing IP addresses.
- **⚡ 100% Offline LAN Operation**: Completely self-contained web portal with inlined SVG icons and responsive CSS/JS. Operates seamlessly on local Wi-Fi, LAN, or Mobile Hotspot even with no active internet connection.
- **🔐 Admin Password-Protected Private Vault**: Encrypted SHA-256 password protection for sensitive files with strict per-visit re-authentication.
- **🖼️ Visual Thumbnails & File Icon Previews**: Live visual thumbnails generated on-the-fly for images, videos, PDFs, and code/text documents, allowing instant file identification without opening.
- **💾 1-Click USB External Drive Sharing & Copy-to-Drive**: Auto-detects inserted USB flash drives and external hard drives with capacity meters, allows 1-click network sharing, and enables direct copying from Public/Vault to any connected Drive.
- **🎥 In-Browser Media Player & Streaming**: Streams videos (MP4, MKV, WebM) with HTTP 206 partial content range seeking, audio tracks with visual controls, image lightbox viewer, text/code viewer, and PDF reader.
- **📦 Drag-and-Drop Batch Uploads & ZIP Downloads**: Upload multiple files simultaneously with real-time percentage progress bars, or download entire folders packaged as ZIP files.

---

## 📂 Project Structure

```
current_working/
├── app.py                      # Main entrypoint (GUI or Headless)
├── server_config.json          # Persistent server settings and vault hash
├── requirements.txt            # Python dependencies
├── core/
│   ├── network.py              # IP discovery, adapters, and QR code generator
│   ├── storage.py              # Storage manager for Public, Vault, and USB
│   ├── thumbnail.py            # High-performance thumbnail generator (images, videos, PDFs, docs)
│   ├── usb_detector.py         # USB/removable drive detection & volume info
│   └── server.py               # Flask multithreaded streaming server & API
├── gui/
│   └── app_gui.py              # CustomTkinter Desktop Admin Control Panel with School Logo
├── web/
│   ├── templates/
│   │   └── index.html          # Mobile-first responsive web portal
│   └── static/
│       ├── css/style.css       # Sleek Glassmorphism styles & thumbnail layouts
│       ├── js/app.js           # Client-side reactivity & offline file manager
│       └── img/                # School logo and branding assets
├── Shared_Storage/
│   ├── Public/                 # Shared public folder for all network devices
│   └── Vault/                  # Password-protected admin vault
└── tests/
    └── test_server_api.py      # Automated unit and security test suite
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Desktop Application
```bash
python app.py
```
This opens the **Antigravity Share Hub GUI**:
1. Click **"Start Server"**.
2. Point your smartphone camera at the **QR Code** on screen to open the web portal.
3. Or copy the generated URL (e.g. `http://192.168.1.15:5000`) and paste it into any web browser on your network.

### 3. Run in Headless / Server Mode (No GUI)
If you want to run the server in a terminal or background service without opening the desktop GUI window:
```bash
python app.py --headless --port 5000
```

### 4. End-User (Students & Teachers) — One-File Installer
For non-technical users, ship `setup\Chautara_Share_Hub.exe` (a 100% standalone
installer + app). Double-clicking it opens a **normal step-by-step Windows installer**:
- uses a responsive, resizable setup window,
- installs to `C:\Program Files\Chautara Share Hub` (asks for the folder),
- asks where to store Public shared files and the Private Vault,
- creates **Desktop / Start Menu shortcuts** and an **Uninstall** shortcut,
- registers in **Settings → Apps → Chautara Share Hub** so it can be
  uninstalled from **Control Panel → Programs and Features**.

See `setup/README.md` for the full install/uninstall guide.

---

## 🔒 Private Vault Credentials
- **Default Master Password**: `admin123`
- You can change the master password anytime in the desktop GUI under the **"Folders & Vault"** tab.

---

## 💾 Sharing USB Drives
1. Plug your USB Flash Drive or External Hard Drive into your PC.
2. In the desktop GUI, navigate to the **"USB Drives"** tab.
3. Click **"Scan Drives"** (or it detects automatically).
4. Switch the toggle to **"Share on Network"**.
5. Optionally enable/disable **"Read-Only Mode"** depending on whether guests should be allowed to upload files to your USB drive.

---

## 🧪 Running Automated Tests
Run the integration test suite to verify server endpoints, media streaming, folder archiving, and vault security:
```bash
python tests/test_server_api.py
```

---

## 👨‍💻 Developer
<div align="center">
  <p><strong>Developed By: Er. Santosh Thakur</strong></p>
  <p>Contact No.: +977-9804743283 &nbsp;•&nbsp; Mail Id.: info@santoshthakur.info.np</p>
  <p>Website: <a href="https://www.santoshthakur.info.np">www.santoshthakur.info.np</a></p>
</div>
