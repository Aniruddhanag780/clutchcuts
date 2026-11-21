import os
import sys
import json
import socket
import threading
import subprocess
from flask import Flask, render_template, request, jsonify, send_from_directory

# Connect pipeline engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline_engine

app = Flask(__name__, template_folder="templates")

STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_shorts")
os.makedirs(STORAGE_DIR, exist_ok=True)

STATE = {
    "is_running": False,
    "progress": 0,
    "status_message": "Ready to generate shorts",
    "logs": [],
    "current_results": []
}

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
    lan_ip = get_lan_ip()
    return render_template("index.html", lan_ip=lan_ip)

@app.route("/api/status")
def status():
    return jsonify(STATE)

@app.route("/api/generate", methods=["POST"])
def generate():
    if STATE["is_running"]:
        return jsonify({"error": "A job is already in progress"}), 400

    data = request.json or {}
    url = data.get("url", "").strip()
    clip_count = int(data.get("clip_count", 2))

    if not url:
        return jsonify({"error": "Please provide a valid stream or video URL"}), 400

    STATE["is_running"] = True
    STATE["progress"] = 5
    STATE["status_message"] = "Initializing stream processing..."
    STATE["logs"] = []
    STATE["current_results"] = []

    def task():
        def progress_cb(msg):
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
            STATE["current_results"] = results
            STATE["status_message"] = "Completed! Ready for instant download."
            STATE["progress"] = 100
        except Exception as e:
            STATE["status_message"] = f"Error: {str(e)}"
            STATE["logs"].append(f"EXCEPTION: {str(e)}")
        finally:
            STATE["is_running"] = False

    t = threading.Thread(target=task, daemon=True)
    t.start()

    return jsonify({"success": True, "message": "Pipeline started"})

@app.route("/api/videos")
def list_videos():
    if not os.path.exists(STORAGE_DIR):
        return jsonify([])
    files = [f for f in os.listdir(STORAGE_DIR) if f.lower().endswith(".mp4")]
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
