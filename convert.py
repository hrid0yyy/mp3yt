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
        if ffpath and os.path.isfile(ffpath):
            return ffpath
    except Exception:
        pass

    raise RuntimeError(
        "FFmpeg not found. Install it and add to PATH, set FFMPEG_PATH to its bin or binary, "
        "or install imageio-ffmpeg: pip install imageio-ffmpeg"
    )

def download_mp3(url: str, output_dir: str = "downloads") -> str:
    os.makedirs(output_dir, exist_ok=True)
    
    # Add more robust error handling
    try:
        ffmpeg_loc = _resolve_ffmpeg_location()
    except Exception as e:
        raise RuntimeError(f"FFmpeg setup failed: {e}")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "restrictfilenames": True,
        "outtmpl": os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "prefer_ffmpeg": True,
        "ffmpeg_location": ffmpeg_loc,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
        "quiet": True,  # Reduce noise in Streamlit
        "no_warnings": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # First extract info to check if video is accessible
            info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("Could not extract video information")
                
            # Now download and convert
            info = ydl.extract_info(url, download=True)

            # Predict final mp3 path using yt-dlp's templating, forcing ext=mp3
            final_mp3 = ydl.prepare_filename({**info, "ext": "mp3"})
            if not os.path.isfile(final_mp3):
                # Fallback: inspect requested_downloads
                rd = (info.get("requested_downloads") or [])
                cand = next((d.get("filepath") for d in rd if d.get("filepath")), None)
                if cand:
                    if cand.lower().endswith(".mp3") and os.path.isfile(cand):
                        final_mp3 = cand
                    else:
                        base, _ = os.path.splitext(cand)
                        if os.path.isfile(base + ".mp3"):
                            final_mp3 = base + ".mp3"

            if not os.path.isfile(final_mp3):
                # List all files in output directory for debugging
                files = os.listdir(output_dir) if os.path.exists(output_dir) else []
                raise RuntimeError(f"MP3 file not found. Expected: {final_mp3}. Files in {output_dir}: {files}")

            return final_mp3
    except Exception as e:
        raise RuntimeError(f"MP3 conversion failed: {str(e)}") from e

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
