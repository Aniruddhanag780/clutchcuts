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
   - Windows:
     ```powershell
     winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
     ```
   - macOS:
     ```bash
     brew install ffmpeg
     ```
3. **Deno (JavaScript Runtime for YouTube Challenges)**:
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

3. **Launch the Web App**:
   - On Windows: Double-click `START_STUDIO.bat`
   - Or via terminal:
     ```bash
     python web_app/server.py
     ```

4. **Open in your browser**:
   - On your PC: `http://localhost:5000`
   - On your Phone (same Wi-Fi): `http://<YOUR_LOCAL_IP>:5000`

---

## 📄 License
MIT License
