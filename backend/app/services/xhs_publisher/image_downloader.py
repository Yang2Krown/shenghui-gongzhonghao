"""
Image downloader for Xiaohongshu publishing.
Adapted from post-to-xhs skill.
"""

import os
import tempfile
import shutil
import uuid
from urllib.parse import urlparse, unquote

import requests

DEFAULT_TIMEOUT = 30
TEMP_DIR_PREFIX = "xhs_images_"


class ImageDownloader:
    def __init__(self, temp_dir: str = None):
        if temp_dir:
            self.temp_dir = temp_dir
            os.makedirs(self.temp_dir, exist_ok=True)
            self._owns_dir = False
        else:
            self.temp_dir = tempfile.mkdtemp(prefix=TEMP_DIR_PREFIX)
            self._owns_dir = True
        self.downloaded_files: list = []

    def _guess_extension(self, url: str, content_type: str = "") -> str:
        path = urlparse(url).path
        _, ext = os.path.splitext(unquote(path))
        if ext and ext.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            return ext.lower()
        ct_map = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}
        if content_type:
            for mime, e in ct_map.items():
                if mime in content_type:
                    return e
        return ".jpg"

    def download(self, url: str, referer: str = None) -> str:
        parsed = urlparse(url)
        if referer is None:
            referer = f"{parsed.scheme}://{parsed.netloc}/"
        headers = {
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT, stream=True, headers=headers)
        resp.raise_for_status()
        ext = self._guess_extension(url, resp.headers.get("Content-Type"))
        filename = f"{uuid.uuid4().hex[:12]}{ext}"
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        self.downloaded_files.append(filepath)
        return filepath

    def download_all(self, urls: list) -> list:
        paths = []
        for url in urls:
            try:
                path = self.download(url)
                paths.append(path)
            except Exception as e:
                print(f"[image_downloader] Failed to download {url}: {e}")
        return paths

    def cleanup(self):
        if self._owns_dir and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        else:
            for f in self.downloaded_files:
                try:
                    os.remove(f)
                except OSError:
                    pass
        self.downloaded_files.clear()
