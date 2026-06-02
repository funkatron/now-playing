"""Stdlib HTTP server for the now-playing API."""

import json
import os
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from now_playing.dashboard_html import render_dashboard, render_overlay
from now_playing.logging_config import LOGGER
from now_playing.paths import namespaced_current_artwork_file
from now_playing.sync_service import read_current_payload, sync


class NowPlayingHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, current_payload_getter):
        super().__init__(server_address, handler_class)
        self.current_payload_getter = current_payload_getter
        self.event_clients: set = set()
        self.event_clients_lock = threading.Lock()

    def add_event_client(self, handler) -> None:
        with self.event_clients_lock:
            self.event_clients.add(handler)

    def remove_event_client(self, handler) -> None:
        with self.event_clients_lock:
            self.event_clients.discard(handler)

    def broadcast_event(self, payload: dict) -> None:
        message = f"event: now_playing\ndata: {json.dumps(payload, sort_keys=True)}\n\n".encode("utf-8")
        with self.event_clients_lock:
            clients = list(self.event_clients)

        stale_clients = []
        for client in clients:
            try:
                client.wfile.write(message)
                client.wfile.flush()
            except Exception:
                stale_clients.append(client)

        if stale_clients:
            with self.event_clients_lock:
                for client in stale_clients:
                    self.event_clients.discard(client)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "NowPlayingHTTP/1.0"

    @staticmethod
    def overlay_preset(raw_value: str) -> str:
        preset = raw_value.strip().lower() if raw_value else "compact"
        return "tv" if preset == "tv" else "compact"

    @staticmethod
    def overlay_flag(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def overlay_max_lines(raw_value: str) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return 2
        return max(1, min(3, value))

    @staticmethod
    def overlay_panel_opacity(raw_value: str) -> float:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return 0.64
        return max(0.20, min(0.95, value))

    def overlay_options(self, query: str) -> dict:
        parsed = urllib.parse.parse_qs(query)
        preset_value = parsed.get("preset", [os.environ.get("NOW_PLAYING_OVERLAY_PRESET", "compact")])[0]
        hide_status_value = parsed.get("hide_status", [os.environ.get("NOW_PLAYING_OVERLAY_HIDE_STATUS", "0")])[0]
        max_lines_value = parsed.get("max_lines", [os.environ.get("NOW_PLAYING_OVERLAY_MAX_LINES", "2")])[0]
        panel_opacity_value = parsed.get("panel_opacity", [os.environ.get("NOW_PLAYING_OVERLAY_PANEL_OPACITY", "0.64")])[0]
        return {
            "preset": self.overlay_preset(preset_value),
            "hide_status": self.overlay_flag(hide_status_value),
            "max_lines": self.overlay_max_lines(max_lines_value),
            "panel_opacity": self.overlay_panel_opacity(panel_opacity_value),
        }

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.respond_html(render_dashboard("/", True))
            return

        if parsed.path == "/overlay":
            self.respond_html(render_overlay("/", True, self.overlay_options(parsed.query)))
            return

        if parsed.path == "/spotify/" or parsed.path == "/spotify":
            self.respond_html(render_dashboard("/spotify", False))
            return

        if parsed.path == "/spotify/overlay":
            self.respond_html(render_overlay("/spotify", False, self.overlay_options(parsed.query)))
            return

        if parsed.path == "/events":
            self.respond_events()
            return

        if parsed.path == "/health":
            self.respond_json({"status": "ok"})
            return

        payload = self.server.current_payload_getter()
        if parsed.path == "/current":
            self.respond_json(payload)
            return

        if parsed.path == "/current.txt":
            self.respond_text(payload.get("text", ""))
            return

        if parsed.path == "/artwork":
            self.respond_json({"artwork_path": payload.get("artwork_path") or None})
            return

        if parsed.path == "/current_artwork.png":
            self.respond_artwork("current")
            return

        if parsed.path == "/spotify/current":
            self.respond_json(read_current_payload("", "spotify", live_fallback=False))
            return

        if parsed.path == "/spotify/current.txt":
            spotify_payload = read_current_payload("", "spotify", live_fallback=False)
            self.respond_text(spotify_payload.get("text", ""))
            return

        if parsed.path == "/spotify/artwork":
            spotify_payload = read_current_payload("", "spotify", live_fallback=False)
            self.respond_json({"artwork_path": spotify_payload.get("artwork_path") or None})
            return

        if parsed.path == "/spotify/current_artwork.png":
            self.respond_artwork("spotify")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, fmt: str, *args) -> None:
        LOGGER.debug("HTTP %s - %s", self.address_string(), fmt % args)

    def respond_json(self, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_text(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_artwork(self, namespace: str = "current") -> None:
        path = namespaced_current_artwork_file(namespace)
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Artwork not found")
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def respond_events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        self.server.add_event_client(self)
        initial_payload = self.server.current_payload_getter()
        self.wfile.write(
            f"event: now_playing\ndata: {json.dumps(initial_payload, sort_keys=True)}\n\n".encode("utf-8")
        )
        self.wfile.flush()

        try:
            while True:
                time.sleep(60)
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except Exception:
            pass
        finally:
            self.server.remove_event_client(self)

    def respond_json(self, payload: dict) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_text(self, body: str) -> None:
        content = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def respond_artwork(self, namespace: str = "current") -> None:
        path = namespaced_current_artwork_file(namespace)
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Artwork not found")
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def respond_events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        self.server.add_event_client(self)
        initial_payload = self.server.current_payload_getter()
        self.wfile.write(
            f"event: now_playing\ndata: {json.dumps(initial_payload, sort_keys=True)}\n\n".encode("utf-8")
        )
        self.wfile.flush()

        try:
            while True:
                time.sleep(60)
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except Exception:
            pass
        finally:
            self.server.remove_event_client(self)

def run_server(source: str, idle_text: str, host: str, port: int, interval_seconds: float) -> int:
    current_payload = {"text": idle_text}
    payload_lock = threading.Lock()
    stop_event = threading.Event()
    server: NowPlayingHTTPServer | None = None

    def refresh_once() -> None:
        nonlocal current_payload
        result = sync(source, idle_text)
        payload = result["track"]
        with payload_lock:
            previous_payload = dict(current_payload)
            current_payload = payload
        if server and previous_payload != payload:
            server.broadcast_event(payload)

    def refresh_loop() -> None:
        nonlocal current_payload
        while not stop_event.is_set():
            try:
                refresh_once()
            except Exception:
                LOGGER.exception("Sync loop failed")
            stop_event.wait(interval_seconds)

    def get_payload() -> dict:
        with payload_lock:
            return dict(current_payload)

    refresh_once()
    worker = threading.Thread(target=refresh_loop, name="sync-loop", daemon=True)
    worker.start()

    server = NowPlayingHTTPServer((host, port), RequestHandler, get_payload)
    LOGGER.info("Serving now playing API on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping server")
    finally:
        stop_event.set()
        server.server_close()
    return 0
