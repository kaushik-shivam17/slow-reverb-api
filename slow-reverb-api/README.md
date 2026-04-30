# Slow + Reverb Audio Processing API

A production-ready REST API that downloads audio from a URL, applies slow (0.85x) and reverb effects, and returns the path to the processed MP3.

## Stack

- Python 3.10+
- Flask 3
- pydub + FFmpeg (audio processing)
- gunicorn (production server)
- Railway-ready (nixpacks.toml)

## Endpoints

### `GET /`
Health check.

**Response:**
```json
{ "status": "ok", "service": "slow-reverb-api" }
```

---

### `POST /process`
Download and process an audio file.

**Request body:**
```json
{
  "title": "song name",
  "url": "https://example.com/audio.mp3"
}
```

**Success response (200):**
```json
{
  "status": "success",
  "title": "song name",
  "file": "output/song_name_abc12345_slow_reverb.mp3"
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| 400 | Missing `title` or `url`, or invalid JSON |
| 422 | Audio file could not be decoded |
| 502 | Failed to download from the provided URL |
| 504 | Download timed out |
| 500 | Internal processing error |

---

## Local Development

```bash
# Install system dependency
brew install ffmpeg        # macOS
apt install ffmpeg         # Ubuntu/Debian

# Install Python deps
pip install -r requirements.txt

# Run dev server
python app.py

# Or production server
gunicorn app:app
```

## Deploy on Railway

1. Push this folder to a GitHub repository
2. Create a new Railway project → Deploy from GitHub repo
3. Railway will auto-detect `nixpacks.toml` and install FFmpeg
4. The `Procfile` starts gunicorn automatically

## Project Structure

```
slow-reverb-api/
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── Procfile            # Railway/gunicorn start command
├── nixpacks.toml       # FFmpeg system dependency for Railway
├── .gitignore
├── input/              # Temporary download folder (auto-created)
└── output/             # Processed MP3 output folder (auto-created)
```

## Audio Processing Details

- **Slow**: Resamples audio to 85% of original speed using pydub's frame-rate trick, then restores original sample rate
- **Reverb**: Overlays 3 delayed echo layers (-6dB, -12dB, -18dB) at 60ms intervals for a natural reverb tail
- **Output**: 192kbps MP3
- **Cleanup**: Temporary input files are deleted after processing
