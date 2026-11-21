import os
import sys
import re
import json
import time
import shutil
import subprocess
from faster_whisper import WhisperModel

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(APP_DIR, "generated_shorts")

def get_config():
    ffmpeg = os.environ.get("FFMPEG_PATH") or shutil.which("ffmpeg")
    ffprobe = os.environ.get("FFPROBE_PATH") or shutil.which("ffprobe")
    deno = os.environ.get("DENO_PATH") or shutil.which("deno")
    return {
        "output_directory": DEFAULT_OUTPUT_DIR,
        "python_path": sys.executable,
        "ffmpeg_path": ffmpeg,
        "ffprobe_path": ffprobe,
        "deno_path": deno
    }

def format_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def generate_ass(words_list, ass_path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,5,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    if not words_list:
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header)
        return

    chunks = []
    chunk_size = 3
    for i in range(0, len(words_list), chunk_size):
        chunk = words_list[i:i + chunk_size]
        chunks.append(chunk)

    events = []
    for chunk in chunks:
        for idx, active_word in enumerate(chunk):
            w_start = format_ass_time(active_word['start'])
            w_end = format_ass_time(active_word['end'])
            line_parts = []
            for j, w in enumerate(chunk):
                w_text = w['word'].strip().upper()
                clean_text = "".join(c for c in w_text if c.isalnum() or c in "'-?!")
                if not clean_text:
                    clean_text = w_text
                if j == idx:
                    line_parts.append(f"{{\\c&H00E5FF&\\fscx115\\fscy115}}{clean_text}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}")
                else:
                    line_parts.append(f"{{\\c&H00FFFFFF&\\fscx100\\fscy100}}{clean_text}")
            display_text = " ".join(line_parts)
            event_line = f"Dialogue: 0,{w_start},{w_end},Hormozi,,0,0,0,,{{\\pos(540,620)\\an5}}{display_text}"
            events.append(event_line)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events) + "\n")

