#!/usr/bin/env python3
"""
OPTIONAL, one-time. Generates kacho-e (Edo-period Japanese woodblock) bird
illustrations into images/ so the collage shows art instead of sumi-ink
silhouettes. Two poses per bird — perched (shown on the board) and in flight
(shown via the toggle on the detail page).

The running app NEVER calls this. It only ever reads the PNGs left behind, so
once generated the app still makes zero non-eBird calls. Skip it entirely and
everything works with silhouettes.

    python3 build_images.py                # art for the birds showing nearby now
    python3 build_images.py --perched-only # skip the in-flight pose (half the cost)
    python3 build_images.py <code> ...     # specific eBird species codes

Three providers (set "image_provider" in config.json, or let it auto-pick):
  - pollinations  — FREE, no key, no signup. Flux model. Default when no key is
    set. Anonymous use is rate-limited (~1 image / 15s) so this throttles itself;
    a full nearby set takes a few minutes. Baked cream background (Flux can't do
    transparency), so birds sit on paper-matched tiles rather than floating.
  - openai        — "openai_api_key"; gpt-image-1 with a real transparent
    background (cleanest float on the paper). A few cents per image.
  - gemini        — "gemini_api_key"; Imagen 3. A few cents per image.
Existing files are skipped so the set stays small.
"""
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT, "images")

POSE_WORD = {"perched": "perched", "flight": "flying"}
POSES = POSE_WORD  # names of the poses to iterate


def load_cfg():
    c = {}
    p = os.path.join(ROOT, "config.json")
    if os.path.exists(p):
        with open(p) as f:
            c = json.load(f)
    provider = c.get("image_provider", "").lower()
    openai_key = os.environ.get("OPENAI_API_KEY", c.get("openai_api_key", ""))
    gemini_key = os.environ.get("GEMINI_API_KEY", c.get("gemini_api_key", ""))
    if not provider:
        # Prefer a real transparent background if a paid key exists; else free.
        provider = "openai" if openai_key else ("gemini" if gemini_key else "pollinations")
    return provider, openai_key, gemini_key, c.get("port", 8080)


# Short, correct field-mark notes fed into the prompt to keep Flux honest about
# plumage (it renders the kacho-e style well but invents species detail without
# this). Same idea as AvianVisitors' per-species prompt addenda. Keyed by
# scientific binomial (lowercase). Extend as you generate more species.
FIELD_MARKS = {
    "dolichonyx oryzivorus": "Breeding male: mostly BLACK face and underparts, a large STRAW-YELLOW/buff patch across the back of the head and nape, white scapulars and white rump. Sparrow-sized, short conical finch bill.",
    "chlidonias niger": "Breeding: jet-black head and underparts, slate-gray back and wings, white undertail. Slender pointed black bill, short slightly forked tail. A small marsh tern.",
    "psiloscops flammeolus": "A very small gray screech-owl with DARK eyes (not yellow), delicate rufous-and-gray bark-like facial pattern, tiny ear tufts.",
    "calidris fuscicollis": "A small sandpiper (peep), long wings reaching past the tail, finely streaked brownish breast, rusty edges on crown and back, a WHITE rump band, thin straight black bill.",
    "spiza americana": "Male: gray head with a yellow eyebrow and yellow breast, a BLACK V-bib on the throat, chestnut shoulder patch, stout pale bill — like a tiny meadowlark.",
    "empidonax minimus": "A tiny olive-gray flycatcher with a bold white eyering, two white wingbars, pale throat, short bill; upright posture.",
}


def prompt_for(common, sci, pose):
    pose_clause = ("Perched: one wing folded, the other tucked."
                   if pose == "perched" else "Flight: both wings fully extended.")
    marks = FIELD_MARKS.get(" ".join((sci or "").lower().split()[:2]), "")
    marks_line = (" Field marks to get right: " + marks) if marks else ""
    return (
        f"Generate a {POSE_WORD[pose]} {common} ({sci}) in the style of an "
        "Edo-period Japanese kacho-e woodblock print. Render with VERY FEW "
        "MARKS: the body is 2-4 flat color zones with sharp boundaries, not "
        "feather-by-feather texture. Confident sumi-e ink linework, soft "
        "watercolor washes. Earthy palette: burnt umber, ochre, indigo, "
        "vermillion, muted greens. Eye, beak, and feet in crisp ink. "
        "The bird sits on a CONSISTENT WARM CREAM ground (aged mulberry paper), "
        "filling the frame, identical across every print. This is the only "
        "background: NO branch, NO twig, NO perch, NO scenery, NO border, NO "
        "frame, NO margin, NO seal stamp, NO signature; the cream ground runs "
        "edge to edge. The perch is implied by toe posture, never drawn. "
        "Exactly two wings, two legs, one head, one beak, one tail. Posture, "
        f"color, and markings match {common} field references.{marks_line} "
        f"{pose_clause}"
    )


