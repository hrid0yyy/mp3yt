import os
import argparse
import shutil
from yt_dlp import YoutubeDL

def _resolve_ffmpeg_location():
    """
    Return a valid ffmpeg location for yt-dlp (directory or binary path), or None to use PATH.
    Tries:
      1) FFMPEG_PATH env (dir or binary)
      2) ffmpeg on PATH
      3) imageio-ffmpeg (auto-downloads a static ffmpeg)
    """
    loc = os.environ.get("FFMPEG_PATH")
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"

    if loc:
        if os.path.isdir(loc):
            cand = os.path.join(loc, exe)
            if os.path.isfile(cand):
                return loc
            raise RuntimeError(f"FFmpeg not found in FFMPEG_PATH directory: {loc}. Expected {exe} there.")
        if os.path.isfile(loc) and os.path.basename(loc).lower().startswith("ffmpeg"):
            return loc
        raise RuntimeError(f"FFMPEG_PATH is set but invalid: {loc}. Point it to ffmpeg's bin directory or binary.")

    # Try PATH
    on_path = shutil.which("ffmpeg")
    if on_path:
        return None  # yt-dlp will use PATH

    # Try imageio-ffmpeg fallback (auto-downloads a static ffmpeg)
    try:
        import imageio_ffmpeg
        ffpath = imageio_ffmpeg.get_ffmpeg_exe()
        if (ffpath and os.path.isfile(ffpath)):
            return ffpath
    except Exception:
        pass

    raise RuntimeError(
        "FFmpeg not found. Install it and add to PATH, set FFMPEG_PATH to its bin or binary, "
        "or install imageio-ffmpeg: pip install imageio-ffmpeg"
    )

def _try_pytube_fallback(url: str, output_dir: str) -> str:
    """
    Fallback using pytube when yt-dlp fails
    """
    try:
        from pytube import YouTube
        import subprocess
        
        yt = YouTube(url)
        # Get the best audio stream
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise RuntimeError("No audio stream found")
            
        # Download the audio file
        audio_file = audio_stream.download(output_path=output_dir)
        
        # Convert to MP3 using ffmpeg
        base_name = os.path.splitext(audio_file)[0]
        mp3_file = f"{base_name}.mp3"
        
        ffmpeg_loc = _resolve_ffmpeg_location()
        ffmpeg_cmd = "ffmpeg"
        if ffmpeg_loc:
            if os.path.isdir(ffmpeg_loc):
                ffmpeg_cmd = os.path.join(ffmpeg_loc, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            else:
                ffmpeg_cmd = ffmpeg_loc
                
        subprocess.run([
            ffmpeg_cmd, "-i", audio_file, "-acodec", "mp3", "-ab", "192k", mp3_file, "-y"
        ], check=True, capture_output=True)
        
        # Clean up original file
        if os.path.exists(audio_file):
            os.remove(audio_file)
            
        return mp3_file
    except Exception as e:
        raise RuntimeError(f"Pytube fallback failed: {e}")

def download_mp3(url: str, output_dir: str = "downloads") -> str:
    os.makedirs(output_dir, exist_ok=True)
    
    # Add more robust error handling
    try:
        ffmpeg_loc = _resolve_ffmpeg_location()
    except Exception as e:
        raise RuntimeError(f"FFmpeg setup failed: {e}")
    
    # First try yt-dlp with minimal config for hosting platforms
    ydl_opts = {
        "format": "bestaudio/best",
        "restrictfilenames": True,
        "outtmpl": os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "prefer_ffmpeg": True,
        "ffmpeg_location": ffmpeg_loc,
        # Minimal headers to avoid detection
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        # Simplified extractor args
        "extractor_args": {
            "youtube": {
                "skip": ["hls", "dash"],
            }
        },
        "no_check_certificate": True,
        "force_ipv4": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_mp3 = ydl.prepare_filename({**info, "ext": "mp3"})
            
            if not os.path.isfile(final_mp3):
                # Try fallback path detection
                rd = (info.get("requested_downloads") or [])
                cand = next((d.get("filepath") for d in rd if d.get("filepath")), None)
                if cand:
                    base, _ = os.path.splitext(cand)
                    if os.path.isfile(base + ".mp3"):
                        final_mp3 = base + ".mp3"
            
            if not os.path.isfile(final_mp3):
                raise RuntimeError("MP3 file not created by yt-dlp")
                
            return final_mp3
            
    except Exception as e:
        error_str = str(e)
        
        # Check for various yt-dlp failure patterns - try pytube fallback
        if any(pattern in error_str for pattern in [
            "Failed to extract any player response",
            "player response", 
            "Sign in to confirm you're not a bot",
            "HTTP Error 403",
            "HTTP Error 429"
        ]):
            try:
                return _try_pytube_fallback(url, output_dir)
            except Exception as pytube_error:
                raise RuntimeError(f"🚫 **Both yt-dlp and pytube failed on this hosting platform.**\n\n**Main Error:** {str(e)[:200]}...\n\n**Fallback Error:** {str(pytube_error)[:200]}...\n\n💡 **Solutions:**\n• Try different videos (some work better)\n• Wait 15+ minutes between attempts\n• Run locally: `streamlit run main.py`\n• Use a VPS for reliable hosting")
        else:
            # For other errors, still try pytube as last resort
            try:
                return _try_pytube_fallback(url, output_dir)
            except Exception:
                # If pytube also fails, show original error
                raise RuntimeError(f"🚫 **Download failed:** {str(e)[:300]}...\n\n💡 **This is expected on hosting platforms due to YouTube's bot detection.**")

def download_mp3_bytes(url: str, output_dir: str = "downloads"):
    """
    Download the video's audio as MP3 and return (filename, bytes).
    """
    mp3_path = download_mp3(url, output_dir)
    filename = os.path.basename(mp3_path)
    with open(mp3_path, "rb") as f:
        data = f.read()
    return filename, data

def main():
    parser = argparse.ArgumentParser(description="Download a YouTube video's audio as MP3.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-o", "--output-dir", default="downloads", help="Output directory")
    args = parser.parse_args()

    out = download_mp3(args.url, args.output_dir)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
