import os
import sys
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = tempfile.mkdtemp()

COOKIES_FROM_BROWSER = None
COOKIES_FILE = None

args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == '--cookies-from-browser' and i + 1 < len(args):
        COOKIES_FROM_BROWSER = args[i + 1]; i += 2
    elif args[i].startswith('--cookies-from-browser='):
        COOKIES_FROM_BROWSER = args[i].split('=', 1)[1]; i += 1
    elif args[i] == '--cookies' and i + 1 < len(args):
        COOKIES_FILE = args[i + 1]; i += 2
    elif args[i].startswith('--cookies='):
        COOKIES_FILE = args[i].split('=', 1)[1]; i += 1
    else:
        i += 1


def get_base_opts():
    import shutil

    node_path = shutil.which('node')
    ffmpeg_path = shutil.which('ffmpeg')

    opts = {
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': ffmpeg_path or 'ffmpeg',  # ✅ penting buat Railway
        'remote_components': 'ejs:github',
    }

    # ✅ cuma set node kalau ada
    if node_path:
        opts['js_runtimes'] = {'node': {'path': node_path}}

    # ✅ cookies tetap jalan
    if COOKIES_FROM_BROWSER:
        opts['cookiesfrombrowser'] = (COOKIES_FROM_BROWSER, None, None, None)
    elif COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE

    return opts


@app.route('/')
def index():
    return send_file('index.html')

@app.route('/info')
def get_info():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL kosong'}), 400

    opts = get_base_opts()
    opts['skip_download'] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    formats = info.get('formats', [])
    available = set()
    for f in formats:
        h = f.get('height')
        if h and f.get('vcodec', 'none') != 'none':
            available.add(h)

    return jsonify({
        'title':               info.get('title'),
        'channel':             info.get('channel') or info.get('uploader'),
        'duration':            info.get('duration'),
        'thumbnail':           info.get('thumbnail'),
        'available_qualities': sorted(available),
    })


@app.route('/download')
def download_video():
    url     = request.args.get('url', '').strip()
    fmt     = request.args.get('format', 'video')
    quality = request.args.get('quality', '720')
    ext     = request.args.get('ext', 'mp3')

    if not url:
        return jsonify({'error': 'URL kosong'}), 400

    output_template = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
    opts = get_base_opts()

    if fmt == 'audio':
        opts.update({
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': ext,
                'preferredquality': '192',
            }],
        })
    else:
        opts.update({
            'format': (
                f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]'
                f'/bestvideo[height<={quality}]+bestaudio'
                f'/best[height<={quality}]'
                f'/best'
            ),
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
        })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            base = os.path.splitext(filename)[0]

            for candidate_ext in ([ext] if fmt == 'audio' else ['mp4', 'mkv', 'webm']):
                candidate = base + '.' + candidate_ext
                if os.path.exists(candidate):
                    filename = candidate
                    break

            if not os.path.exists(filename):
                files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)
                         if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
                if files:
                    filename = max(files, key=os.path.getmtime)

            if not os.path.exists(filename):
                return jsonify({'error': 'File tidak ditemukan setelah download'}), 500

            # ✅ INI YANG MISSING — return send_file
            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))

    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/status')
def status():
    return jsonify({
        'cookies_from_browser': COOKIES_FROM_BROWSER,
        'cookies_file': COOKIES_FILE,
        'cookies_configured': bool(COOKIES_FROM_BROWSER or COOKIES_FILE),
    })


if __name__ == '__main__':
    print("=" * 50)
    print("  YTGrab Backend — http://localhost:5000")
    print("=" * 50)
    if COOKIES_FROM_BROWSER:
        print(f"  Cookies browser : {COOKIES_FROM_BROWSER}")
    elif COOKIES_FILE:
        print(f"  Cookies file    : {COOKIES_FILE}")
    else:
        print("  ⚠ Tidak ada cookies!")
        print("  Jalankan: python server.py --cookies cookies.txt")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=5000)