def _slug(sci):
    return re.sub(r"[^a-z ]", "", (sci or "").lower()).strip().replace(" ", "-")


def already_have(code, sci, pose):
    """True if art for this species+pose already exists under the eBird code or
    the scientific-name slug (so bundled illustrations aren't overwritten)."""
    bslug = _slug(" ".join((sci or "").split()[:2]))
    for base in (code, bslug):
        if not base:
            continue
        for ext in (".png", ".jpg", ".webp"):
            if os.path.exists(os.path.join(IMAGES_DIR, f"{base}_{pose}{ext}")):
                return True
            if os.path.exists(os.path.join(IMAGES_DIR, f"{base}{ext}")):
                return True
    return False


def gen_openai(prompt, key):
    body = json.dumps({
        "model": "gpt-image-1", "prompt": prompt, "size": "1024x1024",
        "background": "transparent", "n": 1,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
    return base64.b64decode(data["data"][0]["b64_json"])


def gen_gemini(prompt, key):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "imagen-3.0-generate-002:predict?key=" + key)
    body = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
    return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])


def gen_pollinations(prompt, _key):
    # Free, no key. GET returns the image bytes directly.
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
           "?width=1024&height=1024&model=flux&nologo=true")
    req = urllib.request.Request(url, headers={"User-Agent": "NeedsNearby/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def nearby(port):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/api/nearby", timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Couldn't reach the running server ({e}). Start server.py first, "
              f"or pass explicit eBird codes.")
        return []


def targets(argv, port):
    codes = [a for a in argv if not a.startswith("-")]
    nb = {o["speciesCode"]: (o["comName"], o["sciName"]) for o in nearby(port)}
    if codes:
        return [(c, *nb.get(c, (c, ""))) for c in codes]
    return [(c, cn, sn) for c, (cn, sn) in nb.items()]


def main():
    argv = sys.argv[1:]
    perched_only = "--perched-only" in argv
    provider, openai_key, gemini_key, port = load_cfg()

    GENERATORS = {"openai": gen_openai, "gemini": gen_gemini, "pollinations": gen_pollinations}
    if provider == "openai" and not openai_key:
        print("image_provider is openai but no openai_api_key set."); return
    if provider == "gemini" and not gemini_key:
        print("image_provider is gemini but no gemini_api_key set."); return
    if provider not in GENERATORS:
        print(f"Unknown image_provider '{provider}'. Use pollinations, openai, or gemini."); return

    key = {"openai": openai_key, "gemini": gemini_key}.get(provider, "")
    gen = GENERATORS[provider]
    throttle = 15 if provider == "pollinations" else 0  # anon rate limit
    poses = ["perched"] if perched_only else list(POSES)

    os.makedirs(IMAGES_DIR, exist_ok=True)
    todo = targets(argv, port)
    if not todo:
        print("Nothing to generate.")
        return

    made = skipped = failed = 0
    print(f"Provider: {provider}. {len(todo)} species, poses: {', '.join(poses)}."
          + (f" (~{throttle}s between images)" if throttle else "") + "\n")
    for code, common, sci in todo:
        for pose in poses:
            if already_have(code, sci, pose):
                skipped += 1
                continue
            out = os.path.join(IMAGES_DIR, f"{code}_{pose}.png")
            try:
                print(f"  {common} — {pose}…")
                data = gen(prompt_for(common, sci, pose), key)
                with open(out, "wb") as f:
                    f.write(data)
                made += 1
                if throttle:
                    time.sleep(throttle)
            except Exception as e:
                print(f"    failed: {e}")
                failed += 1
    print(f"\nDone. {made} generated, {skipped} already existed, {failed} failed.")


if __name__ == "__main__":
    main()
