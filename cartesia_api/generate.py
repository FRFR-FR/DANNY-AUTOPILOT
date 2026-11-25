#!/usr/bin/env python3
"""Generate a WAV voiceover using Cartesia's Python SDK.

Required environment variables:
  CARTESIA_API_KEY
  CARTESIA_TRANSCRIPT

Optional:
  CARTESIA_VOICE_ID (defaults to Cartesia's stock English Skylar voice)
  CARTESIA_MODEL_ID (defaults to sonic-latest)
  CARTESIA_OUTPUT_PATH (defaults to output/cartesia.wav)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cartesia import Cartesia

DEFAULT_VOICE_ID = "f786b574-daa5-4673-aa0c-cbe3e8534c02"
DEFAULT_MODEL_ID = "sonic-latest"


def main() -> int:
    api_key = os.environ.get("CARTESIA_API_KEY", "").strip()
    transcript = os.environ.get("CARTESIA_TRANSCRIPT", "").strip()
    voice_id = os.environ.get("CARTESIA_VOICE_ID", DEFAULT_VOICE_ID).strip()
    model_id = os.environ.get("CARTESIA_MODEL_ID", DEFAULT_MODEL_ID).strip()
    output_path = Path(os.environ.get("CARTESIA_OUTPUT_PATH", "output/cartesia.wav"))

    if not api_key:
        print("Error: CARTESIA_API_KEY is missing. Add it as a GitHub Actions secret.", file=sys.stderr)
        return 2
    if not transcript:
        print("Error: CARTESIA_TRANSCRIPT is empty.", file=sys.stderr)
        return 2
    if not voice_id:
        print("Error: CARTESIA_VOICE_ID is empty.", file=sys.stderr)
        return 2

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        client = Cartesia(api_key=api_key)
        response = client.tts.generate(
            model_id=model_id,
            transcript=transcript,
            voice=voice_id,
            output_format={
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 44100,
            },
            language="en",
        )
        response.write_to_file(str(output_path))
    except Exception as exc:  # SDK errors are surfaced without printing credentials.
        print(f"Cartesia generation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    size_bytes = output_path.stat().st_size
    print(f"Audio saved to {output_path} ({size_bytes:,} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
