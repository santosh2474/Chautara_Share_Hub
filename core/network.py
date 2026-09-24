"""Core network utilities for IP discovery and QR code generation."""
import socket
import io
import base64
import psutil
import qrcode
from PIL import Image

def get_network_interfaces():
    """
    Returns a list of dicts with interface names and IPv4 addresses.
    Prioritizes active Wi-Fi and Ethernet adapters.
    """
    interfaces = []
    seen_ips = set()
    
    # 1. Primary socket connect method to find the default gateway route IP
    primary_ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Connect to a dummy external IP; does not actually send packets
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        primary_ip = None

    if primary_ip and not primary_ip.startswith("127."):
        interfaces.append({
            "name": "Default Gateway Route",
            "ip": primary_ip,
            "is_primary": True
        })
        seen_ips.add(primary_ip)

    # 2. Enumerate all system network adapters via psutil
    try:
        net_addrs = psutil.net_if_addrs()
        net_stats = psutil.net_if_stats()
        
        for iface_name, addrs in net_addrs.items():
            stats = net_stats.get(iface_name)
            is_up = stats.isup if stats else True
            if not is_up:
                continue

            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if ip.startswith("127.") or ip.startswith("169.254."):
                        continue  # Skip loopback and link-local apipa
                    if ip in seen_ips:
                        continue
                    
                    seen_ips.add(ip)
                    interfaces.append({
                        "name": iface_name,
                        "ip": ip,
                        "is_primary": (ip == primary_ip)
                    })
    except Exception:
        pass

    # Fallback to localhost if no LAN interface detected
    if not interfaces:
        interfaces.append({
            "name": "Localhost (Loopback)",
            "ip": "127.0.0.1",
            "is_primary": True
        })

    return interfaces

def get_best_ip():
    """Returns the most recommended LAN IPv4 address."""
    interfaces = get_network_interfaces()
    for iface in interfaces:
        if iface.get("is_primary"):
            return iface["ip"]
    return interfaces[0]["ip"]

def is_port_available(port, host="0.0.0.0"):
    """Check if the given port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, int(port)))
            return True
        except OSError:
            return False

def generate_qr_image(url: str, box_size: int = 8, border: int = 2) -> Image.Image:
    """Generate a high-quality PIL Image containing the QR Code for the given URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF").convert("RGB")
    return img

def generate_qr_base64(url: str) -> str:
    """Generate QR code as base64 string for embedding in HTML or JSON."""
    img = generate_qr_image(url, box_size=6, border=2)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
