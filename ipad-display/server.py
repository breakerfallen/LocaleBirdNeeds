#!/usr/bin/env python3
"""
Needs Nearby — local server.

Runs on your Mac. Serves the app to a tablet or any second screen over your
home Wi-Fi, and is the
ONLY thing that talks to the network: it proxies eBird (so the browser never
hits a cross-origin API and your key stays on this machine) and serves the
local images + body-length table the app reads. Nothing calls Wikipedia or any
image service at display time.

    python3 server.py

Then on the display device open   http://<your-mac-name>.local:8080   (the URL is
printed on startup). Configuration lives in config.json.

Stdlib only — no pip install needed.
"""
import datetime
import json
import os
import re
import socket
import sys
import threading
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "app")
DATA_DIR = os.path.join(ROOT, "data")
IMAGES_DIR = os.path.join(ROOT, "images")
EBIRD_BASE = "https://api.ebird.org/v2"

# Fallbacks only — the real values live in config.json (copy
# config.example.json). lat/lng/place_label are the board's center point.
DEFAULT_CONFIG = {
    "ebird_api_key": "",
    "lat": 39.3906,
    "lng": -104.7486,
    "dist_km": 48,
    "back_days": 30,
    "port": 8080,
    "place_label": "home",
    "owner_name": "Owner",  # author credited on images you upload
    # The household: id -> display name. Ids become file names
    # (data/life_<id>.json) and settings values; set them in config.json.
    "people": {"kathryn": "Kathryn", "melissa": "Melissa"},
}

