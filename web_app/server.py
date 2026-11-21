import os
import sys
import socket
import threading
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_from_directory

# Connect pipeline engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline_engine

app = Flask(__name__, template_folder="templates")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_shorts")
os.makedirs(STORAGE_DIR, exist_ok=True)

STATE = {
    "is_running": False,
    "progress": 0,
    "status_message": "Ready to generate shorts",
    "logs": [],
    "current_results": [],
    "error": None
}
JOB_LOCK = threading.Lock()

def get_lan_ip():
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        lan_ips = [ip for ip in ips if not ip.startswith("127.")]
        return lan_ips[0] if lan_ips else "localhost"
    except Exception:
        return "localhost"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    with JOB_LOCK:
        snapshot = dict(STATE)
        snapshot["logs"] = list(STATE["logs"])
        snapshot["current_results"] = list(STATE["current_results"])
    return jsonify(snapshot)

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send a JSON body containing a video URL"}), 400

    url = data.get("url")
    if not isinstance(url, str):
        return jsonify({"error": "Please provide a valid stream or video URL"}), 400
    url = url.strip()
    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname:
        return jsonify({"error": "Enter a valid YouTube or Twitch URL starting with http:// or https://"}), 400

    count_value = data.get("clip_count", 2)
    if isinstance(count_value, bool) or not isinstance(count_value, (int, str)):
        return jsonify({"error": "Choose 1, 2, 3, or 5 shorts"}), 400
    try:
        clip_count = int(count_value)
    except (TypeError, ValueError):
        return jsonify({"error": "Choose 1, 2, 3, or 5 shorts"}), 400
    if clip_count not in (1, 2, 3, 5):
        return jsonify({"error": "Choose 1, 2, 3, or 5 shorts"}), 400

    with JOB_LOCK:
        if STATE["is_running"]:
            return jsonify({"error": "A job is already in progress"}), 409

        STATE["is_running"] = True
        STATE["progress"] = 5
        STATE["status_message"] = "Initializing stream processing..."
        STATE["logs"] = []
        STATE["current_results"] = []
        STATE["error"] = None

    def task():
        def progress_cb(msg):
            with JOB_LOCK:
                STATE["logs"].append(msg)
                STATE["status_message"] = msg
                if "Scanning" in msg:
                    STATE["progress"] = 25
                elif "Processing Short" in msg:
                    STATE["progress"] = 50
                elif "Compositing" in msg:
                    STATE["progress"] = 75
                elif "Verifying" in msg:
                    STATE["progress"] = 90
                elif "All shorts rendered" in msg:
                    STATE["progress"] = 100

        try:
            results = pipeline_engine.process_stream(
                url=url,
                clip_count=clip_count,
                output_dir=STORAGE_DIR,
                progress_cb=progress_cb
            )
            with JOB_LOCK:
                STATE["current_results"] = results
                STATE["status_message"] = "Completed! Your shorts are ready to preview and download."
                STATE["progress"] = 100
        except Exception as e:
            message = str(e).strip() or "An unexpected processing error occurred."
            with JOB_LOCK:
                STATE["status_message"] = message
                STATE["logs"].append(f"ERROR: {message}")
                STATE["error"] = message
        finally:
            with JOB_LOCK:
                STATE["is_running"] = False

    t = threading.Thread(target=task, daemon=True)
    t.start()

    return jsonify({"success": True, "message": "Pipeline started"})

@app.route("/api/videos")
def list_videos():
    if not os.path.exists(STORAGE_DIR):
        return jsonify([])
    files = [
        f for f in os.listdir(STORAGE_DIR)
        if f.lower().endswith(".mp4")
        and os.path.isfile(os.path.join(STORAGE_DIR, f))
    ]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(STORAGE_DIR, x)), reverse=True)
    return jsonify([{"name": f, "size_mb": round(os.path.getsize(os.path.join(STORAGE_DIR, f)) / (1024*1024), 2)} for f in files])

# In-browser streaming
@app.route("/videos/<path:filename>")
def stream_video(filename):
    return send_from_directory(STORAGE_DIR, filename)

# Direct file download trigger for Phone / PC
@app.route("/download/<path:filename>")
def download_video(filename):
    return send_from_directory(STORAGE_DIR, filename, as_attachment=True)

if __name__ == "__main__":
    lan_ip = get_lan_ip()
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting ClutchCuts Web Studio on port {port}...")
    print(f"PC Access:    http://localhost:{port}")
    print(f"Phone Access: http://{lan_ip}:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
