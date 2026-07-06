# LocaleBirdNeeds

*A live collage of the nearby birds you still **need** — sourced from eBird,
drawn to scale in the kachō-e woodblock style.*

![The collage in dark mode: birds drawn to scale on true black](ipad-display/docs/screenshot.png)

A local, self-hosted bird board for a spare tablet, iPad, or any second screen.
It shows birds reported near a point you choose in the last 30 days that are
still missing from your household's eBird life lists — the birds you haven't
seen yet — arranged as a spiral collage on warm "mulberry paper," each bird
sized by its real body length. Tap one for a map and table of its recent local
sightings.

**Everything stays local.** The only thing the running app talks to is the
eBird API (plus map tiles on the detail page). No accounts, no analytics; your
life lists, settings, and images never leave your machine.

## Get started

Everything lives in [`ipad-display/`](ipad-display/). See its
**[README](ipad-display/README.md)** for setup, configuration, the Atlas and
settings, updating life lists, and troubleshooting. The short version:

```
cd ipad-display
cp config.example.json config.json     # add your free eBird API key, location, and people
python3 fetch_bundled_art.py           # copy in the illustrations (see below)
python3 server.py                      # open the printed address on your display device
```

No dependencies — just Python 3.9+ from the standard library.

## About this project

LocaleBirdNeeds is a variant of **[AvianVisitors](README.avianvisitors.md)** by
Teddy Warner, which collages the birds a microphone *hears*. This project keeps
the collage, the atlas, and the woodblock aesthetic but draws from **eBird
sightings filtered by needs lists** instead — the birds nearby you still need.
New here: the life-list/needs model with CSV upload, to-scale sizing by body
length, silhouette-mask packing and hit-testing, "fresh arrivals fly" driven by
eBird polling, a true-black dark mode, and an in-app art uploader with
per-image attribution.

The lineage: **LocaleBirdNeeds → [AvianVisitors](README.avianvisitors.md) →
[BirdNET-Pi](README.upstream.md)**.

## Credits & license

The 249 bundled kachō-e illustrations are by **Teddy Warner**
([AvianVisitors](https://github.com/Twarner491/AvianVisitors)); they are not
re-committed here — `ipad-display/fetch_bundled_art.py` copies them from this
repository's own `avian/assets/illustrations/`. The species-code-named
illustrations added by this project are by
**[Breakerfallen](https://github.com/Breakerfallen)**. Anything you upload is
credited to you.

Licensed **CC BY-NC-SA 4.0** ([full text](ipad-display/LICENSE)) — attribution
required, non-commercial use only, share-alike — matching the parent project.
Per-image credits are in `ipad-display/images/CREDITS.md`.
