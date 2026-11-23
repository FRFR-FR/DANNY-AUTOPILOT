#!/usr/bin/env python3
"""Small NOAA Ocean Exploration footage download/edit test.

Downloads two specifically identified NOAA Ocean Exploration MP4s, verifies
their content types and minimum sizes, makes short 720p H.264 excerpts, and
writes copy-ready credits. It does not scrape or bulk-download the archive.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path("noaa-test-output")
RAW = ROOT / "originals"
EDITED = ROOT / "clips"
RAW.mkdir(parents=True, exist_ok=True)
EDITED.mkdir(parents=True, exist_ok=True)

SOURCES = [
    {
        "id": "bigfin-squid",
        "title": "Bigfin Squid (Magnapinna sp.)",
        "url": "https://archive.oceanexplorer.noaa.gov/okeanos/explorations/ex2107/media-resources/media/ex2107-bigfin-squid.mp4",
        "page": "https://archive.oceanexplorer.noaa.gov/okeanos/explorations/ex2107/media-resources/bigfin-squid.html",
        "credit": "NOAA Ocean Exploration, Windows to the Deep 2021",
        "start": 90,\n        "crop": "crop=480:270:60:30,scale=1280:720",
        "duration": 12,
    },
    {
        "id": "deep-sea-sea-star",
        "title": "Deep-sea sea star (Sthenaster emmae) feeding on whip coral",
        "url": "https://oceanexplorer.noaa.gov/wp-content/uploads/2021/08/EX2104_VID_20210714_DIVE11_DEEP_SEA_DINING_Web2-1.mp4",
        "page": "https://oceanexplorer.noaa.gov/expedition-feature/okeanos-ex2104-features-hungryseastar/",
        "credit": "NOAA Ocean Exploration, 2021 North Atlantic Stepping Stones: New England and Corner Rise Seamounts",
        "start": 18,
        "duration": 12,
    },
]

def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, check=True)

def download(item: dict) -> Path:
    dest = RAW / f'{item["id"]}.mp4'
    req = urllib.request.Request(item["url"], headers={"User-Agent": "NOAA-footage-test/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response, dest.open("wb") as out:
        ctype = response.headers.get("Content-Type", "")
        if "video" not in ctype and "octet-stream" not in ctype:
            raise RuntimeError(f'Unexpected content type for {item["id"]}: {ctype}')
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    size = dest.stat().st_size
    if size < 100_000:
        raise RuntimeError(f"Download looks too small ({size} bytes): {dest}")
    print(f'Downloaded {dest}: {size / 1_000_000:.2f} MB', flush=True)
    return dest

def edit(item: dict, source: Path) -> Path:
    dest = EDITED / f'{item["id"]}_720p.mp4'
    draw = item["title"].replace(":", r"\:")
    framing = item.get("crop", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2")
    vf = (
        framing + ",setsar=1,fps=30,"
        f"drawtext=text='{draw}':fontcolor=white:fontsize=30:"
        "box=1:boxcolor=black@0.55:boxborderw=16:x=40:y=h-85"
    )
    run([
        "ffmpeg", "-y", "-ss", str(item["start"]), "-i", str(source),
        "-t", str(item["duration"]), "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest),
    ])
    if not dest.exists() or dest.stat().st_size < 50_000:
        raise RuntimeError(f"Edited clip missing or unexpectedly small: {dest}")
    print(f'Edited {dest}: {dest.stat().st_size / 1_000_000:.2f} MB', flush=True)
    return dest

def main() -> None:
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode:
        raise RuntimeError("ffmpeg is not installed")
    manifest = []
    clips = []
    for item in SOURCES:
        raw = download(item)
        clip = edit(item, raw)
        clips.append(clip)
        manifest.append({
            **item,
            "original_file": str(raw),
            "original_size_mb": round(raw.stat().st_size / 1_000_000, 2),
            "edited_file": str(clip),
            "edited_size_mb": round(clip.stat().st_size / 1_000_000, 2),
            "license_status": "NOAA Ocean Exploration page identifies the material as public domain; verify the specific page credit before publication.",
        })

    concat_list = ROOT / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve()}'\n" for p in clips), encoding="utf-8")
    final = ROOT / "noaa_deep_sea_test_compilation.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", "-movflags", "+faststart", str(final)])

    description = [
        "Deep-Sea Footage Test Compilation",
        "",
        "Footage courtesy of NOAA Ocean Exploration. The NOAA Ocean Exploration Video Portal states that its video holdings are public domain. The specific NOAA media pages below provide the credits for the clips used.",
        "",
        "FOOTAGE CREDITS",
    ]
    for item in SOURCES:
        description.extend([
            f'- {item["title"]} — Credit: {item["credit"]}. Source: {item["page"]}',
        ])
    description.extend([
        "",
        "NOAA Ocean Exploration media guidance: https://oceanexplorer.noaa.gov/about/media-kit/",
        "NOAA Ocean Exploration Video Portal: https://www.ncei.noaa.gov/access/ocean-exploration/video/",
        "",
        "This compilation is an independently edited excerpt and is not an official NOAA production or endorsement.",
    ])
    (ROOT / "youtube_description.txt").write_text("\n".join(description) + "\n", encoding="utf-8")
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"FINAL: {final} ({final.stat().st_size / 1_000_000:.2f} MB)", flush=True)
    print(f"CREDITS: {ROOT / 'youtube_description.txt'}", flush=True)

if __name__ == "__main__":
    main()
