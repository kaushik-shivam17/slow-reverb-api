# slow-reverb-api

Flask API that takes an audio URL, applies slow + reverb effects, and returns the processed MP3.

Built to work with Activepieces automations and deploy on Railway.

## Endpoints

**GET /**
Health check — returns `{"status": "ok"}`

**POST /process**

```json
{
  "title": "song name",
  "url": "https://example.com/audio.mp3"
}
```

Returns:
```json
{
  "status": "success",
  "title": "song name",
  "file": "output/song_name_abc12345_slow_reverb.mp3"
}
```

Errors return `{"status": "error", "message": "..."}` with the appropriate HTTP status code.

## Setup

```bash
# needs ffmpeg installed
brew install ffmpeg        # macOS
apt install ffmpeg         # Debian/Ubuntu

pip install -r requirements.txt
python app.py
```

## Deploy (Railway)

1. Push repo to GitHub
2. Create a new Railway project → Deploy from GitHub repo
3. Go to your service → **Settings → Source → Root Directory** → set it to `slow-reverb-api`
4. Redeploy

**Step 3 is required.** The repo root contains Node.js files (`package.json`) so Railway will try to build as Node unless you point it at the right folder. Once the root directory is set, `railway.toml` and `nixpacks.toml` take over and install Python + FFmpeg correctly.

## Notes

- Speed is set to 0.85x using pydub's frame rate trick
- Reverb is 3 echo layers at 60ms intervals, -6/-12/-18 dB
- Output is 192kbps MP3
- Input files are deleted after processing
