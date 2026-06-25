"""Background HTTP server to serve generated images to Lagrange via URL.

Lagrange (Node.js OneBot impl) can't reliably read local file paths on
Windows (retcode 1200 = file not found). Serving images via a local HTTP
endpoint bypasses this — Lagrange downloads them like any remote URL.
"""
from __future__ import annotations

import logging
import os
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

logger = logging.getLogger("qq_bot.utils.image_server")

_server: HTTPServer | None = None
_port: int = 18900
_base_url: str = ""


def _get_handler(directory: str):
    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt, *args):
            logger.debug(f"ImageServer: {fmt % args}")

    return _Handler


def start(port: int, image_dir: str) -> str:
    """Start the image HTTP server in a daemon thread.

    Returns the base URL (e.g. ``http://127.0.0.1:18900``).
    """
    global _server, _port, _base_url

    _port = port
    _base_url = f"http://127.0.0.1:{port}"

    os.makedirs(image_dir, exist_ok=True)

    _server = HTTPServer(("127.0.0.1", port), _get_handler(image_dir))
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()

    logger.info(f"Image server started at {_base_url} serving {image_dir}")
    return _base_url


def stop():
    """Shut down the image server."""
    global _server
    if _server is not None:
        _server.shutdown()
        _server = None


def url_for(filename: str) -> str:
    """Build the public HTTP URL for a file served from the image directory."""
    return f"{_base_url}/{filename}"