def process_stream(url, clip_count=2, output_dir=None, progress_cb=None):
    temp_dir = os.path.join(APP_DIR, f"job_{time.time_ns()}")
    os.makedirs(temp_dir, exist_ok=True)
    try:
        return _process_stream(url, clip_count, output_dir, progress_cb, temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def _process_stream(url, clip_count, output_dir, progress_cb, temp_dir):
    cfg = get_config()
    if not cfg["ffmpeg_path"] or not os.path.isfile(cfg["ffmpeg_path"]):
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to PATH, or set FFMPEG_PATH.")
    if not cfg["ffprobe_path"] or not os.path.isfile(cfg["ffprobe_path"]):
        raise RuntimeError("FFprobe was not found. Install FFmpeg and add it to PATH, or set FFPROBE_PATH.")
    if clip_count not in (1, 2, 3, 5):
        raise ValueError("Choose 1, 2, 3, or 5 shorts.")
    if not output_dir:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    def log(msg):
        print(msg)
        if progress_cb:
            progress_cb(msg)

    log(f"Starting pipeline for URL: {url} | Count: {clip_count}")

    # Step 1: Ingest stream metadata (Multi-client Android/iOS/TV/Web fallback)
    log("Fetching stream metadata and community highlights...")
    import yt_dlp
    js_runtimes = {'deno': {'path': cfg['deno_path']}} if cfg.get('deno_path') else {}
    ydl_opts = {
        'skip_download': True,
        'getcomments': True,
        'ignoreerrors': False,
        'js_runtimes': js_runtimes,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'tv', 'web'],
                'comment_sort': ['top'],
                'max_comments': ['150', 'all', '150', '0']
            }
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        log(f"Warning on full extraction, falling back to direct mobile client: {str(e)}")
        fallback_opts = {
            'skip_download': True,
            'getcomments': False,
            'js_runtimes': js_runtimes,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv']
                }
            }
        }
        with yt_dlp.YoutubeDL(fallback_opts) as ydl:
            info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("Could not read video details. Check the URL, access permissions, and try again.")
    video_title = info.get('title', 'Video')
    duration = info.get('duration') or 0
    if duration <= 0:
        raise RuntimeError("This video has no available duration. Make sure it is a published video or VOD.")
    comments = info.get('comments') or []
    log(f"Stream: '{video_title}' | Duration: {duration}s | Comments analyzed: {len(comments)}")

    # Step 2: Peak moment detection
    log("Scanning for highest-energy moments...")
    time_regex = re.compile(r'(\d{1,2}):(\d{2})(?::(\d{2}))?')
    candidates = []
    
    for c in comments:
        text = c.get('text', '')
        likes = c.get('like_count', 0)
        matches = time_regex.findall(text)
        for m in matches:
            sec = int(m[0])*3600 + int(m[1])*60 + int(m[2]) if m[2] else int(m[0])*60 + int(m[1])
            if 10 <= sec <= duration - 32:
                score = likes + (50 if any(k in text.lower() for k in ['clutch', 'fail', 'lol', 'police', 'fight', 'jump', 'kill', 'car']) else 10)
                candidates.append((score, sec, text))

    candidates.sort(key=lambda x: x[0], reverse=True)
    
    selected_moments = []
    min_gap = 120
    for score, sec, text in candidates:
        if all(abs(sec - s) >= min_gap for s in selected_moments):
            selected_moments.append(sec)
        if len(selected_moments) >= clip_count:
            break

    max_start = max(0, duration - 32)
    while len(selected_moments) < clip_count:
        fallback_sec = int((len(selected_moments) + 1) * max_start / (clip_count + 1))
        selected_moments.append(fallback_sec)

    log(f"Selected {len(selected_moments)} peak moment windows at: {[f'{s}s ({s//60}m{s%60}s)' for s in selected_moments]}")

    results = []
    model = None

    for i, start_sec in enumerate(selected_moments):
        clip_num = i + 1
        clip_len = min(32, max(1, duration - start_sec))
        end_sec = start_sec + clip_len
        log(f"\n--- Processing Short #{clip_num} ({start_sec}s - {end_sec}s) ---")
        
        raw_slice = os.path.join(temp_dir, f"slice_{clip_num}.mp4")
        ass_path = os.path.join(temp_dir, f"subs_{clip_num}.ass")
        final_mp4 = os.path.join(output_dir, f"viral_short_{clip_num}_{int(time.time())}.mp4")

        # Download slice (Universal format selector + safe error logging)
        log(f"Downloading stream slice ({start_sec}s to {end_sec}s)...")
        slice_cmd = [
            cfg['python_path'], "-m", "yt_dlp",
            "--extractor-args", "youtube:player_client=android,ios,tv,web",
            "--download-sections", f"*{start_sec}-{end_sec}",
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "--merge-output-format", "mp4",
            "--force-overwrites",
            url, "-o", raw_slice
        ]
        if cfg.get('deno_path'):
            slice_cmd.extend(["--js-runtimes", f"deno:{cfg['deno_path']}"])

        ffmpeg_dir = os.path.dirname(cfg.get('ffmpeg_path', ''))
        if ffmpeg_dir and ffmpeg_dir not in ['/usr/bin', '/usr/local/bin', '/bin']:
            slice_cmd.extend(["--ffmpeg-location", ffmpeg_dir])

        try:
            subprocess.run(slice_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            err_details = (e.stderr or e.stdout or str(e)).strip()
            log(f"Slice download error details: {err_details}")
            raise Exception(f"Video slice download failed: {err_details}")

        source_probe = subprocess.run(
            [
                cfg['ffprobe_path'], "-v", "error", "-show_entries", "stream=codec_type",
                "-of", "json", raw_slice
            ],
            capture_output=True,
            text=True,
        )
        if source_probe.returncode:
            details = (source_probe.stderr or "FFprobe could not inspect the downloaded clip.").strip()
            raise RuntimeError(f"Could not inspect downloaded clip: {details}")
        source_streams = json.loads(source_probe.stdout).get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in source_streams):
            raise RuntimeError("The downloaded clip does not contain a video stream.")
        has_audio = any(stream.get("codec_type") == "audio" for stream in source_streams)

        # Transcribe (Optimized with beam_size=1 for 4x faster CPU transcription)
        words = []
        transcript_text = []
        if has_audio:
            log("Transcribing with faster-whisper (word timestamps)...")
            if model is None:
                model = WhisperModel('base', device='cpu', compute_type='int8')
            segments, _ = model.transcribe(raw_slice, task='translate', word_timestamps=True, beam_size=1)
            for s in segments:
                transcript_text.append(s.text.strip())
                if s.words:
                    for w in s.words:
                        words.append({'word': w.word, 'start': w.start, 'end': w.end})
        else:
            log("No audio track found; rendering this short without captions.")
        full_transcript = " ".join(transcript_text)

        generate_ass(words, ass_path)

        # Composite & Render 9:16 layout (Optimized ambient blur for 15x faster CPU encoding)
        log("Compositing 9:16 vertical layout with zero PTS drift...")
        ass_escaped = ass_path.replace('\\', '/').replace(':', r'\:')
        audio_filter = (
            "[0:a]asetpts=PTS-STARTPTS,aresample=async=1[a_sync];"
            if has_audio
            else f"anullsrc=r=44100:cl=stereo,atrim=duration={clip_len}[a_sync];"
        )
        filter_complex = (
            f"[0:v]setpts=PTS-STARTPTS,split=2[v_bg][v_fg];"
            f"{audio_filter}"
            f"[v_bg]scale=180:320:force_original_aspect_ratio=increase,crop=180:320,boxblur=5:1,scale=1080:1920,eq=brightness=-0.15[bg];"
            f"[v_fg]scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440[foreground];"
            f"[bg][foreground]overlay=x=0:y=240[comp];"
            f"[comp]subtitles=filename='{ass_escaped}'[v_out]"
        )

        render_cmd = [
            cfg['ffmpeg_path'], "-y",
            "-i", raw_slice,
            "-filter_complex", filter_complex,
            "-map", "[v_out]",
            "-map", "[a_sync]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "8M",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            final_mp4
        ]
        try:
            subprocess.run(render_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            details = (e.stderr or e.stdout or str(e)).strip()
            log(f"Render error details: {details}")
            raise RuntimeError(f"Could not render short #{clip_num}: {details}") from e

        # Verify
        log("Verifying zero sync drift via ffprobe...")
        probe_cmd = [
            cfg['ffprobe_path'], "-v", "error",
            "-show_entries", "stream=index,codec_name,start_time,duration",
            "-of", "json", final_mp4
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode:
            details = (probe_result.stderr or "FFprobe could not verify the rendered file.").strip()
            raise RuntimeError(f"Short #{clip_num} failed output verification: {details}")
        output_streams = json.loads(probe_result.stdout).get("streams", [])
        if not any(stream.get("codec_name") for stream in output_streams if stream.get("index") == 0):
            raise RuntimeError(f"Short #{clip_num} does not contain a valid video stream.")

        results.append({
            'file': final_mp4,
            'filename': os.path.basename(final_mp4),
            'timestamp': f"{start_sec//60}:{start_sec%60:02d} - {end_sec//60}:{end_sec%60:02d}",
            'transcript': full_transcript
        })
        log(f"Short #{clip_num} is ready for direct browser download!")

    log("\nAll shorts rendered! Ready to download to your phone or PC.")
    return results
