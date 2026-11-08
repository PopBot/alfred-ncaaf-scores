#!/usr/bin/env python3
"""
download_logos.py — Downloads official NCAA FBS logos from ESPN's CDN
and saves them as 64x64 transparent PNGs in cfb_logos/{team_id}.png.
Uses Pillow if installed, falling back to pure-Python image_utils if not.
"""
from __future__ import annotations

import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKFLOW_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(WORKFLOW_DIR, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import requests
from image_utils import decode_png_rgba, encode_rgba_png, resize_nearest

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TEAMS_FILE = os.path.join(WORKFLOW_DIR, "data", "teams.json")
LOGOS_DIR  = os.path.join(WORKFLOW_DIR, "cfb_logos")
os.makedirs(LOGOS_DIR, exist_ok=True)

HEADERS = {"User-Agent": "curl/8.7.1", "Accept": "*/*"}


def _save_64x64_png(raw_bytes: bytes, out_path: str) -> bool:
    if HAS_PIL:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        img.save(out_path, "PNG")
        return True

    # Pure-Python fallback
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(raw_bytes)
    try:
        decoded = decode_png_rgba(tmp_path)
        if not decoded:
            return False
        w, h, px = decoded
        if (w, h) != (64, 64):
            px = resize_nearest(px, w, h, 64, 64)
        png_bytes = encode_rgba_png(px, 64, 64)
        with open(out_path, "wb") as f:
            f.write(png_bytes)
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _download_one(team: dict) -> tuple[str, bool, str]:
    tid = str(team["id"])
    name = team["name"]
    out_path = os.path.join(LOGOS_DIR, f"{tid}.png")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
        return name, True, "cached"

    url = team.get("logo_url") or f"https://a.espncdn.com/i/teamlogos/ncaa/500/{tid}.png"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200 and resp.content:
            if _save_64x64_png(resp.content, out_path):
                return name, True, "downloaded"
        return name, False, f"HTTP {resp.status_code}"
    except Exception as e:
        return name, False, str(e)


def download_all_logos():
    with open(TEAMS_FILE) as f:
        teams = json.load(f)

    print(f"Ensuring 64x64 PNG logos for {len(teams)} FBS teams (PIL={HAS_PIL})...")
    ok_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(_download_one, t) for t in teams]
        for fut in as_completed(futures):
            name, ok, msg = fut.result()
            if ok:
                ok_count += 1
            else:
                fail_count += 1
                print(f"  ✗ Failed {name}: {msg}")

    print(f"Logo sync complete: {ok_count} ready, {fail_count} failed.")


if __name__ == "__main__":
    download_all_logos()
