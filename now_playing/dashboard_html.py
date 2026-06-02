"""Dashboard and overlay HTML rendering."""

import os
import urllib.parse
from typing import Optional

from now_playing.templates import load_html_template


def render_dashboard(route_prefix: str, use_sse: bool) -> str:
    fallback_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Now Playing</title>
  <style>
    :root {
      --bg: #060709;
      --bg-2: #11161b;
      --panel: rgba(10, 12, 15, 0.84);
      --panel-edge: rgba(255, 255, 255, 0.08);
      --text: #f4efe4;
      --muted: #aea79b;
      --soft: #7e7a73;
      --accent: #c7462d;
      --accent-soft: rgba(199, 70, 45, 0.2);
      --glow: rgba(199, 70, 45, 0.16);
      --art-bg: linear-gradient(145deg, #191b1f, #08090b);
      --font-iosevka:
    "Iosevka Aile",
    "Iosevka Etoile",
    "Iosevka Curly",
    "Iosevka Curly Slab",
    "Iosevka Slab",
    "Iosevka Term",
    "Iosevka Fixed",
    "Iosevka",
    "Iosevka Nerd Font",
    "IosevkaTerm Nerd Font",
    "IosevkaTerm NFM",
    "Iosevka NFM",
    monospace;
    }
    body {
      margin: 0;
      min-height: 100vh;
      background:
    radial-gradient(circle at top left, rgba(199, 70, 45, 0.18), transparent 28%),
    radial-gradient(circle at 85% 20%, rgba(73, 86, 104, 0.2), transparent 24%),
    linear-gradient(160deg, var(--bg) 0%, #0d1116 46%, #13181f 100%);
      color: var(--text);
      font-family: var(--font-iosevka);
      overflow-x: hidden;
      overflow-y: auto;
    }
    body, button, input, textarea, select {
      font-family: var(--font-iosevka);
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
    linear-gradient(rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0.01)),
    repeating-linear-gradient(
      180deg,
      transparent 0,
      transparent 3px,
      rgba(255, 255, 255, 0.015) 4px
    );
      mix-blend-mode: soft-light;
      opacity: 0.55;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      align-items: start;
      justify-items: center;
      padding: clamp(18px, 4vh, 40px) 20px 24px;
      box-sizing: border-box;
    }
    .card {
      position: relative;
      width: min(1120px, 100%);
      box-sizing: border-box;
      border-radius: 30px;
      padding: 24px;
      background:
    linear-gradient(180deg, rgba(255,255,255,0.04), transparent 18%),
    var(--panel);
      border: 1px solid var(--panel-edge);
      box-shadow:
    0 38px 90px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(255, 255, 255, 0.03) inset,
    0 0 90px var(--glow);
      backdrop-filter: blur(14px);
    }
    .card::before {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      padding: 1px;
      background: linear-gradient(135deg, rgba(199, 70, 45, 0.55), transparent 35%, rgba(255,255,255,0.08));
      -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
      -webkit-mask-composite: xor;
      mask-composite: exclude;
      pointer-events: none;
      opacity: 0.7;
    }
    .masthead {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 18px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 11px;
      color: var(--muted);
    }
    .brand {
      display: inline-flex;
      gap: 10px;
      align-items: center;
    }
    .brand-mark {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 18px rgba(199, 70, 45, 0.7);
    }
    .brand-copy {
      display: flex;
      gap: 10px;
      align-items: baseline;
    }
    .brand-copy strong {
      color: var(--text);
      font-weight: 700;
    }
    .signal {
      display: inline-flex;
      gap: 8px;
      align-items: center;
      color: var(--soft);
    }
    .grid {
      display: grid;
      gap: 22px;
      grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
      align-items: start;
    }
    .artwork {
      aspect-ratio: 1;
      border-radius: 24px;
      overflow: hidden;
      background: var(--art-bg);
      display: grid;
      grid-template: 1fr / 1fr;
      place-items: center;
      border: 1px solid rgba(255, 255, 255, 0.06);
      box-shadow:
    inset 0 0 0 1px rgba(255,255,255,0.03),
    0 20px 50px rgba(0, 0, 0, 0.35);
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 11px;
      position: relative;
    }
    .artwork::after {
      content: "";
      position: absolute;
      inset: 0;
      background:
    linear-gradient(180deg, rgba(255,255,255,0.08), transparent 24%),
    linear-gradient(135deg, transparent 45%, rgba(199, 70, 45, 0.14));
      pointer-events: none;
    }
    .artwork > * {
      grid-area: 1 / 1;
    }
    .artwork img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: none;
      position: relative;
      z-index: 1;
    }
    .content {
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      min-width: 0;
    }
    .kicker {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.22em;
      font-size: 12px;
    }
    .title {
      margin-top: 12px;
      font-size: clamp(40px, 6vw, 84px);
      line-height: 1.05;
      font-weight: 800;
      font-family: var(--font-iosevka);
      letter-spacing: -0.08em;
      text-wrap: balance;
      overflow-wrap: break-word;
      word-break: break-word;
      min-width: 0;
    }
    .meta {
      margin-top: 10px;
      color: #d8d1c2;
      font-size: clamp(18px, 2vw, 24px);
      max-width: 30ch;
    }
    .status-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-top: 18px;
    }
    .status {
      display: inline-flex;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      color: var(--text);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border: 1px solid rgba(255,255,255,0.08);
    }
    .state-playing {
      background: var(--accent-soft);
      border-color: rgba(199, 70, 45, 0.35);
      color: #ffd6cf;
    }
    .state-idle, .state-not_running {
      color: var(--muted);
    }
    .details {
      display: grid;
      gap: 12px;
      margin-top: 20px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      min-width: 0;
    }
    .detail {
      padding-top: 12px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }
    .detail-label {
      display: block;
      color: var(--soft);
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 10px;
      margin-bottom: 6px;
    }
    .detail-value {
      color: var(--text);
      font-size: 15px;
      word-break: break-word;
      overflow-wrap: anywhere;
      font-family: var(--font-iosevka);
    }
    .masthead,
    .brand,
    .brand-copy,
    .signal,
    .kicker,
    .meta,
    .status,
    .detail-label,
    .detail-value,
    .footer-note {
      font-family: var(--font-iosevka);
    }
    .footer-note {
      margin-top: 18px;
      color: var(--soft);
      font-size: 12px;
      letter-spacing: 0.06em;
    }
    .providers {
      display: grid;
      gap: 10px;
      margin-top: 18px;
    }
    .provider-card {
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
    }
    .provider-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 6px;
    }
    .provider-name {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 11px;
    }
    .provider-state {
      color: var(--text);
      font-size: 13px;
      text-transform: uppercase;
    }
    .provider-detail {
      color: var(--soft);
      font-size: 12px;
      line-height: 1.45;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .provider-error {
      color: #ffb4a5;
    }
    @media (min-width: 961px) {
      .content {
    padding-right: 8px;
      }
    }
    @media (max-width: 960px) {
      .grid {
    grid-template-columns: 1fr;
      }
      .meta {
    max-width: none;
      }
      .details {
    grid-template-columns: 1fr;
      }
    }
    @media (max-width: 680px) {
      .shell {
    padding: 14px;
      }
      .card {
    padding: 16px;
    border-radius: 22px;
      }
      .masthead {
    margin-bottom: 14px;
      }
      .title {
    font-size: clamp(34px, 11vw, 56px);
    letter-spacing: -0.05em;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <main class="card">
      <div class="masthead">
    <div class="brand">
      <span class="brand-mark"></span>
      <div class="brand-copy">
            <strong>Funkatron</strong>
            <span>/ Dead Agent signal</span>
      </div>
    </div>
    <div class="signal">Local viewer / SSE live feed</div>
      </div>
      <div class="grid">
    <div class="artwork">
      <img id="artwork-image" alt="Current artwork">
      <div id="artwork-empty">No Artwork</div>
    </div>
    <section class="content">
      <div class="kicker">Now Playing</div>
      <div id="title" class="title">Waiting for playback</div>
      <div id="meta" class="meta">Start Apple Music or Spotify and press play.</div>
      <div class="status-row">
            <div id="status" class="status">idle</div>
      </div>
      <div class="details">
            <div class="detail">
              <span class="detail-label">Source</span>
              <span id="source" class="detail-value">unknown</span>
            </div>
            <div class="detail">
              <span class="detail-label">Updated</span>
              <span id="updated-at" class="detail-value">never</span>
            </div>
      </div>
      <div id="providers" class="providers"></div>
      <div class="footer-note">Live local feed for stream overlays, OBS, and operator checks.</div>
    </section>
      </div>
    </main>
  </div>
  <script>
    const endpointPrefix = "__ENDPOINT_PREFIX__";
    const useSse = __USE_SSE__;
    const titleEl = document.getElementById("title");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const sourceEl = document.getElementById("source");
    const updatedAtEl = document.getElementById("updated-at");
    const artworkImageEl = document.getElementById("artwork-image");
    const artworkEmptyEl = document.getElementById("artwork-empty");
    const providersEl = document.getElementById("providers");
    let lastArtworkVersion = "";

    function endpoint(path) {
      return endpointPrefix + path;
    }

    function formatProviderName(name) {
      if (name === "apple_music") return "Apple Music";
      if (name === "spotify") return "Spotify";
      return name || "Unknown";
    }

    function renderProviders(payload) {
      const providers = payload.providers || {};
      const entries = Object.entries(providers);
      if (!entries.length) {
    providersEl.innerHTML = "";
    return;
      }

      providersEl.innerHTML = entries.map(([name, info]) => {
    const detailClass = info.error ? "provider-detail provider-error" : "provider-detail";
    const detail = info.error || info.detail || "No additional detail";
    return `
      <div class="provider-card">
            <div class="provider-head">
              <span class="provider-name">${formatProviderName(name)}</span>
              <span class="provider-state">${info.state || "unknown"}</span>
            </div>
            <div class="${detailClass}">${detail}</div>
      </div>
    `;
      }).join("");
    }

    function render(payload) {
      sourceEl.textContent = payload.source || "unknown";
      updatedAtEl.textContent = payload.updated_at || "never";
      statusEl.textContent = payload.state || "unknown";
      statusEl.className = "status state-" + (payload.state || "unknown");
      renderProviders(payload);

      if (payload.state === "playing" && payload.title) {
    titleEl.textContent = payload.title;
    const parts = [payload.artist, payload.album, payload.year].filter(Boolean);
    metaEl.textContent = parts.join(" • ") || "Playing";
      } else {
    titleEl.textContent = "Waiting for playback";
    metaEl.textContent = "Start Apple Music or Spotify and press play.";
      }

      if (payload.artwork_path) {
    const version = payload.updated_at || payload.artwork_path;
    if (version !== lastArtworkVersion) {
      artworkImageEl.src = endpoint("/current_artwork.png") + "?v=" + encodeURIComponent(version);
      lastArtworkVersion = version;
    }
    artworkImageEl.style.display = "block";
    artworkEmptyEl.style.display = "none";
      } else {
    lastArtworkVersion = "";
    artworkImageEl.removeAttribute("src");
    artworkImageEl.style.display = "none";
    artworkEmptyEl.style.display = "block";
      }
    }

    async function fetchCurrent() {
      const response = await fetch(endpoint("/current"), { cache: "no-store" });
      if (!response.ok) {
    throw new Error("current fetch failed");
      }
      render(await response.json());
    }

    let events = null;
    let reconnectTimer = null;

    function scheduleReconnect() {
      if (!useSse || reconnectTimer !== null) {
    return;
      }
      reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectEvents();
      }, 2000);
    }

    function connectEvents() {
      if (!useSse) {
    return;
      }
      if (events) {
    events.close();
      }
      events = new EventSource(endpoint("/events"));
      events.addEventListener("now_playing", (event) => {
    render(JSON.parse(event.data));
      });
      events.onerror = () => {
    statusEl.textContent = "disconnected";
    if (events) {
      events.close();
      events = null;
    }
    scheduleReconnect();
      };
    }

    fetchCurrent().catch(() => {
      statusEl.textContent = "disconnected";
    });

    connectEvents();
    setInterval(() => {
      fetchCurrent().catch(() => {
    statusEl.textContent = "disconnected";
      });
    }, 5000);
  </script>
</body>
</html>"""
    endpoint_prefix = "" if route_prefix == "/" else route_prefix
    html = load_html_template(
            "dashboard.html",
            "NOW_PLAYING_DASHBOARD_TEMPLATE_PATH",
            fallback_html,
            ("__ENDPOINT_PREFIX__", "__USE_SSE__"),
    )
    return html.replace("__ENDPOINT_PREFIX__", endpoint_prefix).replace("__USE_SSE__", "true" if use_sse else "false")



def render_overlay(route_prefix: str, use_sse: bool, overlay_options: Optional[dict] = None) -> str:
    options = overlay_options or {
            "preset": "compact",
            "hide_status": False,
            "max_lines": 2,
            "panel_opacity": 0.64,
    }
    preset = options["preset"]
    status_class = "overlay-hide-status" if options["hide_status"] else ""
    max_lines = str(options["max_lines"])
    panel_opacity = f"{options['panel_opacity']:.2f}"

    fallback_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Now Playing Overlay</title>
  <style>
    :root {
      --text: #f4efe4;
      --muted: #d8d1c2;
      --panel: rgba(10, 12, 15, __OVERLAY_PANEL_OPACITY__);
      --panel-edge: rgba(255, 255, 255, 0.14);
      --font-iosevka:
    "Iosevka Aile",
    "Iosevka Etoile",
    "Iosevka Curly",
    "Iosevka Curly Slab",
    "Iosevka Slab",
    "Iosevka Term",
    "Iosevka Fixed",
    "Iosevka",
    "Iosevka Nerd Font",
    "IosevkaTerm Nerd Font",
    "IosevkaTerm NFM",
    "Iosevka NFM",
    monospace;
    }
    html, body {
      margin: 0;
      width: 100%;
      min-height: 100vh;
      background: transparent;
      color: var(--text);
      font-family: var(--font-iosevka);
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .overlay {
      display: grid;
      grid-template-columns: 160px minmax(0, 1fr);
      gap: 14px;
      align-items: center;
      width: min(760px, calc(100vw - 24px));
      padding: 12px;
      border-radius: 18px;
      background: var(--panel);
      border: 1px solid var(--panel-edge);
      box-shadow: 0 14px 44px rgba(0, 0, 0, 0.4);
      box-sizing: border-box;
      margin: 12px;
      position: relative;
      isolation: isolate;
    }
    .overlay.overlay-tv {
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 24px;
      width: min(1840px, calc(100vw - 64px));
      padding: 24px;
      border-radius: 28px;
    }
    .overlay.overlay-tv::before {
      content: "";
      position: absolute;
      inset: -18px;
      border-radius: inherit;
      background-image: var(--artwork-url);
      background-size: cover;
      background-position: center;
      filter: blur(56px) saturate(1.15);
      opacity: 0;
      transform: scale(1.05);
      pointer-events: none;
      z-index: -1;
      transition: opacity 300ms ease;
    }
    .overlay.overlay-tv.has-art::before {
      opacity: 0.24;
    }
    .artwork {
      width: 160px;
      height: 160px;
      border-radius: 14px;
      overflow: hidden;
      background: rgba(0, 0, 0, 0.35);
      display: grid;
      place-items: center;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 10px;
      color: #b6afa2;
    }
    .overlay.overlay-tv .artwork {
      width: 280px;
      height: 280px;
      border-radius: 22px;
      border: 1px solid rgba(255, 255, 255, 0.18);
      box-shadow:
    0 26px 52px rgba(0, 0, 0, 0.58),
    0 0 0 1px rgba(255, 255, 255, 0.06) inset;
      background: linear-gradient(150deg, rgba(255, 255, 255, 0.08), rgba(12, 12, 12, 0.48));
    }
    .artwork img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: none;
      transform: scale(1.02);
      transition: transform 1200ms ease;
    }
    .overlay.overlay-tv .artwork img {
      transform: scale(1.08);
    }
    .overlay.overlay-tv.has-art .artwork img {
      transform: scale(1.12);
    }
    .content {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .title {
      font-size: clamp(28px, 4.2vw, 52px);
      line-height: 0.92;
      font-weight: 800;
      letter-spacing: -0.04em;
      margin: 0;
      max-width: 30ch;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: __OVERLAY_MAX_LINES__;
      line-clamp: __OVERLAY_MAX_LINES__;
      overflow: hidden;
    }
    .overlay.overlay-tv .title {
      font-size: clamp(64px, 8vw, 124px);
      line-height: 0.94;
      letter-spacing: -0.03em;
    }
    .meta {
      margin: 0;
      color: var(--muted);
      font-size: clamp(16px, 2vw, 24px);
      line-height: 1.2;
      max-width: 36ch;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: __OVERLAY_MAX_LINES__;
      line-clamp: __OVERLAY_MAX_LINES__;
      overflow: hidden;
    }
    .overlay.overlay-tv .meta {
      font-size: clamp(34px, 4vw, 56px);
      max-width: 34ch;
    }
    .status {
      margin: 0;
      font-size: 11px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #b6afa2;
    }
    .overlay.overlay-tv .status {
      font-size: 20px;
      letter-spacing: 0.14em;
    }
    .overlay.overlay-hide-status .status {
      display: none;
    }
    @media (max-width: 960px) {
      .overlay.overlay-tv {
    grid-template-columns: 156px minmax(0, 1fr);
    width: min(960px, calc(100vw - 24px));
    gap: 14px;
    padding: 14px;
      }
      .overlay.overlay-tv .artwork {
    width: 156px;
    height: 156px;
      }
      .overlay.overlay-tv .title {
    font-size: clamp(36px, 7.6vw, 72px);
      }
      .overlay.overlay-tv .meta {
    font-size: clamp(20px, 3.8vw, 34px);
      }
    }
    @media (max-width: 640px) {
      .overlay {
    grid-template-columns: 96px minmax(0, 1fr);
    gap: 10px;
      }
      .artwork {
    width: 96px;
    height: 96px;
      }
    }
  </style>
</head>
<body>
  <main class="overlay overlay-__OVERLAY_PRESET__ __OVERLAY_STATUS_CLASS__">
    <div class="artwork">
      <img id="artwork-image" alt="Current artwork">
      <div id="artwork-empty">No Artwork</div>
    </div>
    <section class="content">
      <h1 id="title" class="title">Waiting for playback</h1>
      <p id="meta" class="meta">Start Apple Music or Spotify and press play.</p>
      <p id="status" class="status">idle</p>
    </section>
  </main>
  <script>
    const endpointPrefix = "__ENDPOINT_PREFIX__";
    const useSse = __USE_SSE__;
    const titleEl = document.getElementById("title");
    const metaEl = document.getElementById("meta");
    const statusEl = document.getElementById("status");
    const overlayEl = document.querySelector(".overlay");
    const artworkImageEl = document.getElementById("artwork-image");
    const artworkEmptyEl = document.getElementById("artwork-empty");
    let lastArtworkVersion = "";

    function endpoint(path) {
      return endpointPrefix + path;
    }

    function cssUrl(value) {
      return `url("${String(value).replace(/"/g, '\\"')}")`;
    }

    function render(payload) {
      const state = payload.state || "unknown";
      statusEl.textContent = state;

      if (state === "playing" && payload.title) {
    titleEl.textContent = payload.title;
    const parts = [payload.artist, payload.album, payload.year].filter(Boolean);
    metaEl.textContent = parts.join(" • ") || "Playing";
      } else {
    titleEl.textContent = "Waiting for playback";
    metaEl.textContent = "Start Apple Music or Spotify and press play.";
      }

      if (payload.artwork_path) {
    overlayEl.classList.add("has-art");
    overlayEl.style.setProperty("--artwork-url", cssUrl(endpoint("/current_artwork.png")));
    const version = payload.updated_at || payload.artwork_path;
    if (version !== lastArtworkVersion) {
      artworkImageEl.src = endpoint("/current_artwork.png") + "?v=" + encodeURIComponent(version);
      lastArtworkVersion = version;
    }
    artworkImageEl.style.display = "block";
    artworkEmptyEl.style.display = "none";
      } else {
    overlayEl.classList.remove("has-art");
    overlayEl.style.removeProperty("--artwork-url");
    lastArtworkVersion = "";
    artworkImageEl.removeAttribute("src");
    artworkImageEl.style.display = "none";
    artworkEmptyEl.style.display = "block";
      }
    }

    async function fetchCurrent() {
      const response = await fetch(endpoint("/current"), { cache: "no-store" });
      if (!response.ok) {
    throw new Error("current fetch failed");
      }
      render(await response.json());
    }

    let events = null;
    let reconnectTimer = null;

    function scheduleReconnect() {
      if (!useSse || reconnectTimer !== null) {
    return;
      }
      reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectEvents();
      }, 2000);
    }

    function connectEvents() {
      if (!useSse) {
    return;
      }
      if (events) {
    events.close();
      }
      events = new EventSource(endpoint("/events"));
      events.addEventListener("now_playing", (event) => {
    render(JSON.parse(event.data));
      });
      events.onerror = () => {
    statusEl.textContent = "disconnected";
    if (events) {
      events.close();
      events = null;
    }
    scheduleReconnect();
      };
    }

    fetchCurrent().catch(() => {
      statusEl.textContent = "disconnected";
    });

    connectEvents();
    setInterval(() => {
      fetchCurrent().catch(() => {
    statusEl.textContent = "disconnected";
      });
    }, 5000);
  </script>
</body>
</html>"""
    endpoint_prefix = "" if route_prefix == "/" else route_prefix
    html = load_html_template(
            "overlay.html",
            "NOW_PLAYING_OVERLAY_TEMPLATE_PATH",
            fallback_html,
            (
                "__ENDPOINT_PREFIX__",
                "__USE_SSE__",
                "__OVERLAY_PRESET__",
                "__OVERLAY_STATUS_CLASS__",
                "__OVERLAY_MAX_LINES__",
                "__OVERLAY_PANEL_OPACITY__",
            ),
    )
    return (
            html.replace("__ENDPOINT_PREFIX__", endpoint_prefix)
            .replace("__USE_SSE__", "true" if use_sse else "false")
            .replace("__OVERLAY_PRESET__", preset)
            .replace("__OVERLAY_STATUS_CLASS__", status_class)
            .replace("__OVERLAY_MAX_LINES__", max_lines)
            .replace("__OVERLAY_PANEL_OPACITY__", panel_opacity)
    )



