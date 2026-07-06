#!/usr/bin/env python3
"""
Seeds data/image_credits.json — attribution for every image in images/.

Bundled scientific-name-slug illustrations came from Teddy Warner's
AvianVisitors repo (CC BY-NC-SA 4.0). Code-named files are uploads, credited to
the app owner. Re-running preserves existing entries and only fills gaps, so
per-upload credits recorded by the server aren't clobbered.

    python3 build_credits.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT, "images")
DATA_DIR = os.path.join(ROOT, "data")
CC = "CC BY-NC-SA 4.0"
CC_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"


def main():
    cfg = {}
    p = os.path.join(ROOT, "config.json")
    if os.path.exists(p):
        cfg = json.load(open(p))
    owner = cfg.get("owner_name", "Owner")

    credits_path = os.path.join(DATA_DIR, "image_credits.json")
    credits = json.load(open(credits_path)) if os.path.exists(credits_path) else {}

    teddy = {"author": "Teddy Warner", "license": CC, "licenseUrl": CC_URL,
             "source": "AvianVisitors (github.com/Twarner491/AvianVisitors)"}
    owner_cr = {"author": owner, "license": CC, "licenseUrl": CC_URL, "source": "Uploaded"}

    # bundled illustrations: bases that are scientific-name slugs (contain a hyphen)
    bundled = added_b = added_u = 0
    bases = {}  # base -> "bundled" | "upload"
    for f in os.listdir(IMAGES_DIR):
        m = re.match(r"^(.+)_(perched|flight)\.(png|jpg|jpeg|webp)$", f)
        if not m:
            continue
        base = m.group(1)
        bases[base] = "upload" if re.fullmatch(r"[a-z0-9]+", base) else "bundled"

    for base, kind in bases.items():
        if base in credits:
            continue
        credits[base] = dict(teddy if kind == "bundled" else owner_cr)
        if kind == "bundled":
            added_b += 1
        else:
            added_u += 1

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(credits_path, "w") as fh:
        json.dump(credits, fh, indent=0, sort_keys=True)
    print(f"image_credits.json: {len(credits)} total "
          f"(+{added_b} bundled → Teddy Warner, +{added_u} uploads → {owner})")


if __name__ == "__main__":
    main()
