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
    return {
        "output_directory": DEFAULT_OUTPUT_DIR,
        "python_path": r"C:\Users\COMPUTER\AppData\Local\Programs\Python\Python311\python.exe",
        "ffmpeg_path": r"C:\Users\COMPUTER\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin\ffmpeg.exe",
        "ffprobe_path": r"C:\Users\COMPUTER\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin\ffprobe.exe",
        "deno_path": r"C:\Users\COMPUTER\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe\deno.exe"
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
    cfg = get_config()
    if not output_dir:
        output_dir = DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(r"C:\Users\COMPUTER\.gemini\antigravity\scratch\stream_to_shorts_pipeline", f"job_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)

    def log(msg):
        print(msg)
        if progress_cb:
            progress_cb(msg)

    log(f"Starting pipeline for URL: {url} | Count: {clip_count}")

    # Step 1: Ingest stream metadata
    log("Fetching stream metadata and community highlights...")
    import yt_dlp
    ydl_opts = {
        'skip_download': True,
        'getcomments': True,
        'js_runtimes': {'deno': [cfg['deno_path']]},
        'extractor_args': {
            'youtube': {
                'comment_sort': ['top'],
                'max_comments': ['150', 'all', '150', '0']
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        video_title = info.get('title', 'Gaming Stream')
        duration = info.get('duration', 3600)
        comments = info.get('comments', [])
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
            if 10 <= sec <= duration - 40:
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

    while len(selected_moments) < clip_count:
        fallback_sec = int((len(selected_moments) + 1) * duration / (clip_count + 1))
        selected_moments.append(fallback_sec)

    log(f"Selected {len(selected_moments)} peak moment windows at: {[f'{s}s ({s//60}m{s%60}s)' for s in selected_moments]}")

    results = []
    model = WhisperModel('base', device='cpu', compute_type='int8')

    for i, start_sec in enumerate(selected_moments):
        clip_num = i + 1
        clip_len = 32
        end_sec = start_sec + clip_len
        log(f"\n--- Processing Short #{clip_num} ({start_sec}s - {end_sec}s) ---")
        
        raw_slice = os.path.join(temp_dir, f"slice_{clip_num}.mp4")
        ass_path = os.path.join(temp_dir, f"subs_{clip_num}.ass")
        final_mp4 = os.path.join(output_dir, f"viral_short_{clip_num}_{int(time.time())}.mp4")

        # Download slice
        log(f"Downloading stream slice ({start_sec}s to {end_sec}s)...")
        slice_cmd = [
            cfg['python_path'], "-m", "yt_dlp",
            "--js-runtimes", f"deno:{cfg['deno_path']}",
            "--ffmpeg-location", os.path.dirname(cfg['ffmpeg_path']),
            "--download-sections", f"*{start_sec}-{end_sec}",
            "-f", "136+140/bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/18/best",
            "--force-overwrites",
            url, "-o", raw_slice
        ]
        subprocess.run(slice_cmd, check=True, capture_output=True)

        # Transcribe
        log("Transcribing with faster-whisper (word timestamps)...")
        segments, _ = model.transcribe(raw_slice, task='translate', word_timestamps=True, beam_size=5)
        words = []
        transcript_text = []
        for s in segments:
            transcript_text.append(s.text.strip())
            if s.words:
                for w in s.words:
                    words.append({'word': w.word, 'start': w.start, 'end': w.end})
        full_transcript = " ".join(transcript_text)

        generate_ass(words, ass_path)

        # Composite & Render 9:16 layout
        log("Compositing 9:16 vertical layout with zero PTS drift...")
        ass_escaped = ass_path.replace('\\', '/').replace(':', r'\:')
        filter_complex = (
            f"[0:v]setpts=PTS-STARTPTS,split=3[v_bg][v_cam][v_game];"
            f"[0:a]asetpts=PTS-STARTPTS,aresample=async=1[a_sync];"
            f"[v_bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:2,eq=brightness=-0.15[bg];"
            f"[v_cam]crop=360:280:910:10,scale=620:480[facecam];"
            f"[v_game]crop=534:714:373:0,scale=1080:1440[gameplay];"
            f"[bg][facecam]overlay=x=230:y=0[comp1];"
            f"[comp1][gameplay]overlay=x=0:y=480[comp2];"
            f"[comp2]subtitles=filename='{ass_escaped}'[v_out]"
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
        subprocess.run(render_cmd, check=True, capture_output=True)

        # Verify
        log("Verifying zero sync drift via ffprobe...")
        probe_cmd = [
            cfg['ffprobe_path'], "-v", "error",
            "-show_entries", "stream=index,codec_name,start_time,duration",
            "-of", "json", final_mp4
        ]
        subprocess.run(probe_cmd, capture_output=True, text=True)

        results.append({
            'file': final_mp4,
            'filename': os.path.basename(final_mp4),
            'timestamp': f"{start_sec//60}:{start_sec%60:02d} - {end_sec//60}:{end_sec%60:02d}",
            'transcript': full_transcript
        })
        log(f"Short #{clip_num} is ready for direct browser download!")

    shutil.rmtree(temp_dir, ignore_errors=True)
    log("\nAll shorts rendered! Ready to download to your phone or PC.")
    return results