CC_BY_NC_SA = "CC BY-NC-SA 4.0"
CC_BY_NC_SA_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    path = os.path.join(ROOT, "config.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                cfg.update(json.load(f))
        except Exception as e:
            print(f"WARNING: couldn't read config.json ({e}); using defaults")
    else:
        print("WARNING: no config.json — copy config.example.json to config.json "
              "and set your eBird key, location (lat/lng/place_label), and people.")
    # env override so the key never has to be committed to a file
    cfg["ebird_api_key"] = os.environ.get("EBIRD_API_KEY", cfg.get("ebird_api_key", ""))
    return cfg


CONFIG = load_config()


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def write_json_atomic(path, obj):
    # Unique tmp name so concurrent writers (threaded server) can't collide.
    tmp = "%s.%d.%d.tmp" % (path, os.getpid(), threading.get_ident())
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def binomial(sci):
    return " ".join((sci or "").lower().split()[:2])


# ---- runtime settings (distance / days / whose) --------------------------
# User-adjustable from the cog on the board; persisted so a kiosk reload keeps
# them. Distance is stored in miles (eBird wants km, capped at its 50 km max).
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
MI_PER_KM = 0.621371
KM_PER_MI = 1.609344
MAX_DIST_MI = 31  # eBird's dist cap is 50 km ~= 31 mi


def load_settings():
    s = read_json(SETTINGS_PATH, {})
    default_mi = int(round(CONFIG.get("dist_km", 48) * MI_PER_KM))
    try:
        dist_mi = int(s.get("dist_miles", default_mi))
    except (TypeError, ValueError):
        dist_mi = default_mi
    dist_mi = max(1, min(MAX_DIST_MI, dist_mi))
    days = s.get("days", CONFIG.get("back_days", 30))
    if days not in (1, 3, 7, 30):
        days = 30
    whose = s.get("whose", "both")
    if whose != "both" and whose not in PEOPLE:
        whose = "both"
    theme = s.get("theme", "light")
    if theme not in ("light", "dark"):
        theme = "light"
    return {"dist_miles": dist_mi, "days": days, "whose": whose, "theme": theme}


def effective_dist_km(settings):
    return round(min(50.0, settings["dist_miles"] * KM_PER_MI), 1)


# ---- life lists / needs matching -----------------------------------------
# One model for everyone: each person has a life list (data/life_<person>.json,
# a list of {sci, common}), updated by uploading their eBird life-list CSV or
# by one-off edits. A bird is a NEED for a person iff it's not on their list.
# Who "everyone" is comes from config.json's "people" (id -> display name);
# ids are slugged because they become file names and settings values.
def _load_people():
    ppl = CONFIG.get("people") or DEFAULT_CONFIG["people"]
    out = {}
    for pid, label in ppl.items():
        pid = re.sub(r"[^a-z0-9_]", "", str(pid).lower())
        if pid:
            out[pid] = str(label).strip() or pid.title()
    return out or dict(DEFAULT_CONFIG["people"])


PEOPLE_LABELS = _load_people()
PEOPLE = tuple(PEOPLE_LABELS)


def life_path(person):
    return os.path.join(DATA_DIR, "life_%s.json" % person)


def load_life_sets():
    sets = {}
    for person in PEOPLE:
        entries = read_json(life_path(person), [])
        s = set()
        for e in entries:
            sci = (e.get("sci") or "").lower()
            if sci:
                s.add(sci)
                s.add(binomial(sci))
        sets[person] = s
    return sets


def need_status(sci_name, life_sets):
    sci = (sci_name or "").lower()
    bino = binomial(sci)
    return {p: not (sci in s or bino in s) for p, s in life_sets.items()}


def parse_lifelist_csv(text):
    """Parse an eBird life-list CSV export. Current exports have separate
    'Common Name' and 'Scientific Name' columns (plus 'Category'); older ones
    a single 'Species' column holding 'Common Name - Scientific Name'. Handles
    both, tolerant of column order and extra columns. Returns [{sci, common}]
    deduped."""
    import csv as csv_mod
    import io
    rows = list(csv_mod.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        return []

    # Locate a header row in the first few lines.
    header_i, cols = None, {}
    for i, row in enumerate(rows[:5]):
        names = {c.strip().lower(): j for j, c in enumerate(row)}
        if "scientific name" in names or "species" in names:
            header_i, cols = i, names
            break

    out, seen = [], set()

    def add(common, sci):
        common, sci = (common or "").strip(), (sci or "").strip()
        if len(sci.split()) < 2:  # not a binomial -> not a species row
            return
        key = sci.lower()
        if key in seen:
            return
        seen.add(key)
        out.append({"sci": sci, "common": common})

    if header_i is not None and "scientific name" in cols:
        sci_j = cols["scientific name"]
        com_j = cols.get("common name")
        cat_j = cols.get("category")
        for row in rows[header_i + 1:]:
            if len(row) <= sci_j:
                continue
            # keep species-level rows; skip spuhs/slashes/hybrids if flagged
            if cat_j is not None and len(row) > cat_j:
                cat = row[cat_j].strip().lower()
                if cat and cat not in ("species", "issf", "form", "domestic"):
                    continue
            add(row[com_j] if com_j is not None and len(row) > com_j else "", row[sci_j])
    else:
        # Older layout: one 'Species' column, 'Common Name - Scientific Name'.
        sp_j = cols.get("species", 1)
        start = header_i + 1 if header_i is not None else 0
        for row in rows[start:]:
            if len(row) <= sp_j or " - " not in row[sp_j]:
                continue
            common, sci = row[sp_j].strip().rsplit(" - ", 1)
            add(common, sci)

    out.sort(key=lambda e: (e["common"] or e["sci"]).lower())
    return out


# ---- species table (length + shape + local image) ------------------------
def load_species_table():
    return read_json(os.path.join(DATA_DIR, "species_data.json"), {})


# ---- image credit registry ----------------------------------------------
# data/image_credits.json maps an image base (eBird code for uploads, or a
# scientific-name slug for the bundled art) to its author + license. Bundled
# art is Teddy Warner's; uploads are credited to config.owner_name.
CREDITS_PATH = os.path.join(DATA_DIR, "image_credits.json")
_credits_cache = None


def load_credits():
    global _credits_cache
    if _credits_cache is None:
        _credits_cache = read_json(CREDITS_PATH, {})
    return _credits_cache


def save_credits(credits):
    global _credits_cache
    write_json_atomic(CREDITS_PATH, credits)
    _credits_cache = credits


def _img_slug(s):
    return re.sub(r"[^a-z ]", "", (s or "").lower()).strip().replace(" ", "-")


def _credit_for(url):
    """Attribution for a resolved /images/... URL, or None for silhouettes."""
    if not url or "/images/" not in url:
        return None
    fname = url.split("/images/", 1)[1].split("?", 1)[0]
    base = fname.rsplit(".", 1)[0].rsplit("_", 1)[0]  # strip ext + _perched/_flight
    return load_credits().get(base)


# Existence lookups go through an index of images/ rebuilt only when the
# directory's mtime changes (adds/removes/renames touch it). Probing the
# filesystem per species per request added up to thousands of stat calls on
# every /api/nearby and /api/atlas hit.
_img_index = {"mtime": None, "names": {}}
_IMG_EXT_PRIORITY = {"png": 0, "jpg": 1, "jpeg": 2, "webp": 3}


def _images_index():
    try:
        mt = os.path.getmtime(IMAGES_DIR)
    except OSError:
        return {}
    if _img_index["mtime"] != mt:
        names = {}
        for name in os.listdir(IMAGES_DIR):
            base, _, ext = name.rpartition(".")
            pri = _IMG_EXT_PRIORITY.get(ext.lower())
            if not base or pri is None:
                continue
            cur = names.get(base)
            if cur is None or pri < cur[1]:
                names[base] = (name, pri)
        _img_index["names"] = {b: n for b, (n, _) in names.items()}
        _img_index["mtime"] = mt
    return _img_index["names"]


def _find_image(base, suffix=""):
    """Local illustration for a species/pose, or None. Never a URL off this
    machine. `base` may be an eBird speciesCode (uploads / build_images output)
    or a scientific-name slug (the bundled AvianVisitors illustrations). A
    modification-time query busts the browser cache when a file is replaced."""
    if not base:
        return None
    name = _images_index().get(base + suffix)
    if not name:
        return None
    try:
        mt = int(os.path.getmtime(os.path.join(IMAGES_DIR, name)))
    except OSError:
        return None
    return "/images/%s?m=%d" % (name, mt)


def enrich(obs, table):
    sci = (obs.get("sciName") or "").lower()
    row = table.get(sci) or table.get(binomial(sci)) or {}
    length_in = row.get("lengthIn", 8)
    shape = row.get("shape", "songbird")
    guessed = "lengthIn" not in row
    code = obs.get("speciesCode") or ""
    bslug = _img_slug(binomial(sci))
    # Real art wins if on disk — keyed by eBird code or by scientific-name slug,
    # perched pose preferred; else the typed sumi-ink silhouette. Never a URL.
    perched = (_find_image(code, "_perched") or _find_image(bslug, "_perched")
               or _find_image(code) or _find_image(bslug))
    flight = _find_image(code, "_flight") or _find_image(bslug, "_flight")
    img = perched or ("/vendor/silhouettes/%s.svg?v=3" % shape)
    return {
        "lengthIn": length_in, "shape": shape, "guessedSize": guessed,
        "img": img, "imgFlight": flight, "hasArt": bool(perched),
        "credit": _credit_for(perched),
    }


# ---- sightings cache + atlas registry -------------------------------------
# eBird is polled at most once an hour (per distance); every page load in
# between is served from disk. Each fresh fetch also folds into a cumulative
# registry (data/atlas.json) of every species that has ever shown up here —
# that's what the Atlas page browses.
NEARBY_CACHE_PATH = os.path.join(DATA_DIR, "cache_nearby.json")
ATLAS_PATH = os.path.join(DATA_DIR, "atlas.json")
NEARBY_TTL_S = 3600
_cache_lock = threading.Lock()


# A species flies on the collage while it's a fresh arrival: first recorded by
# our polling within the last 24 h, or returning after being gone a while.
NEW_WINDOW_S = 24 * 3600
ARRIVAL_GAP_DAYS = 14  # unseen at least this long, then seen again = a re-arrival


def _obs_date(s):
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _gap_days(prev_obs, new_obs):
    # Signed: only a genuinely LATER sighting can count as a re-arrival. A
    # late-submitted old checklist (new obs date before lastSeen) must not
    # re-stamp the species as fresh.
    a, b = _obs_date(prev_obs), _obs_date(new_obs)
    return (b - a).days if (a and b) else 0


def _update_atlas(obs_list, fetched_at):
    atlas = read_json(ATLAS_PATH, {})
    for o in obs_list:
        code = o.get("speciesCode")
        if not code:
            continue
        cur = atlas.get(code) or {}
        new_dt = o.get("obsDt") or ""
        # Stamp the arrival time when the species is brand new, or when it comes
        # back after an absence; otherwise carry the existing stamp (0 = legacy /
        # continuing, so it won't suddenly fly).
        arrived = (not cur) or _gap_days(cur.get("lastSeen"), new_dt) >= ARRIVAL_GAP_DAYS
        first_fetched = fetched_at if arrived else cur.get("firstFetchedAt", 0)
        entry = {
            "speciesCode": code,
            "comName": o.get("comName") or cur.get("comName") or "",
            "sciName": o.get("sciName") or cur.get("sciName") or "",
            "firstSeen": cur.get("firstSeen") or new_dt,
            "lastSeen": max(cur.get("lastSeen") or "", new_dt),
            "lastLoc": cur.get("lastLoc") or "",
            "firstFetchedAt": first_fetched,
        }
        # The location follows the most-recent sighting only — a late-submitted
        # older checklist keeps the newer location.
        if new_dt >= (cur.get("lastSeen") or ""):
            entry["lastLoc"] = o.get("locName") or entry["lastLoc"]
        atlas[code] = entry
    write_json_atomic(ATLAS_PATH, atlas)


def get_nearby_obs():
    """Raw eBird obs for the current radius, from the disk cache when it's
    less than an hour old. Life-list filtering happens per-request afterwards,
    so list edits show up without waiting out the cache."""
    import time as _time
    st = load_settings()
    dist_km = effective_dist_km(st)
    with _cache_lock:
        cache = read_json(NEARBY_CACHE_PATH, {})
        fresh = (cache.get("dist_km") == dist_km and
                 _time.time() - cache.get("fetched_at", 0) < NEARBY_TTL_S)
        if fresh:
            return cache.get("obs", []), cache.get("fetched_at", 0)
        try:
            obs = ebird_get("/data/obs/geo/recent?" + q(
                lat=CONFIG["lat"], lng=CONFIG["lng"], dist=dist_km,
                back=CONFIG["back_days"], includeProvisional="true"))
        except Exception:
            if cache.get("obs"):  # eBird down -> serve stale rather than fail
                return cache["obs"], cache.get("fetched_at", 0)
            raise
        fetched_at = _time.time()
        write_json_atomic(NEARBY_CACHE_PATH, {
            "fetched_at": fetched_at, "dist_km": dist_km, "obs": obs})
        _update_atlas(obs, fetched_at)
        return obs, fetched_at


# ---- eBird proxy ---------------------------------------------------------
def ebird_get(path_and_query):
    if not CONFIG.get("ebird_api_key"):
        raise RuntimeError("No eBird API key set. Put it in config.json (ebird_api_key) "
                           "or the EBIRD_API_KEY environment variable.")
    req = urllib.request.Request(
        EBIRD_BASE + path_and_query,
        headers={"X-eBirdApiToken": CONFIG["ebird_api_key"]},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def q(**kw):
    return "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())


# ---- taxonomy (for the needs editor's species search) --------------------
_taxonomy_cache = None


def load_taxonomy():
    global _taxonomy_cache
    if _taxonomy_cache is not None:
        return _taxonomy_cache
    path = os.path.join(DATA_DIR, "taxonomy.json")
    tax = read_json(path, None)
    if not tax:
        tax = ebird_get("/ref/taxonomy/ebird?fmt=json&locale=en")
        write_json_atomic(path, tax)
    _taxonomy_cache = [
        {"comName": t.get("comName", ""), "sciName": t.get("sciName", ""),
         "speciesCode": t.get("speciesCode", "")}
        for t in tax if t.get("category") == "species"
    ]
    return _taxonomy_cache


class Handler(BaseHTTPRequestHandler):
    server_version = "NeedsNearby/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))

    # -- helpers --
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client (iPad) went away mid-response; nothing to do

    def send_file(self, fs_path):
        if not os.path.isfile(fs_path):
            self.send_error(404, "Not found")
            return
        ext = os.path.splitext(fs_path)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(fs_path, "rb") as f:
            data = f.read()
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            # Hard-cache only the generated raster art (it never changes once
            # written). Silhouettes/SVG and pages stay revalidated so restyles and
            # rebuilds show up immediately.
            if ext in (".png", ".jpg", ".jpeg", ".webp") and os.path.normpath(IMAGES_DIR) in os.path.normpath(fs_path):
                self.send_header("Cache-Control", "public, max-age=31536000")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def resolve_static(self, path):
        # Map a URL path to a file on disk, jailed to known roots.
        if path == "/" or path == "":
            return os.path.join(APP_DIR, "index.html")
        if path.startswith("/images/"):
            base, rel = IMAGES_DIR, path[len("/images/"):]
        elif path.startswith("/data/"):
            base, rel = DATA_DIR, path[len("/data/"):]
        else:
            base, rel = APP_DIR, path.lstrip("/")
        rel = urllib.parse.unquote(rel)
        full = os.path.normpath(os.path.join(base, rel))
        if not full.startswith(os.path.normpath(base) + os.sep) and full != os.path.normpath(base):
            return None  # path traversal attempt
        return full

    # -- GET --
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self.handle_api_get(path, urllib.parse.parse_qs(parsed.query))
        fs_path = self.resolve_static(path)
        if fs_path is None:
            return self.send_error(403, "Forbidden")
        self.send_file(fs_path)

    def handle_api_get(self, path, qs):
        try:
            if path == "/api/config":
                counts = {p: len(read_json(life_path(p), [])) for p in PEOPLE}
                st = load_settings()
                return self.send_json({
                    "lat": CONFIG["lat"], "lng": CONFIG["lng"],
                    "dist_km": effective_dist_km(st), "dist_miles": st["dist_miles"],
                    "max_dist_miles": MAX_DIST_MI,
                    "days": st["days"], "whose": st["whose"], "theme": st["theme"],
                    "back_days": CONFIG["back_days"],
                    "place_label": CONFIG.get("place_label", CONFIG.get("location_label", "")),
                    "has_key": bool(CONFIG.get("ebird_api_key")),
                    "people": [{"id": p, "label": PEOPLE_LABELS[p]} for p in PEOPLE],
                    "life_counts": counts,
                })

            if path == "/api/nearby":
                import time as _t
                obs, fetched_at = get_nearby_obs()
                life_sets = load_life_sets()
                # An empty life list means "not uploaded yet", not "needs every
                # bird on earth" — treat that person as needing nothing so the
                # board isn't flooded before their first CSV upload.
                active = {p: s for p, s in life_sets.items() if s}
                table = load_species_table()
                atlas = read_json(ATLAS_PATH, {})
                now_ts = _t.time()
                out = []
                for o in obs:
                    needs = need_status(o.get("sciName"), active)
                    if not any(needs.values()):
                        continue
                    o = dict(o)
                    o["needs"] = needs
                    o.update(enrich(o, table))
                    # Fresh arrival (first recorded < 24 h ago) flies, if it has a
                    # flight illustration; everything else is perched.
                    ff = (atlas.get(o.get("speciesCode")) or {}).get("firstFetchedAt", 0)
                    is_new = bool(ff) and (now_ts - ff < NEW_WINDOW_S)
                    o["isNew"] = is_new
                    if is_new and o.get("imgFlight"):
                        o["img"] = o["imgFlight"]
                        o["pose"] = "flight"
                    else:
                        o["pose"] = "perched"
                    out.append(o)
                out.sort(key=lambda x: x["lengthIn"], reverse=True)
                return self.send_json({"obs": out, "fetched_at": fetched_at})

            if path == "/api/atlas":
                atlas = read_json(ATLAS_PATH, {})
                life_sets = load_life_sets()
                active = {p: s for p, s in life_sets.items() if s}
                table = load_species_table()
                out = []
                for e in atlas.values():
                    row = dict(e)
                    row["needs"] = need_status(e.get("sciName"), active)
                    row.update(enrich(e, table))
                    out.append(row)
                out.sort(key=lambda x: x.get("lastSeen") or "", reverse=True)
                return self.send_json(out)

            if path == "/api/species":
                code = qs.get("code", [""])[0]
                if not code:
                    return self.send_json({"error": "code required"}, 400)
                # Same radius the board is using (the cog setting), not the
                # static config default — otherwise the detail page shows
                # sightings from outside the chosen circle.
                dist_km = effective_dist_km(load_settings())
                data = ebird_get("/data/obs/geo/recent/%s?" % urllib.parse.quote(code) + q(
                    lat=CONFIG["lat"], lng=CONFIG["lng"], dist=dist_km,
                    back=CONFIG["back_days"], includeProvisional="true", maxResults=200))
                table = load_species_table()
                info = {}
                if data:
                    info = enrich(data[0], table)
                    life_sets = load_life_sets()
                    active = {p: s for p, s in life_sets.items() if s}
                    info["needs"] = need_status(data[0].get("sciName"), active)
                return self.send_json({"sightings": data, "info": info})

            if path == "/api/species-art":
                code = qs.get("code", [""])[0]
                sci = qs.get("sci", [""])[0]
                info = enrich({"speciesCode": code, "sciName": sci}, load_species_table())
                return self.send_json({"img": info["img"], "imgFlight": info["imgFlight"],
                                       "hasArt": info["hasArt"]})

            if path == "/api/species-search":
                term = (qs.get("q", [""])[0] or "").strip().lower()
                if len(term) < 2:
                    return self.send_json([])
                tax = load_taxonomy()
                hits = [t for t in tax
                        if term in t["comName"].lower() or term in t["sciName"].lower()]
                hits.sort(key=lambda t: (not t["comName"].lower().startswith(term), t["comName"]))
                return self.send_json(hits[:25])

            return self.send_json({"error": "unknown endpoint"}, 404)
        except urllib.error.HTTPError as e:
            return self.send_json({"error": "eBird error %s: %s" % (e.code, e.reason)}, 502)
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)

    # -- image upload / delete (user-supplied art, keyed by eBird code) --
    @staticmethod
    def _sniff_image(raw):
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if raw.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":  # RIFF alone is also WAV/AVI
            return "webp"
        return None

    def handle_image(self, path, payload):
        import base64 as _b64
        code = (payload.get("code") or "").strip().lower()
        pose = payload.get("pose")
        if not re.fullmatch(r"[a-z0-9]+", code or "") or pose not in ("perched", "flight"):
            return self.send_json({"error": "valid code and pose (perched/flight) required"}, 400)
        base = "%s_%s" % (code, pose)

        # Only ever touch user-uploaded, code-named files — never bundled art.
        existing = [f for f in os.listdir(IMAGES_DIR)
                    if f.rsplit(".", 1)[0] == base and "." in f]

        if path == "/api/delete-image":
            for f in existing:
                os.remove(os.path.join(IMAGES_DIR, f))
            # drop the credit only if no poses remain for this code
            if not any(fn.startswith(code + "_") for fn in os.listdir(IMAGES_DIR)):
                credits = load_credits()
                if credits.pop(code, None) is not None:
                    save_credits(credits)
            return self.send_json({"ok": True, "removed": len(existing)})

        data_url = payload.get("dataUrl") or ""
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        try:
            raw = _b64.b64decode(b64)
        except Exception:
            return self.send_json({"error": "couldn't decode the image data"}, 400)
        if len(raw) > 12 * 1024 * 1024:
            return self.send_json({"error": "image too large (max 12 MB)"}, 400)
        ext = self._sniff_image(raw)
        if not ext:
            return self.send_json({"error": "not a PNG, JPEG, or WebP image"}, 400)

        for f in existing:  # replace any prior upload for this species+pose
            os.remove(os.path.join(IMAGES_DIR, f))
        with open(os.path.join(IMAGES_DIR, base + "." + ext), "wb") as fh:
            fh.write(raw)
        # attribute the upload to the app's owner
        credits = load_credits()
        credits[code] = {"author": CONFIG.get("owner_name", "Owner"),
                         "license": CC_BY_NC_SA, "licenseUrl": CC_BY_NC_SA_URL,
                         "source": "Uploaded"}
        save_credits(credits)
        return self.send_json({"ok": True, "file": base + "." + ext})

    # -- POST (settings + life lists + image uploads) --
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/lifelist", "/api/settings",
                               "/api/upload-image", "/api/delete-image"):
            return self.send_json({"error": "unknown endpoint"}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

            if parsed.path in ("/api/upload-image", "/api/delete-image"):
                return self.handle_image(parsed.path, payload)

            if parsed.path == "/api/settings":
                cur = load_settings()
                if "dist_miles" in payload:
                    try:
                        cur["dist_miles"] = max(1, min(MAX_DIST_MI, int(payload["dist_miles"])))
                    except (TypeError, ValueError):
                        pass
                if payload.get("days") in (1, 3, 7, 30):
                    cur["days"] = payload["days"]
                if payload.get("whose") == "both" or payload.get("whose") in PEOPLE:
                    cur["whose"] = payload["whose"]
                if payload.get("theme") in ("light", "dark"):
                    cur["theme"] = payload["theme"]
                write_json_atomic(SETTINGS_PATH, cur)
                return self.send_json({"ok": True, "settings": cur,
                                       "dist_km": effective_dist_km(cur)})

            person = payload.get("person")
            action = payload.get("action")
            if person not in PEOPLE:
                return self.send_json({"error": "person must be one of %s" % (PEOPLE,)}, 400)
            path = life_path(person)

            if action == "upload":
                entries = parse_lifelist_csv(payload.get("csv") or "")
                if not entries:
                    return self.send_json({"error": "No species found in that file. "
                                           "Expected an eBird life-list CSV export — either "
                                           "separate Common Name / Scientific Name columns, or a "
                                           "Species column like 'Mallard - Anas platyrhynchos'."}, 400)
                write_json_atomic(path, entries)
                return self.send_json({"ok": True, "count": len(entries)})

            sci = (payload.get("sci") or "").strip()
            common = (payload.get("common") or "").strip()
            if action not in ("add", "remove") or not sci:
                return self.send_json({"error": "need action (upload/add/remove) and sci"}, 400)
            items = read_json(path, [])
            items = [e for e in items if (e.get("sci") or "").lower() != sci.lower()]
            if action == "add":
                items.append({"sci": sci, "common": common})
            items.sort(key=lambda e: (e.get("common") or e.get("sci") or "").lower())
            write_json_atomic(path, items)
            return self.send_json({"ok": True, "count": len(items)})
        except Exception as e:
            return self.send_json({"error": str(e)}, 500)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    port = int(CONFIG.get("port", 8080))
    host = socket.gethostname()
    if host and not host.endswith(".local"):
        host_local = host.split(".")[0] + ".local"
    else:
        host_local = host
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("\n  Needs Nearby is running.")
    print("  Center: %s (%.4f, %.4f) — change in config.json." % (
        CONFIG.get("place_label", CONFIG.get("location_label", "home")),
        CONFIG["lat"], CONFIG["lng"]))
    print("  On the display device (same Wi-Fi), open one of:")
    print(f"      http://{host_local}:{port}")
    print(f"      http://{lan_ip()}:{port}")
    if not CONFIG.get("ebird_api_key"):
        print("\n  ! No eBird API key yet — set ebird_api_key in config.json.")
        print("    Get a free key at https://ebird.org/api/keygen")
    print("\n  Ctrl-C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    main()
