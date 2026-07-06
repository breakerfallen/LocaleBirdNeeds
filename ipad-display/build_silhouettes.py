#!/usr/bin/env python3
"""
Writes the typed bird silhouettes into app/vendor/silhouettes/. One SVG per
body-shape group referenced by data/species_data.json ("shape" field). Pure
local generation, no network. Run once:

    python3 build_silhouettes.py

All silhouettes share a 100x100 viewBox and sit on a common baseline, so when
the grid scales an image's width by the bird's body length the relative sizes
stay honest. Head faces left (field-guide convention).
"""
import os

FILL = "#33302a"  # sumi ink, for reading on the warm cream ground
VB = ('width="100" height="100" viewBox="0 0 100 100" '
      'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMax meet"')

# Each entry is the inner SVG for that shape group.
SHAPES = {
    "songbird": """
      <ellipse cx="55" cy="52" rx="27" ry="19"/>
      <circle cx="31" cy="40" r="12"/>
      <polygon points="19,39 5,42 19,46"/>
      <polygon points="78,50 96,58 80,61"/>
      <path d="M48 69 L46 88 M60 69 L62 88" stroke="{f}" stroke-width="2.4" fill="none"/>
    """,
    "waterfowl": """
      <ellipse cx="56" cy="50" rx="38" ry="17"/>
      <path d="M28 44 Q22 30 20 30" stroke="{f}" stroke-width="9" fill="none" stroke-linecap="round"/>
      <circle cx="20" cy="33" r="10"/>
      <polygon points="12,31 2,33 12,39"/>
      <polygon points="90,46 99,42 88,53"/>
    """,
    "wader": """
      <ellipse cx="60" cy="47" rx="21" ry="12"/>
      <path d="M44 40 Q34 24 30 15" stroke="{f}" stroke-width="6" fill="none" stroke-linecap="round"/>
      <circle cx="29" cy="14" r="7"/>
      <polygon points="23,13 6,16 23,17"/>
      <polygon points="78,45 90,47 78,50"/>
      <path d="M53 58 L50 92 M66 58 L69 92" stroke="{f}" stroke-width="2.2" fill="none"/>
    """,
    "raptor": """
      <ellipse cx="53" cy="56" rx="20" ry="26"/>
      <circle cx="46" cy="26" r="13"/>
      <path d="M34 24 Q26 25 30 32 Q34 30 36 29 Z"/>
      <polygon points="60,76 72,94 52,82"/>
      <path d="M47 80 L46 92 M57 78 L58 92" stroke="{f}" stroke-width="2.8" fill="none"/>
    """,
    "falcon": """
      <ellipse cx="53" cy="56" rx="16" ry="26"/>
      <circle cx="47" cy="26" r="12"/>
      <path d="M36 24 Q28 25 32 31 Q36 29 38 28 Z"/>
      <polygon points="60,44 88,30 62,58"/>
      <polygon points="58,78 68,94 50,82"/>
      <path d="M48 80 L47 92 M56 78 L57 92" stroke="{f}" stroke-width="2.6" fill="none"/>
    """,
    "owl": """
      <ellipse cx="50" cy="62" rx="23" ry="25"/>
      <circle cx="50" cy="31" r="23"/>
      <polygon points="32,12 40,28 46,15"/>
      <polygon points="54,15 60,28 68,12"/>
      <path d="M43 85 L42 94 M57 85 L58 94" stroke="{f}" stroke-width="2.8" fill="none"/>
    """,
    "shorebird": """
      <ellipse cx="56" cy="48" rx="24" ry="15"/>
      <circle cx="29" cy="38" r="10"/>
      <polygon points="19,37 7,40 19,42"/>
      <polygon points="78,46 92,50 78,53"/>
      <path d="M50 62 L48 90 M63 62 L65 90" stroke="{f}" stroke-width="2.2" fill="none"/>
    """,
    "gull": """
      <ellipse cx="53" cy="47" rx="34" ry="15"/>
      <circle cx="20" cy="39" r="9"/>
      <polygon points="11,38 1,40 11,42"/>
      <polygon points="78,44 99,50 80,54"/>
      <path d="M48 60 L47 74 M59 60 L60 74" stroke="{f}" stroke-width="2.2" fill="none"/>
    """,
    "dove": """
      <ellipse cx="50" cy="51" rx="26" ry="18"/>
      <circle cx="24" cy="41" r="9"/>
      <polygon points="16,40 8,41 16,44"/>
      <polygon points="74,49 99,55 76,58"/>
      <path d="M46 66 L45 80 M57 66 L58 80" stroke="{f}" stroke-width="2.2" fill="none"/>
    """,
    "hummingbird": """
      <ellipse cx="54" cy="50" rx="16" ry="11"/>
      <circle cx="38" cy="44" r="8"/>
      <polygon points="31,43 5,45 31,47"/>
      <polygon points="54,46 78,28 60,52"/>
      <polygon points="66,52 82,58 66,56"/>
    """,
    "woodpecker": """
      <ellipse cx="50" cy="58" rx="15" ry="30"/>
      <circle cx="50" cy="23" r="12"/>
      <polygon points="45,13 41,1 51,13"/>
      <polygon points="44,84 50,98 56,84"/>
      <path d="M40 60 L33 63 M60 60 L67 63" stroke="{f}" stroke-width="2.6" fill="none"/>
    """,
    "corvid": """
      <ellipse cx="55" cy="53" rx="30" ry="20"/>
      <circle cx="27" cy="41" r="13"/>
      <polygon points="15,39 2,43 15,46"/>
      <polygon points="80,51 100,57 82,62"/>
      <path d="M50 72 L48 90 M63 72 L65 90" stroke="{f}" stroke-width="2.6" fill="none"/>
    """,
    "swallow": """
      <ellipse cx="52" cy="51" rx="22" ry="9"/>
      <circle cx="29" cy="47" r="8"/>
      <polygon points="21,46 14,47 21,49"/>
      <polygon points="46,49 86,22 58,53"/>
      <polygon points="66,53 96,50 78,56 96,66 70,58"/>
    """,
    "gamebird": """
      <ellipse cx="53" cy="59" rx="30" ry="22"/>
      <path d="M32 44 Q26 34 24 34" stroke="{f}" stroke-width="8" fill="none" stroke-linecap="round"/>
      <circle cx="24" cy="37" r="9"/>
      <path d="M24 27 Q22 20 26 18" stroke="{f}" stroke-width="2.2" fill="none"/>
      <polygon points="15,37 9,38 15,41"/>
      <polygon points="78,50 94,36 80,60"/>
      <path d="M48 79 L46 93 M60 79 L62 93" stroke="{f}" stroke-width="3" fill="none"/>
    """,
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "app", "vendor", "silhouettes")
    os.makedirs(out_dir, exist_ok=True)
    for shape, inner in SHAPES.items():
        body = inner.strip().replace("{f}", FILL)
        svg = f'<svg {VB} fill="{FILL}">\n{body}\n</svg>\n'
        with open(os.path.join(out_dir, f"{shape}.svg"), "w") as f:
            f.write(svg)
    print(f"Wrote {len(SHAPES)} silhouettes to {out_dir}")


if __name__ == "__main__":
    main()
