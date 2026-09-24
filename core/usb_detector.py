"""USB and External Drive Detection Module for Windows and Cross-Platform."""
import os
import platform
import psutil

# Windows Drive Type Constants
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

def get_drive_volume_name(drive_path: str) -> str:
    """Returns the volume label for a drive on Windows, or basename on UNIX."""
    if platform.system() == "Windows":
        try:
            import ctypes
            volume_buf = ctypes.create_unicode_buffer(1024)
            fs_buf = ctypes.create_unicode_buffer(1024)
            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_path),
                volume_buf,
                ctypes.sizeof(volume_buf),
                None, None, None,
                fs_buf,
                ctypes.sizeof(fs_buf)
            )
            if res and volume_buf.value:
                return volume_buf.value
        except Exception:
            pass
    return os.path.basename(drive_path.rstrip("/\\")) or drive_path

def get_drive_type_code(drive_path: str) -> int:
    """Returns the Windows drive type code or fallback."""
    if platform.system() == "Windows":
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(drive_path)
        except Exception:
            pass
    return DRIVE_FIXED

def format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string (MB, GB, TB)."""
    if num_bytes is None or num_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"

def scan_drives():
    """
    Scans and returns all available drives and partitions.
    Marks external / removable USB drives prominently.
    """
    drives = []
    try:
        partitions = psutil.disk_partitions(all=False)
        for p in partitions:
            mount = p.mountpoint
            try:
                usage = psutil.disk_usage(mount)
            except (PermissionError, OSError):
                continue

            type_code = get_drive_type_code(mount)
            is_removable = (type_code == DRIVE_REMOVABLE) or ("removable" in p.opts.lower())
            is_cdrom = (type_code == DRIVE_CDROM) or ("cdrom" in p.opts.lower())
            
            # Skip optical drives with no media
            if is_cdrom and usage.total == 0:
                continue

            vol_label = get_drive_volume_name(mount)
            if not vol_label:
                if is_removable:
                    vol_label = "USB Flash Drive"
                else:
                    vol_label = f"Local Disk ({mount[0] if len(mount) > 0 else 'Disk'})"

            free_pct = round((usage.free / usage.total) * 100, 1) if usage.total > 0 else 0
            used_pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0

            drives.append({
                "device": p.device,
                "mountpoint": mount,
                "fstype": p.fstype,
                "opts": p.opts,
                "label": vol_label,
                "is_removable": is_removable,
                "is_system": mount.upper().startswith("C:"),
                "total_bytes": usage.total,
                "free_bytes": usage.free,
                "used_bytes": usage.used,
                "total_str": format_bytes(usage.total),
                "free_str": format_bytes(usage.free),
                "used_str": format_bytes(usage.used),
                "used_percent": used_pct,
                "free_percent": free_pct,
            })
    except Exception as e:
        print(f"Error scanning drives: {e}")

    return drives
