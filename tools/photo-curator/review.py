#!/usr/bin/env python3
"""
Photo Curator — Phase 3: local review UI.

A tiny Flask app on 127.0.0.1:5757 that shows a grid of all assets in the
curator DB and lets you flag each one as accepted / rejected / home-video.
Designed strictly for local use — no auth, binds loopback only.

Keyboard shortcuts:
    j / k       prev / next card
    a           accept
    r           reject
    h           mark as home-video
    u           reset to 'new'
    enter       open full-size in modal
    esc         close modal

Usage:
    python review.py
    python review.py --port 5800
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sqlite3
import subprocess
import threading
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template_string, request, send_file

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / "imgsort"
THUMBS_DIR = STATE_DIR / "thumbs"
PREVIEW_DIR = STATE_DIR / "preview"
DB_PATH = STATE_DIR / "curator.db"

# Mirror of web/optimize_videos.sh — keep in sync.
PREVIEW_FFMPEG_VF = (
    "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease,"
    "scale=trunc(iw/2)*2:trunc(ih/2)*2"
)
PREVIEW_FFMPEG_ARGS = [
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "22",
    "-r", "30",
    "-movflags", "+faststart",
    "-an",
]

# Per-id encoding lock so concurrent requests for the same video don't fight.
_encoding_locks: dict[int, threading.Lock] = {}
_encoding_locks_master = threading.Lock()


def _get_encode_lock(asset_id: int) -> threading.Lock:
    with _encoding_locks_master:
        lock = _encoding_locks.get(asset_id)
        if lock is None:
            lock = threading.Lock()
            _encoding_locks[asset_id] = lock
        return lock


def _ensure_preview(asset_id: int, src: Path) -> Path | None:
    """
    Encode src into PREVIEW_DIR/<id>.mp4 with the same settings as
    optimize_videos.sh, idempotent + locked. Returns the path on success.
    """
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    dest = PREVIEW_DIR / f"{asset_id}.mp4"
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return dest
    lock = _get_encode_lock(asset_id)
    with lock:
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            return dest
        tmp = dest.with_suffix(".tmp.mp4")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-vf", PREVIEW_FFMPEG_VF,
            *PREVIEW_FFMPEG_ARGS,
            str(tmp),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0 or not tmp.exists():
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            return None
        os.replace(tmp, dest)
        return dest

app = Flask(__name__)


def db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# ---------- routes ---------------------------------------------------------


INDEX_HTML = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Isar Photo Curator</title>
<style>
  :root { --bg:#0f1115; --card:#1a1d24; --txt:#e6e8ee; --muted:#8a93a4;
          --acc:#3aa675; --rej:#c0504d; --home:#3a7bd5; --new:#444;
          --flood:#d68a2a; }
  html, body { background: var(--bg); color: var(--txt); margin:0;
               font-family: system-ui, sans-serif; }
  header { padding: 10px 16px; background: #14171d; display:flex; gap:16px;
           align-items:center; position: sticky; top:0; z-index: 10;
           border-bottom: 1px solid #232730; }
  header h1 { font-size: 16px; margin: 0; }
  header .filters { display: flex; gap: 6px; }
  header button { background: #232730; color: var(--txt); border: 0;
                  padding: 6px 12px; border-radius: 4px; cursor: pointer; }
  header button.active { background: #3a7bd5; }
  .stats { color: var(--muted); font-size: 13px; margin-left: auto; }
  main { padding: 16px; }
  .grid { display: grid; gap: 12px;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  .card { background: var(--card); border-radius: 6px; overflow: hidden;
          border: 2px solid transparent; position: relative; }
  .card.sel { border-color: #3a7bd5; }
  .card.s-accepted   { border-color: var(--acc); }
  .card.s-rejected   { border-color: var(--rej); opacity: 0.55; }
  .card.s-home-video { border-color: var(--home); }
  .thumb-wrap { width: 100%; aspect-ratio: 1/1; overflow: hidden;
                background: #000; position: relative; }
  .card .thumb { width: 100%; height: 100%; object-fit: contain;
                 display: block; cursor: pointer;
                 transition: transform 0.2s ease; }
  .card .thumb.r90  { transform: rotate(90deg); }
  .card .thumb.r180 { transform: rotate(180deg); }
  .card .thumb.r270 { transform: rotate(270deg); }
  .icon-btn { position: absolute; background: rgba(0,0,0,.7); color: #fff;
              border: 0; width: 26px; height: 26px; border-radius: 50%;
              cursor: pointer; font-size: 14px; line-height: 26px;
              padding: 0; opacity: 0; transition: opacity 0.15s; }
  .card:hover .icon-btn,
  .card.sel  .icon-btn { opacity: 1; }
  .rotate-btn { top: 6px; right: 6px; }
  .flood-btn  { top: 6px; right: 38px; }
  .card.flood .flood-btn { opacity: 1; background: var(--flood); }
  .card.flood { box-shadow: inset 0 0 0 2px var(--flood); }
  .flood-badge { position: absolute; bottom: 6px; left: 6px;
                 background: var(--flood); color: #000; padding: 2px 8px;
                 font-size: 10px; font-weight: 700; border-radius: 3px;
                 letter-spacing: 0.5px; display: none; }
  .card.flood .flood-badge { display: block; }
  .badge { position: absolute; top: 6px; left: 6px; background: rgba(0,0,0,.7);
           color: #fff; padding: 2px 6px; font-size: 11px; border-radius: 3px; }
  .badge.video { background: rgba(58,123,213,.85); }
  .meta { padding: 8px 10px; font-size: 12px; line-height: 1.4; }
  .meta .label { color: var(--txt); font-weight: 500; }
  .meta .when, .meta .dist { color: var(--muted); }
  .actions { display: flex; gap: 4px; padding: 0 10px 10px; }
  .actions button { flex: 1; background: #232730; color: var(--txt);
                    border: 0; padding: 6px 0; border-radius: 3px;
                    cursor: pointer; font-size: 11px; }
  .actions button.a:hover { background: var(--acc); }
  .actions button.r:hover { background: var(--rej); }
  .actions button.h:hover { background: var(--home); }
  .modal { position: fixed; inset: 0; background: rgba(0,0,0,.92);
           display: none; align-items: center; justify-content: center;
           z-index: 100; }
  .modal.open { display: flex; }
  .modal img, .modal video { max-width: 95vw; max-height: 95vh; }
  .modal .close { position: absolute; top: 14px; right: 18px; color: #fff;
                  font-size: 28px; cursor: pointer; background: none; border: 0; z-index: 5; }
  .modal .toolbar { position: absolute; top: 14px; left: 14px;
                    display: flex; gap: 8px; z-index: 5; }
  .modal .toolbar button { background: rgba(40,44,52,.85); color: #fff;
                            border: 1px solid #555; padding: 8px 14px;
                            border-radius: 4px; cursor: pointer;
                            font-size: 12px; }
  .modal .toolbar button.on { background: var(--home); border-color: var(--home); }
  .modal .toolbar .status { padding: 8px 14px; background: rgba(0,0,0,.6);
                            border-radius: 4px; font-size: 12px; color: var(--muted); }

  /* Home-Preview mode: simulate the landing page background */
  .modal.home-preview { background: #0a0d12; }
  .modal.home-preview video { max-width: 100vw; max-height: 100vh;
                              width: 100vw; height: 100vh; object-fit: cover; }
  .modal.home-preview .home-overlay {
    position: absolute; inset: 0; pointer-events: none;
    background: linear-gradient(180deg,
      rgba(10,13,18,0.65) 0%,
      rgba(10,13,18,0.35) 35%,
      rgba(10,13,18,0.55) 70%,
      rgba(10,13,18,0.85) 100%);
  }
  .modal:not(.home-preview) .home-overlay { display: none; }
  .modal.home-preview .home-mock {
    position: absolute; inset: 0; pointer-events: none;
    display: flex; flex-direction: column; padding: 32px 48px;
    color: #e6e8ee; font-family: system-ui, sans-serif;
  }
  .modal.home-preview .home-mock .h-nav {
    display: flex; gap: 24px; font-size: 14px; opacity: 0.92;
    border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 14px;
  }
  .modal.home-preview .home-mock .h-nav .brand { font-weight: 700; margin-right: auto; }
  .modal.home-preview .home-mock .h-hero {
    margin-top: auto; margin-bottom: 64px; max-width: 720px;
  }
  .modal.home-preview .home-mock .h-hero h1 {
    font-size: 56px; font-weight: 700; margin: 0 0 16px;
    text-shadow: 0 2px 16px rgba(0,0,0,0.6);
  }
  .modal.home-preview .home-mock .h-hero p {
    font-size: 18px; line-height: 1.5; margin: 0; opacity: 0.92;
    text-shadow: 0 1px 8px rgba(0,0,0,0.6);
  }
  .modal:not(.home-preview) .home-mock { display: none; }
  .empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Isar Photo Curator</h1>
  <div class="filters">
    {% for f in ['new','accepted','home-video','rejected','all'] %}
      <button class="filter-btn{% if f == active_filter %} active{% endif %}"
              data-filter="{{ f }}">{{ f }}</button>
    {% endfor %}
  </div>
  <div class="stats" id="stats">{{ assets|length }} Treffer</div>
</header>
<main>
  {% if assets %}
  <div class="grid" id="grid">
    {% for a in assets %}
    <div class="card s-{{ a.status }}{% if a.is_flood %} flood{% endif %}"
         data-id="{{ a.id }}" data-kind="{{ a.kind }}"
         data-rotation="{{ a.display_rotation }}"
         data-flood="{{ 1 if a.is_flood else 0 }}">
      <div class="thumb-wrap">
        <img class="thumb {% if a.display_rotation %}r{{ a.display_rotation }}{% endif %}"
             src="/thumb/{{ a.id }}.jpg" alt="">
        <button class="icon-btn flood-btn" title="Hochwasser markieren (f)">⚠</button>
        <button class="icon-btn rotate-btn" title="90° drehen (t)">↻</button>
        <span class="flood-badge">HOCHWASSER</span>
      </div>
      <div class="badge {% if a.kind == 'video' %}video{% endif %}">
        {{ a.kind }}{% if a.duration_s %} · {{ a.duration_s|round(1) }}s{% endif %}
      </div>
      <div class="meta">
        <div class="label">{{ a.location_label or '—' }}</div>
        <div class="when">{{ (a.taken_at or '')[:16].replace('T',' ') }}</div>
        <div class="dist">{{ '%.0f' % a.distance_isar_m }} m zur Isar</div>
      </div>
      <div class="actions">
        <button class="a" data-status="accepted">Accept</button>
        <button class="r" data-status="rejected">Reject</button>
        <button class="h" data-status="home-video">Home</button>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty">Nix da. Anderen Filter probieren.</div>
  {% endif %}
</main>
<div class="modal" id="modal">
  <div class="toolbar" id="modal-toolbar">
    <button id="btn-original" class="on">Original</button>
    <button id="btn-home-preview">Home-Vorschau (1080p, CRF 22)</button>
    <span class="status" id="preview-status" style="display:none">Encoding…</span>
  </div>
  <button class="close" id="modal-close">×</button>
  <div id="modal-body"></div>
  <div class="home-overlay"></div>
  <div class="home-mock">
    <div class="h-nav">
      <span class="brand">Isarwasser <span style="opacity:.6">München</span></span>
      <span>Dahoam</span><span>Erkunden</span><span>Rekorde</span>
    </div>
    <div class="h-hero">
      <h1>Isarwasser in München</h1>
      <p>Eine interaktive Ansicht von Wasserstand und Wassertemperatur der Isar — von 1973 bis heute.</p>
    </div>
  </div>
</div>
<script>
let selectedIdx = -1;
const cards = Array.from(document.querySelectorAll('.card'));

function selectCard(idx) {
  if (selectedIdx >= 0) cards[selectedIdx].classList.remove('sel');
  selectedIdx = Math.max(0, Math.min(cards.length - 1, idx));
  if (cards[selectedIdx]) {
    cards[selectedIdx].classList.add('sel');
    cards[selectedIdx].scrollIntoView({block: 'nearest', behavior: 'smooth'});
  }
}

async function setStatus(id, status, cardEl) {
  const r = await fetch('/status/' + id, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status})
  });
  if (r.ok) {
    // Preserve current rotation class when rebuilding className.
    const rot = cardEl.dataset.rotation;
    cardEl.className = 'card sel s-' + status;
  }
}

async function rotateCard(cardEl) {
  const id = cardEl.dataset.id;
  const cur = parseInt(cardEl.dataset.rotation || '0', 10);
  const next = (cur + 90) % 360;
  const r = await fetch('/rotate/' + id, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({rotation: next})
  });
  if (r.ok) {
    cardEl.dataset.rotation = next;
    const img = cardEl.querySelector('.thumb');
    img.classList.remove('r90', 'r180', 'r270');
    if (next) img.classList.add('r' + next);
  }
}

async function toggleFlood(cardEl) {
  const id = cardEl.dataset.id;
  const next = cardEl.dataset.flood === '1' ? 0 : 1;
  const r = await fetch('/flood/' + id, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({is_flood: next})
  });
  if (r.ok) {
    cardEl.dataset.flood = String(next);
    cardEl.classList.toggle('flood', next === 1);
  }
}

document.querySelectorAll('.actions button').forEach(btn => {
  btn.addEventListener('click', e => {
    e.stopPropagation();
    const card = btn.closest('.card');
    setStatus(card.dataset.id, btn.dataset.status, card);
  });
});

document.querySelectorAll('.rotate-btn').forEach(btn => {
  btn.addEventListener('click', e => {
    e.stopPropagation();
    rotateCard(btn.closest('.card'));
  });
});

document.querySelectorAll('.flood-btn').forEach(btn => {
  btn.addEventListener('click', e => {
    e.stopPropagation();
    toggleFlood(btn.closest('.card'));
  });
});

document.querySelectorAll('.thumb').forEach(img => {
  img.addEventListener('click', e => {
    const card = img.closest('.card');
    selectCard(cards.indexOf(card));
    openModal(card.dataset.id, card.dataset.kind);
  });
});

document.querySelectorAll('.filter-btn').forEach(b => {
  b.addEventListener('click', () => {
    const f = b.dataset.filter;
    location.href = '/?filter=' + encodeURIComponent(f);
  });
});

let currentModalId = null;
let currentModalKind = null;

function setToolbarMode(mode) {
  // mode: 'original' | 'home'
  const orig = document.getElementById('btn-original');
  const home = document.getElementById('btn-home-preview');
  orig.classList.toggle('on', mode === 'original');
  home.classList.toggle('on', mode === 'home');
}

function loadOriginal() {
  if (!currentModalId) return;
  const modal = document.getElementById('modal');
  const body = document.getElementById('modal-body');
  modal.classList.remove('home-preview');
  document.getElementById('preview-status').style.display = 'none';
  if (currentModalKind === 'video') {
    body.innerHTML = '<video controls autoplay loop src="/full/' + currentModalId + '"></video>';
  } else {
    body.innerHTML = '<img src="/full/' + currentModalId + '">';
  }
  setToolbarMode('original');
}

async function loadHomePreview() {
  if (!currentModalId || currentModalKind !== 'video') return;
  const modal = document.getElementById('modal');
  const body = document.getElementById('modal-body');
  const status = document.getElementById('preview-status');
  setToolbarMode('home');
  modal.classList.add('home-preview');
  // Show encoding status while we wait. The fetch returns binary, but we
  // can probe with a HEAD-equivalent: just request and stream into a
  // hidden video, with status visible until the video starts.
  body.innerHTML = '';
  status.textContent = 'Encoding (kann ein paar Sek dauern)…';
  status.style.display = 'inline-block';
  const url = '/preview/' + currentModalId + '.mp4?ts=' + Date.now();
  // Trigger the encode by issuing a fetch; we discard the body and let
  // the <video> element pick the (now-cached) file from the same URL.
  try {
    const r = await fetch(url, {method: 'GET'});
    if (!r.ok) {
      status.textContent = 'Encoding fehlgeschlagen (' + r.status + ')';
      return;
    }
    // Drain the response so the cache file is fully written before <video> reads it.
    await r.blob();
  } catch (e) {
    status.textContent = 'Fehler: ' + e.message;
    return;
  }
  status.style.display = 'none';
  body.innerHTML = '<video autoplay muted loop playsinline src="' + url + '"></video>';
}

function openModal(id, kind) {
  currentModalId = id;
  currentModalKind = kind;
  document.getElementById('modal').classList.add('open');
  // Toolbar only relevant for videos.
  document.getElementById('modal-toolbar').style.display = (kind === 'video') ? 'flex' : 'none';
  loadOriginal();
}
function closeModal() {
  const modal = document.getElementById('modal');
  modal.classList.remove('open');
  modal.classList.remove('home-preview');
  document.getElementById('modal-body').innerHTML = '';
  document.getElementById('preview-status').style.display = 'none';
  currentModalId = null;
  currentModalKind = null;
}
document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('btn-original').addEventListener('click', e => {
  e.stopPropagation();
  loadOriginal();
});
document.getElementById('btn-home-preview').addEventListener('click', e => {
  e.stopPropagation();
  loadHomePreview();
});
document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});

document.addEventListener('keydown', e => {
  if (document.getElementById('modal').classList.contains('open')) {
    if (e.key === 'Escape') closeModal();
    return;
  }
  const card = cards[selectedIdx];
  switch (e.key) {
    case 'j': selectCard(selectedIdx + 1); break;
    case 'k': selectCard(selectedIdx - 1); break;
    case 'a': if (card) setStatus(card.dataset.id, 'accepted', card); break;
    case 'r': if (card) setStatus(card.dataset.id, 'rejected', card); break;
    case 'h': if (card) setStatus(card.dataset.id, 'home-video', card); break;
    case 'u': if (card) setStatus(card.dataset.id, 'new', card); break;
    case 't': if (card) rotateCard(card); break;
    case 'f': if (card) toggleFlood(card); break;
    case 'Enter': if (card) openModal(card.dataset.id, card.dataset.kind); break;
  }
});

if (cards.length) selectCard(0);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    f = request.args.get("filter", "new")
    if f == "all":
        rows = db().execute(
            "SELECT * FROM assets WHERE thumb_path IS NOT NULL "
            "ORDER BY taken_at"
        ).fetchall()
    else:
        rows = db().execute(
            "SELECT * FROM assets WHERE status = ? AND thumb_path IS NOT NULL "
            "ORDER BY taken_at",
            (f,),
        ).fetchall()
    return render_template_string(INDEX_HTML, assets=rows, active_filter=f)


@app.route("/thumb/<int:asset_id>.jpg")
def thumb(asset_id: int):
    row = db().execute(
        "SELECT thumb_path FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if not row or not row["thumb_path"]:
        abort(404)
    p = THUMBS_DIR / row["thumb_path"]
    if not p.exists():
        abort(404)
    return send_file(p, mimetype="image/jpeg")


@app.route("/full/<int:asset_id>")
def full(asset_id: int):
    row = db().execute(
        "SELECT source_path, kind FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if not row:
        abort(404)
    p = Path(row["source_path"])
    if not p.exists() or not p.is_file():
        abort(404)
    mime, _ = mimetypes.guess_type(str(p))
    return send_file(p, mimetype=mime or "application/octet-stream")


@app.route("/preview/<int:asset_id>.mp4")
def preview(asset_id: int):
    """
    Re-encode the source video on demand using the *web* optimize settings
    (1080p, CRF 22), cache the result in imgsort/preview/, and stream it.
    Used by the curator's "Home-Vorschau" mode so you can judge the actual
    quality the landing page will show before bulk-running optimize_videos.sh.
    """
    row = db().execute(
        "SELECT source_path, kind FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    if not row:
        abort(404)
    if row["kind"] != "video":
        abort(400, "preview only works for videos")
    src = Path(row["source_path"])
    if not src.exists() or not src.is_file():
        abort(404)
    encoded = _ensure_preview(asset_id, src)
    if encoded is None:
        abort(500, "ffmpeg encode failed")
    return send_file(encoded, mimetype="video/mp4")


@app.route("/status/<int:asset_id>", methods=["POST"])
def set_status(asset_id: int):
    payload = request.get_json(force=True)
    status = payload.get("status")
    if status not in ("new", "accepted", "rejected", "home-video"):
        abort(400)
    conn = db()
    cur = conn.execute(
        "UPDATE assets SET status = ? WHERE id = ?", (status, asset_id)
    )
    conn.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"ok": True, "status": status})


@app.route("/rotate/<int:asset_id>", methods=["POST"])
def set_rotation(asset_id: int):
    payload = request.get_json(force=True)
    rot = payload.get("rotation")
    if rot not in (0, 90, 180, 270):
        abort(400)
    conn = db()
    cur = conn.execute(
        "UPDATE assets SET display_rotation = ? WHERE id = ?", (rot, asset_id)
    )
    conn.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"ok": True, "rotation": rot})


@app.route("/flood/<int:asset_id>", methods=["POST"])
def set_flood(asset_id: int):
    payload = request.get_json(force=True)
    flag = payload.get("is_flood")
    if flag not in (0, 1, True, False):
        abort(400)
    flag = 1 if flag else 0
    conn = db()
    cur = conn.execute(
        "UPDATE assets SET is_flood = ? WHERE id = ?", (flag, asset_id)
    )
    conn.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"ok": True, "is_flood": flag})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5757)
    args = ap.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found. Run scan.py and thumbs.py first.")
        return 2

    print(f"Photo Curator → http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
