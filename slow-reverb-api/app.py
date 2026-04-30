import os
import gc
import time
import uuid
import logging
import requests
from flask import Flask, request, jsonify
from pydub import AudioSegment

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

INPUT_DIR = "input"
OUTPUT_DIR = "output"
MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024  # 60 MB
OUTPUT_MAX_AGE_SECONDS = 3600          # delete output files older than 1 hour

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def slugify_title(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in title)
    return safe.strip().replace(" ", "_")[:60]


def apply_slow(audio: AudioSegment, speed: float = 0.85) -> AudioSegment:
    new_frame_rate = int(audio.frame_rate * speed)
    slowed = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    return slowed.set_frame_rate(audio.frame_rate)


def apply_reverb(audio: AudioSegment, delay_ms: int = 60) -> AudioSegment:
    tail = AudioSegment.silent(duration=delay_ms * 3)
    result = audio + tail

    for i, db in enumerate([-6, -12, -18], start=1):
        offset = delay_ms * i
        pad_len = max(0, len(result) - len(audio) - offset)
        echo = AudioSegment.silent(duration=offset) + audio + AudioSegment.silent(duration=pad_len)
        if len(echo) < len(result):
            echo = echo + AudioSegment.silent(duration=len(result) - len(echo))
        result = result.overlay(echo + db)
        del echo
        gc.collect()

    return result


def cleanup_old_outputs():
    now = time.time()
    try:
        for fname in os.listdir(OUTPUT_DIR):
            fpath = os.path.join(OUTPUT_DIR, fname)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > OUTPUT_MAX_AGE_SECONDS:
                os.remove(fpath)
                logger.info(f"removed old output: {fname}")
    except Exception as e:
        logger.warning(f"output cleanup error: {e}")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "slow-reverb-api"}), 200


@app.route("/process", methods=["POST"])
def process():
    cleanup_old_outputs()

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "error", "message": "Invalid JSON body"}), 400

    title = data.get("title", "").strip()
    url = data.get("url", "").strip()

    if not title:
        return jsonify({"status": "error", "message": "Missing required field: title"}), 400
    if not url:
        return jsonify({"status": "error", "message": "Missing required field: url"}), 400

    unique_id = uuid.uuid4().hex[:8]
    slug = slugify_title(title)
    input_path = os.path.join(INPUT_DIR, f"{slug}_{unique_id}.mp3")
    output_filename = f"{slug}_{unique_id}_slow_reverb.mp3"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    logger.info(f"job started: '{title}'")

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        downloaded = 0
        with open(input_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > MAX_DOWNLOAD_BYTES:
                    f.close()
                    _cleanup(input_path)
                    return jsonify({"status": "error", "message": "Audio file too large (60MB limit)"}), 413
                f.write(chunk)
        logger.info(f"downloaded {downloaded // 1024}KB to {input_path}")
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "Timeout while downloading audio URL"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"download failed: {e}")
        return jsonify({"status": "error", "message": f"Failed to download audio: {str(e)}"}), 502

    try:
        audio = AudioSegment.from_file(input_path)
        logger.info(f"loaded {len(audio)}ms, {audio.channels}ch, {audio.frame_rate}Hz")
    except Exception as e:
        logger.error(f"could not load audio: {e}")
        _cleanup(input_path)
        return jsonify({"status": "error", "message": f"Invalid or unsupported audio file: {str(e)}"}), 422

    _cleanup(input_path)

    try:
        slowed = apply_slow(audio, speed=0.85)
        del audio
        gc.collect()

        processed = apply_reverb(slowed)
        del slowed
        gc.collect()

        processed.export(output_path, format="mp3", bitrate="192k")
        del processed
        gc.collect()

        logger.info(f"done: {output_path}")
    except Exception as e:
        logger.error(f"processing failed: {e}")
        return jsonify({"status": "error", "message": f"Audio processing failed: {str(e)}"}), 500

    return jsonify({
        "status": "success",
        "title": title,
        "file": output_path
    }), 200


def _cleanup(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"cleanup failed for {path}: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
