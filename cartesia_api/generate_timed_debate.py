#!/usr/bin/env python3
"""Generate the full timecoded Glasswing debate with Cartesia Sonic 3.6.

Outputs full-length master and individual speaker stems aligned to the
5:18.4 silent picture described in CMNS.pdf.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from cartesia import Cartesia

SAMPLE_RATE = 44100
DURATION = 318.4
SPEAKERS = ("Liam", "George", "Nadia")
VOICE_IDS = {
    "Liam": "ed82c17b-4704-4d34-be43-5d19065acdf1",   # Carl
    "George": "65209f8e-6140-4a20-b819-3cc2e21da19b", # Nolan
    "Nadia": "a33f7a4c-100f-41cf-a1fd-5822e8fc253f",  # Lauren
}


def fit_clip(path: Path, max_seconds: float, out_path: Path) -> tuple[Path, float, float]:
    """Speed up only when needed; never let a line pass its printed out-time."""
    info = sf.info(path)
    actual = float(info.duration)
    if actual <= max_seconds:
        return path, 1.0, actual

    target = max(0.10, max_seconds - 0.025)
    tempo = actual / target
    if tempo > 1.40:
        raise RuntimeError(
            f"{path.name} needs {tempo:.2f}x to fit {max_seconds:.2f}s. "
            "A line would sound unnaturally rushed; please review that line."
        )
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to fit a long line to its timecode")
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(path), "-af", f"atempo={tempo:.6f}",
         "-ar", str(SAMPLE_RATE), "-ac", "1", str(out_path)],
        check=True,
    )
    fitted_duration = float(sf.info(out_path).duration)
    if fitted_duration > max_seconds:
        raise RuntimeError(f"Time-fit validation failed for {path.name}: {fitted_duration:.3f}s > {max_seconds:.3f}s")
    return out_path, tempo, fitted_duration


def read_mono(path: Path) -> np.ndarray:
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if sr != SAMPLE_RATE:
        raise RuntimeError(f"Unexpected sample rate in {path}: {sr}")
    if audio.shape[1] > 1:
        audio = np.mean(audio, axis=1, keepdims=True)
    return audio[:, 0]


def write_srt(lines: list[dict], path: Path) -> None:
    def stamp(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        hh, ms = divmod(ms, 3_600_000)
        mm, ms = divmod(ms, 60_000)
        ss, ms = divmod(ms, 1000)
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"
    rows = []
    for idx, line in enumerate(lines, 1):
        rows.append(
            f"{idx}\n{stamp(line['start'])} --> {stamp(line['end_actual'])}\n"
            f"{line['speaker'].upper()}: {line['text']}\n"
        )
    path.write_text("\n".join(rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dialogue", default="production/glasswing_cartesia/dialogue.json")
    parser.add_argument("--output-dir", default="out/glasswing-cartesia")
    args = parser.parse_args()

    key = os.environ.get("CARTESIA_API_KEY", "").strip()
    if not key:
        print("CARTESIA_API_KEY is missing. Add it in repository Actions secrets.", file=sys.stderr)
        return 2

    dialogue_path = Path(args.dialogue)
    out = Path(args.output_dir)
    clips = out / "clips"
    clips.mkdir(parents=True, exist_ok=True)

    spec = json.loads(dialogue_path.read_text(encoding="utf-8"))
    duration = float(spec["duration_seconds"])
    if abs(duration - DURATION) > 0.001:
        raise RuntimeError(f"Expected {DURATION}s source timeline, got {duration}")
    lines = spec["lines"]
    if len(lines) != 44:
        raise RuntimeError(f"Expected 44 spoken segments, got {len(lines)}")
    if {x["speaker"] for x in lines} != set(SPEAKERS):
        raise RuntimeError("Dialogue speaker map is incomplete")

    previous_end = 0.0
    for i, line in enumerate(lines, 1):
        if not (0 <= line["start"] < line["end"] <= duration):
            raise RuntimeError(f"Invalid time range on line {i}")
        if line["start"] < previous_end:
            raise RuntimeError(f"Overlapping timecodes at line {i}")
        previous_end = line["end"]

    client = Cartesia(api_key=key)
    total_samples = int(round(duration * SAMPLE_RATE))
    master = np.zeros(total_samples, dtype=np.float32)
    stems = {speaker: np.zeros(total_samples, dtype=np.float32) for speaker in SPEAKERS}
    report_lines = []

    for index, line in enumerate(lines, 1):
        speaker = line["speaker"]
        start = float(line["start"])
        max_seconds = float(line["end"]) - start
        raw_path = clips / f"line-{index:02d}-{speaker.lower()}-raw.wav"
        fitted_path = clips / f"line-{index:02d}-{speaker.lower()}-fit.wav"

        last_error = None
        speech_speed = float(line.get("speech_speed", 1.0))
        # Cached clips do not carry generation settings; regenerate explicitly accelerated lines.
        if raw_path.exists() and raw_path.stat().st_size >= 1000 and speech_speed <= 1.0:
            print(f"REUSE {index:02d}/44 {speaker}: {raw_path.stat().st_size:,} bytes", flush=True)
        else:
            raw_path.unlink(missing_ok=True)
            last_error = None
            for attempt in range(3):
                try:
                    response = client.tts.generate(
                        model_id=spec.get("model_id", "sonic-3.6"),
                        transcript=line["text"],
                        voice=VOICE_IDS[speaker],
                        output_format={
                            "container": "wav",
                            "encoding": "pcm_s16le",
                            "sample_rate": SAMPLE_RATE,
                        },
                        language="en",
                        generation_config={"speed": speech_speed, "volume": 1.0},
                    )
                    response.write_to_file(str(raw_path))
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
            if last_error is not None:
                raise RuntimeError(f"Cartesia failed on line {index} ({speaker}): {last_error}") from last_error

        if not raw_path.exists() or raw_path.stat().st_size < 1000:
            raise RuntimeError(f"Cartesia returned an empty file for line {index}")
        fitted_path.unlink(missing_ok=True)
        final_path, tempo, clip_seconds = fit_clip(raw_path, max_seconds, fitted_path)

        audio = read_mono(final_path)
        # Soft edge fades prevent audible clicks while retaining the source timing.
        fade = min(int(SAMPLE_RATE * 0.012), len(audio) // 4)
        if fade > 0:
            audio[:fade] *= np.linspace(0.0, 1.0, fade, dtype=np.float32)
            audio[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)

        start_sample = int(round(start * SAMPLE_RATE))
        end_sample = start_sample + len(audio)
        if end_sample > total_samples or end_sample > int(round(float(line["end"]) * SAMPLE_RATE)):
            raise RuntimeError(f"Audio for line {index} exceeds its final time window")
        master[start_sample:end_sample] += audio
        stems[speaker][start_sample:end_sample] += audio
        actual_end = start + clip_seconds
        report_lines.append({
            "index": index,
            "speaker": speaker,
            "voice_name": spec["voices"][speaker]["name"],
            "voice_id": VOICE_IDS[speaker],
            "start": start,
            "end": float(line["end"]),
            "end_actual": round(actual_end, 4),
            "target_window_seconds": round(max_seconds, 4),
            "generated_seconds": round(float(sf.info(raw_path).duration), 4),
            "final_seconds": round(clip_seconds, 4),
            "atempo": round(tempo, 4),
            "text": line["text"],
        })
        print(
            f"LINE {index:02d}/44 {speaker}: {clip_seconds:.2f}s "
            f"({start:.2f}-{actual_end:.2f})",
            flush=True,
        )

    peak = float(np.max(np.abs(master)))
    if peak > 0.98:
        gain = 0.98 / peak
        master *= gain
        for speaker in SPEAKERS:
            stems[speaker] *= gain

    out.mkdir(parents=True, exist_ok=True)
    sf.write(out / "dialogue.wav", master, SAMPLE_RATE, subtype="PCM_16")
    for speaker in SPEAKERS:
        sf.write(out / f"{speaker}.wav", stems[speaker], SAMPLE_RATE, subtype="PCM_16")

    write_srt(report_lines, out / "dialogue.srt")
    report = {
        "status": "passed",
        "episode": spec["title"],
        "source_video": spec["video_filename"],
        "duration_seconds": duration,
        "sample_rate": SAMPLE_RATE,
        "model_id": spec.get("model_id", "sonic-3.6"),
        "line_count": len(lines),
        "voice_mapping": spec["voices"],
        "timings": report_lines,
        "closing_silence_seconds": round(duration - report_lines[-1]["end_actual"], 3),
        "music": False,
    }
    (out / "audio-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Validate exact master/stem duration and timecode bounds.
    for path in [out / "dialogue.wav", *(out / f"{s}.wav" for s in SPEAKERS)]:
        info = sf.info(path)
        if abs(float(info.duration) - duration) > 0.025 or info.samplerate != SAMPLE_RATE:
            raise RuntimeError(f"Output validation failed: {path.name} {info}")
    if any(x["end_actual"] > x["end"] + 0.001 for x in report_lines):
        raise RuntimeError("One or more lines overran the published PDF timecodes")

    print(json.dumps({
        "status": "passed",
        "line_count": len(lines),
        "duration_seconds": duration,
        "voices": {k: v["name"] for k, v in spec["voices"].items()},
        "files": ["dialogue.wav", "Liam.wav", "George.wav", "Nadia.wav", "dialogue.srt", "audio-report.json"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
