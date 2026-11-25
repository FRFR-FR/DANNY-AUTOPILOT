# Cartesia Glasswing debate voiceover

This job uses Cartesia Sonic 3.6 to synthesize the complete 44-line debate in the 5:18.4 timeline supplied in `CMNS.pdf`.

## Secret

Add the repository Actions secret:

- Name: `CARTESIA_API_KEY`
- Value: your Cartesia API key

## Selected English voices

- **Liam:** Carl — Steady Storyteller (male; measured documentary narration)
- **George:** Nolan — Expressive Agent (male; warm, natural conversational delivery)
- **Nadia:** Lauren — Lively Narrator (female; expressive narration)

These are public Cartesia library voices. The selection is based on Cartesia's published voice descriptions; the job does not claim a subjective listening comparison.

## Run

Open Actions → **Cartesia — Glasswing full debate voiceover** → Run workflow.

The job generates:
- `dialogue.wav` — complete 318.4-second stereo/mono timeline (voice-only)
- `Liam.wav`, `George.wav`, `Nadia.wav` — isolated full-length speaker stems
- `dialogue.srt` — timecoded captions
- `audio-report.json` — voice map and timing validation

To also produce `glasswing-full-cartesia.mp4`, supply a direct HTTPS download URL for the matching silent picture `glasswing_full_silent.mp4`. It must be 1280x720, 30fps and approximately 318.4 seconds. The workflow muxes the narration without re-encoding the video stream.

The API key is only read from the GitHub Actions secret and is never written to the repository or artifact. Generated artifacts are retained for 90 days.
