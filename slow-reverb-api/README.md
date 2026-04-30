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

Push to GitHub, connect to Railway. The `nixpacks.toml` handles ffmpeg installation and `Procfile` starts gunicorn.

## Notes

- Speed is set to 0.85x using pydub's frame rate trick
- Reverb is 3 echo layers at 60ms intervals, -6/-12/-18 dB
- Output is 192kbps MP3
- Input files are deleted after processing
