# Cartesia API test runner

A small, isolated Cartesia text-to-speech test harness. It runs on GitHub Actions and stores the generated WAV as a downloadable workflow artifact.

## One-time setup

1. Open **Settings → Secrets and variables → Actions → New repository secret**.
2. Create a secret named `CARTESIA_API_KEY`.
3. Paste your Cartesia API key into the secret value and save it. Never commit the key to this repository.

## Generate speech

1. Open the **Actions** tab.
2. Select **Cartesia TTS – Generate WAV**.
3. Choose **Run workflow**.
4. Enter the text to speak. The default voice is Cartesia's stock English Skylar voice; you can replace its voice ID with another voice ID from your Cartesia account.
5. Run the workflow.
6. Open the completed run and download the `cartesia-tts-audio` artifact.

The runner uses the Cartesia Python SDK, the `sonic-latest` model by default, and WAV/PCM audio at 44.1 kHz.

## Local use

```bash
python -m pip install -r cartesia_api/requirements.txt
export CARTESIA_API_KEY="your-key"
export CARTESIA_TRANSCRIPT="Hello from Cartesia."
export CARTESIA_VOICE_ID="f786b574-daa5-4673-aa0c-cbe3e8534c02"
python cartesia_api/generate.py
```

The local command writes `output/cartesia.wav`. The API key is read from the environment and is never printed.
