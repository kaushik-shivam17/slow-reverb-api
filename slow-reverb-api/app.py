import os
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

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def slugify_title(title: str) -> str:
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "" for c in title)
    return safe.strip().replace(" ", "_")[:60]


def apply_slow(audio: AudioSegment, speed: float = 0.85) -> AudioSegment:
    new_frame_rate = int(audio.frame_rate * speed)
    slowed = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    return slowed.set_frame_rate(audio.frame_rate)


def apply_reverb(audio: AudioSegment, decay: float = 0.4, delay_ms: int = 60) -> AudioSegment:
    silence = AudioSegment.silent(duration=delay_ms)
    padded = audio + silence

    echo1 = silence + audio - 6
    echo2 = silence + silence + audio - 12
    echo3 = silence + silence + silence + audio - 18

    max_len = max(len(padded), len(echo1), len(echo2), len(echo3))

    def pad(seg):
        return seg + AudioSegment.silent(duration=max_len - len(seg))

    result = pad(padded).overlay(pad(echo1)).overlay(pad(echo2)).overlay(pad(echo3))
    return result


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "slow-reverb-api"}), 200


@app.route("/process", methods=["POST"])
def process():
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

    logger.info(f"Processing request — title: '{title}', url: {url}")

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        with open(input_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Downloaded audio to {input_path}")
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "message": "Timeout while downloading audio URL"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
        return jsonify({"status": "error", "message": f"Failed to download audio: {str(e)}"}), 502

    try:
        audio = AudioSegment.from_file(input_path)
        logger.info(f"Loaded audio — duration: {len(audio)}ms, channels: {audio.channels}, rate: {audio.frame_rate}Hz")
    except Exception as e:
        logger.error(f"Failed to load audio: {e}")
        _cleanup(input_path)
        return jsonify({"status": "error", "message": f"Invalid or unsupported audio file: {str(e)}"}), 422

    try:
        logger.info("Applying slow effect (0.85x)...")
        slowed = apply_slow(audio, speed=0.85)

        logger.info("Applying reverb effect...")
        processed = apply_reverb(slowed)

        processed.export(output_path, format="mp3", bitrate="192k")
        logger.info(f"Exported processed audio to {output_path}")
    except Exception as e:
        logger.error(f"Audio processing failed: {e}")
        _cleanup(input_path)
        return jsonify({"status": "error", "message": f"Audio processing failed: {str(e)}"}), 500

    _cleanup(input_path)

    return jsonify({
        "status": "success",
        "title": title,
        "file": output_path
    }), 200


def _cleanup(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Cleaned up temp file: {path}")
    except Exception as e:
        logger.warning(f"Could not clean up {path}: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
