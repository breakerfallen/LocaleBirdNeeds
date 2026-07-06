#!/usr/bin/env python3
"""
One-time: copies Teddy Warner's kacho-e illustrations into images/ from the
AvianVisitors assets that live elsewhere in this repository — they are NOT
duplicated in this folder (that would re-commit ~290 MB the repo already
carries). Run this once after cloning and the collage gets its full art set;
skip it and every species simply uses its typed silhouette.

    python3 fetch_bundled_art.py [path/to/avian/assets/illustrations]

Without an argument it looks in ../avian/assets/illustrations (the layout of
the `avian-visitors` branch this branch is based on).

images/_illustration_sources.json maps the repo's scientific-name slugs to the
(current eBird taxonomy) slugs this app installs them under — e.g. the repo's
accipiter-cooperii becomes astur-cooperii. Existing files are never
overwritten, so your own uploads and replacements are safe. Local file copies
only; nothing touches the network.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT, "images")
MAPPING = os.path.join(IMAGES_DIR, "_illustration_sources.json")
# AvianVisitors names the poses <slug>.png (perched) and <slug>-2.png (flight).
POSE_SRC_SUFFIX = {"perched": "", "flight": "-2"}
EXTS = (".png", ".jpg", ".jpeg", ".webp")


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
        os.path.join(ROOT, "..", "avian", "assets", "illustrations"))
    if not os.path.isdir(src_dir):
        print(f"Illustration folder not found: {src_dir}\n"
              "Pass the path to AvianVisitors' avian/assets/illustrations "
              "(it's in this repository on the `avian-visitors` branch).")
        return 1
    try:
        mapping = json.load(open(MAPPING))
    except OSError:
        print(f"Missing {MAPPING} — can't map repo slugs to installed names.")
        return 1

    copied = skipped = missing = 0
    for repo_slug, installed_slug in mapping.items():
        for pose, src_suffix in POSE_SRC_SUFFIX.items():
            src = next((p for ext in EXTS
                        if os.path.isfile(p := os.path.join(src_dir, f"{repo_slug}{src_suffix}{ext}"))),
                       None)
            if not src:
                missing += 1
                continue
            dst = os.path.join(IMAGES_DIR, f"{installed_slug}_{pose}" + os.path.splitext(src)[1])
            if os.path.exists(dst):
                skipped += 1
                continue
            shutil.copy2(src, dst)
            copied += 1
    print(f"Done. {copied} copied, {skipped} already present, {missing} not found in source.")
    print("Now seed their attribution:  python3 build_credits.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
