"""Fast Thumbnail Generator for Images, Videos, PDFs, and Text Documents."""
import os
import hashlib
import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

log = logging.getLogger("thumbnail")

# Register HEIC/HEIF/AVIF decoding so Pillow can open iPhone photos.
# pillow-heif adds "heic" and "heif" to PIL.Image.open() when available.
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

class ThumbnailGenerator:
    """Generates and caches lightweight thumbnail previews for multiple file formats."""

    THUMB_SIZE = (280, 180)
    SUPPORTED_IMG = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico', '.svg',
                     '.tiff', '.tif', '.heic', '.heif', '.avif', '.apng', '.jfif'}
    SUPPORTED_VID = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'}
    SUPPORTED_PDF = {'.pdf'}
    SUPPORTED_TXT = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.csv', '.xml', '.yaml', '.yml', '.log'}

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_supported(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in (self.SUPPORTED_IMG | self.SUPPORTED_VID | self.SUPPORTED_PDF | self.SUPPORTED_TXT)

    def get_cache_path(self, filepath: str) -> str:
        stat = os.stat(filepath)
        key = f"{filepath}_{stat.st_mtime}_{stat.st_size}"
        filename = hashlib.md5(key.encode('utf-8')).hexdigest() + ".jpg"
        return os.path.join(self.cache_dir, filename)

    def generate_thumbnail(self, filepath: str) -> Optional[str]:
        """Generates or retrieves cached thumbnail for the file. Returns path to JPEG image."""
        if not os.path.isfile(filepath):
            return None

        ext = os.path.splitext(filepath)[1].lower()
        if not self.is_supported(filepath):
            return None

        cache_path = self.get_cache_path(filepath)
        if os.path.exists(cache_path):
            return cache_path

        try:
            if ext in self.SUPPORTED_IMG:
                if ext == '.svg':
                    # Browsers render SVG natively; we serve the original file
                    # instead of rasterizing it (Pillow needs an external loader).
                    return None
                return self._generate_image_thumb(filepath, cache_path)
            elif ext in self.SUPPORTED_PDF:
                return self._generate_pdf_thumb(filepath, cache_path)
            elif ext in self.SUPPORTED_VID:
                return self._generate_video_thumb(filepath, cache_path)
            elif ext in self.SUPPORTED_TXT:
                return self._generate_text_thumb(filepath, cache_path)
        except Exception as e:
            # Silent on formats we intentionally cannot rasterize (e.g. HEIC
            # without pillow-heif installed) — the caller falls back to the
            # original file or a file icon.
            log.debug("Thumbnail generation skipped for %s: %s", filepath, e)

        return None

    def _generate_image_thumb(self, src: str, dest: str) -> Optional[str]:
        try:
            with Image.open(src) as img:
                # Apply EXIF orientation so phone/camera photos render upright
                img = ImageOps.exif_transpose(img) or img
                img = img.convert('RGB')
                img.thumbnail(self.THUMB_SIZE, Image.Resampling.LANCZOS)
                img.save(dest, format='JPEG', quality=82)
            return dest
        except Exception:
            return None

    def _generate_pdf_thumb(self, src: str, dest: str) -> Optional[str]:
        try:
            import fitz
            doc = fitz.open(src)
            if len(doc) == 0:
                return None
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=90)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail(self.THUMB_SIZE, Image.Resampling.LANCZOS)
            img.save(dest, format='JPEG', quality=82)
            doc.close()
            return dest
        except Exception:
            return None

    def _generate_video_thumb(self, src: str, dest: str) -> Optional[str]:
        try:
            import cv2
            cap = cv2.VideoCapture(src)
            # Try capturing around frame 20 or 1 sec
            cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
            cap.release()

            if success and frame is not None:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                img.thumbnail(self.THUMB_SIZE, Image.Resampling.LANCZOS)
                img.save(dest, format='JPEG', quality=82)
                return dest
        except Exception:
            pass
        return None

    def _generate_text_thumb(self, src: str, dest: str) -> Optional[str]:
        try:
            # Read first few lines of text
            lines = []
            with open(src, 'r', encoding='utf-8', errors='ignore') as f:
                for _ in range(8):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.rstrip())

            content = "\n".join(lines) if lines else "Empty File"
            if len(content) > 300:
                content = content[:300] + "..."

            # Create stylish dark canvas with header bar
            width, height = self.THUMB_SIZE
            img = Image.new('RGB', (width, height), color='#0f172a')
            draw = ImageDraw.Draw(img)

            # Draw header bar
            draw.rectangle([(0, 0), (width, 24)], fill='#1e293b')
            # 3 decorative window dots
            draw.ellipse([(8, 8), (14, 14)], fill='#ef4444')
            draw.ellipse([(18, 8), (24, 14)], fill='#f59e0b')
            draw.ellipse([(28, 8), (34, 14)], fill='#10b981')

            # Draw text content
            ext = os.path.splitext(src)[1].upper()
            draw.text((42, 6), f"{ext} FILE", fill='#94a3b8')
            draw.text((12, 34), content, fill='#38bdf8')

            img.save(dest, format='JPEG', quality=80)
            return dest
        except Exception:
            return None
