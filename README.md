# ⚡ ClutchCuts AI — Native Stream-to-Shorts Automation Studio

Automate clipping YouTube and Twitch livestreams into viral 9:16 vertical Shorts, Reels, and TikToks directly on your machine with **zero subscriptions, zero watermarks, and zero external cloud APIs**.

---

## 🌟 Key Features

- **🎯 Zero Audio-Video Drift (DASH Sync)**: Presentation timestamps locked using `setpts=PTS-STARTPTS` & `aresample=async=1` to guarantee `0.000000s` alignment.
- **📱 9:16 Split-Screen Layout (1080x1920)**:
  - Ambient blurred background with Gaussian blur (`boxblur=25:2`, `eq=brightness=-0.15`)
  - Top facecam cropped and scaled to `620x480` centered at `y=0`
  - 3:4 crosshair-aligned gameplay cropped and scaled to `1080x1440` (zero black letterboxes)
- **🔥 Word-by-Word Hormozi Karaoke Subtitles**: Generated using `faster-whisper` with active word pop (`\fscx115\fscy115`, `#FFE500` / `&H00E5FF&`, `\bord6\shad3`) positioned at safe zone `\pos(540,620)`.
- **🌐 Responsive Web App Dashboard**:
  - Simple URL input with customizable clip counts (1, 2, 3, 5 shorts).
  - In-browser vertical 9:16 video player preview.
  - Direct 1-click **"Download Video (MP4)"** straight to your device (PC, iPhone, Android).
  - Multi-device Wi-Fi access via local IP (e.g., `http://192.168.x.x:5000`).
- **🧹 Automated Cleanup**: Temporary raw slices, ASS subtitles, and frames are purged after every render.

---

## 🛠️ Prerequisites

1. **Python 3.10+**:
   ```bash
   python --version
   ```
2. **FFmpeg & FFprobe**:
   Both commands must be available on your `PATH`. If they are installed elsewhere, set `FFMPEG_PATH` and `FFPROBE_PATH` to their full executable paths.
   - Windows:
     ```powershell
     winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
     ```
   - macOS:
     ```bash
     brew install ffmpeg
     ```
3. **Deno (JavaScript Runtime for YouTube Challenges)**:
   Deno is optional, but can help yt-dlp access some YouTube videos. If it is installed outside your `PATH`, set `DENO_PATH` to its executable.
   - Windows:
     ```powershell
     winget install DenoLand.Deno --accept-package-agreements --accept-source-agreements
     ```
   - macOS:
     ```bash
     brew install deno
     ```

---

## 🚀 Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ClutchCuts-AI.git
   cd ClutchCuts-AI
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   If YouTube reports that no player response is available after retries, update yt-dlp and restart the studio:
   ```bash
   python -m pip install --upgrade yt-dlp
   ```
   If YouTube asks you to sign in to confirm you're not a bot, you can optionally let yt-dlp use
   cookies from a browser where you are signed in. Set `YTDLP_COOKIES_FROM_BROWSER` to the browser
   name before starting the studio (for example, `chrome`, `firefox`, or `edge`). In PowerShell:
   ```powershell
   $env:YTDLP_COOKIES_FROM_BROWSER = "chrome"
   python web_app/server.py
   ```
   The setting is opt-in; yt-dlp reads cookies locally from that browser for metadata and downloads.
   Never share exported cookie files or logs containing authentication data. This does not grant
   access to videos your account cannot view.

3. **Launch the Web App**:
   - On Windows: Double-click `START_STUDIO.bat` from the project folder. It uses the project’s current location and checks that Python dependencies are installed.
   - Or via terminal:
     ```bash
     python web_app/server.py
     ```

4. **Open in your browser**:
   - On your PC: `http://localhost:5000`
   - On your Phone (same Wi-Fi): `http://<YOUR_LOCAL_IP>:5000`

   Netlify serves only the static preview; video processing requires the Python backend. Use the local app above or deploy the Docker backend to a server with FFmpeg and enough memory for Whisper.

---

## 📄 License
MIT License
