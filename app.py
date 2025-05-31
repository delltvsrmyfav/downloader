import eventlet
eventlet.monkey_patch() # Must be the absolute first thing!

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import yt_dlp
import os
import re
import logging
from collections import deque

# --- Configure Logging ---
# Get the Flask app logger
app_logger = logging.getLogger(__name__)
app_logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatters and add them to handlers
formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
console_handler.setFormatter(formatter)

# Add handlers to the logger (prevent adding multiple times on reload in debug mode)
if not app_logger.handlers:
    app_logger.addHandler(console_handler)

# Set up logging for yt-dlp to emit to client and console
class YtDlpLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET, socketio_instance=None, session_id=None, app_instance=None):
        super().__init__(name, level)
        self.socketio_instance = socketio_instance
        self.session_id = session_id
        self.app_instance = app_instance
        self.set_log_level('INFO') # Default to INFO, allows progress messages

        self.levelname_map = {
            logging.DEBUG: 'DEBUG',
            logging.INFO: 'INFO',
            logging.WARNING: 'WARNING',
            logging.ERROR: 'ERROR',
            logging.CRITICAL: 'CRITICAL'
        }

    def set_log_level(self, level_name):
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        self.setLevel(level_map.get(level_name.upper(), logging.INFO))

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, **kwargs):
        log_message = msg % args

        if self.socketio_instance and self.session_id and self.app_instance:
            with self.app_instance.app_context():
                # Emit to 'progress_update' as per your original JS
                self.socketio_instance.emit('progress_update', {'progress': 0, 'message': f'yt-dlp: {log_message}'}, room=self.session_id)

        if level >= logging.INFO:
            app_logger.info(f"yt-dlp {self.levelname_map.get(level, 'UNKNOWN')}: {log_message}")


# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_you_should_change_in_production') # CHANGE THIS FOR PRODUCTION!
socketio = SocketIO(app, async_mode='eventlet')

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

download_queue = deque()

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best', # Fetch best video and audio, then mux
            'no_warnings': True,
            'quiet': True, # Suppress most console output from yt-dlp itself
            'extract_flat': True, # Handle playlists by extracting info for each item (no download)
            'force_generic_extractor': False,
            'dump_single_json': True, # Get full info as JSON
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            title = info.get('title', 'N/A')
            thumbnail = info.get('thumbnail', '')
            channel = info.get('channel', 'N/A')
            duration = info.get('duration', 0)
            view_count = info.get('view_count', 0)
            description = info.get('description', 'No description available.')
            uploader = info.get('uploader', 'N/A')
            upload_date = info.get('upload_date', 'N/A') # YYYYMMDD
            webpage_url = info.get('webpage_url', url)

            formats = []
            for f in info.get('formats', []):
                # We need both video (vcodec != 'none') and audio (acodec != 'none') streams
                # or combined formats. Check for proper URL and at least one codec.
                if 'url' in f and (f.get('vcodec') != 'none' or f.get('acodec') != 'none'):
                    height = f.get('height')
                    
                    # Determine a user-friendly resolution string
                    resolution_str = f"{height}p" if height else (f.get('resolution') or 'N/A')

                    # If it's an audio-only stream (no video codec, no height), explicitly mark it
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and height is None:
                        resolution_str = "Audio"
                    elif height is None and not f.get('acodec'):
                        # Skip if it's neither video nor audio (e.g., subtitles, metadata)
                        continue 

                    formats.append({
                        'format_id': f.get('format_id'),
                        'ext': f.get('ext'),
                        'quality': f.get('format_note') or resolution_str or 'N/A', # Use height for quality
                        'resolution': resolution_str, # Use height for resolution display
                        'width': f.get('width'), # Include width and height for client-side filtering
                        'height': height,
                        'filesize': f.get('filesize'),
                        'url': f.get('url'),
                        'vcodec': f.get('vcodec'),
                        'acodec': f.get('acodec')
                    })
            
            # Sort formats primarily by height (descending), then by filesize (descending)
            # This ensures higher quality video appears first, then audio
            formats.sort(key=lambda x: (
                x['height'] if x['height'] is not None else (-1 if x.get('resolution') == 'Audio' else -2), # -1 for Audio, -2 for unknown
                x['filesize'] if x['filesize'] is not None else 0
            ), reverse=True)

            return jsonify({
                'title': title,
                'thumbnail': thumbnail,
                'channel': channel,
                'duration': duration,
                'view_count': view_count,
                'description': description,
                'formats': formats,
                'original_url': url,
                'uploader': uploader,
                'upload_date': upload_date,
                'webpage_url': webpage_url
            })

    except yt_dlp.utils.DownloadError as e:
        app_logger.error(f"yt-dlp Download Error while getting info: {e}")
        return jsonify({'error': f'Failed to get video info: {str(e)}'}), 500
    except Exception as e:
        app_logger.error(f"An unexpected error occurred while fetching video information: {e}", exc_info=True)
        return jsonify({'error': 'An unexpected error occurred while fetching video information.'}), 500

@app.route('/summarize_video', methods=['POST'])
def summarize_video():
    data = request.json
    title = data.get('title')
    description = data.get('description')

    if not title and not description:
        return jsonify({'error': 'No video title or description provided for summarization.'}), 400

    if description and description != 'No description available.':
        # Limit description to prevent excessively long summaries or API calls
        summary_text = f"Summary of '{title}': {description[:500].strip()}..."
        if len(description) > 500:
            summary_text += "\n(Description trimmed for summarization)"
    elif title:
        summary_text = f"No detailed description available, but the video is titled '{title}'."
    else:
        summary_text = "Could not generate summary."

    return jsonify({'summary': summary_text})


# --- SocketIO Event Handlers ---
@socketio.on('connect')
def test_connect():
    app_logger.info(f"Client connected: {request.sid}")
    # Original JS expects 'status_update' for initial connection
    emit('status_update', {'message': 'Connected to server!'})

@socketio.on('disconnect')
def test_disconnect():
    app_logger.info(f"Client disconnected: {request.sid}")

@socketio.on('start_download')
def handle_start_download(data):
    video_url = data['video_url']
    format_id = data['format_id']
    video_title = data['video_title']
    session_id = request.sid

    app_logger.info(f"Received download request for {video_url} with format {format_id}")
    # Use 'progress_update' as per your original JS
    emit('progress_update', {'progress': 0, 'message': 'Starting download...', 'status': 'preparing'}, room=session_id)

    socketio.start_background_task(download_video_task, app, socketio, video_url, format_id, video_title, session_id)


# --- Background Task for Download ---
def download_video_task(app_instance, socketio_instance, video_url, format_id, video_title, session_id):
    with app_instance.app_context():
        try:
            # Clean title for filename: remove invalid chars, replace spaces with underscores
            clean_title = re.sub(r'[^\w\s.-]', '', video_title).strip().replace(' ', '_')
            # Ensure it's not empty after cleaning
            if not clean_title:
                clean_title = "downloaded_video"

            # Limit filename length to prevent issues with OS file systems
            if len(clean_title) > 100:
                clean_title = clean_title[:100]


            def progress_hook(d):
                with app_instance.app_context():
                    if d['status'] == 'downloading':
                        total_bytes = d.get('total_bytes')
                        downloaded_bytes = d.get('downloaded_bytes')
                        
                        total_bytes_str = d.get('total_bytes_str')
                        downloaded_bytes_str = d.get('downloaded_bytes_str')
                        speed = d.get('speed_str')
                        eta = d.get('eta_str')

                        percent = 0
                        message = "Downloading..."

                        if total_bytes is not None and downloaded_bytes is not None and total_bytes > 0:
                            percent = (downloaded_bytes / total_bytes) * 100
                            message = (
                                f"Downloading: {downloaded_bytes_str or 'N/A'} / {total_bytes_str or 'N/A'} "
                                f"at {speed or 'N/A'} ETA {eta or 'N/A'}"
                            )
                        else:
                            # Fallback if total_bytes is not available yet (e.g., pre-processing)
                            message_parts = ["Downloading..."]
                            if downloaded_bytes_str:
                                message_parts.append(f"Downloaded: {downloaded_bytes_str}")
                            if speed:
                                message_parts.append(f"Speed: {speed}")
                            if eta:
                                message_parts.append(f"ETA: {eta}")
                            message = " ".join(message_parts)
                            percent = d.get('progress', 0) # Use a generic 'progress' if available

                        # Emit to 'progress_update' as per your original JS
                        socketio_instance.emit('progress_update', {'progress': percent, 'message': message, 'status': 'downloading'}, room=session_id)
                        app_logger.info(f"Download Progress: {percent:.1f}% - {message}")

                    elif d['status'] == 'finished':
                        filename = d['filename']
                        # Ensure filename is just the basename, not the full path for client
                        final_filename_basename = os.path.basename(filename)

                        # Verify file exists on disk
                        full_download_path = os.path.join(DOWNLOAD_FOLDER, final_filename_basename)
                        if os.path.exists(full_download_path):
                            app_logger.info(f"Verification: File '{full_download_path}' successfully found on disk.")
                        else:
                            app_logger.error(f"Verification ERROR: File '{full_download_path}' NOT FOUND on disk after download!")
                            with app_instance.app_context():
                                # Emit to 'download_error' as per your original JS expectations
                                socketio_instance.emit('download_error', {'message': f'Download reported complete, but file not found: {final_filename_basename}'}, room=session_id)
                            return

                        # Emit to 'progress_update' and 'download_complete' as per your original JS
                        socketio_instance.emit('progress_update', {'progress': 100, 'message': 'Download complete!', 'status': 'finished'}, room=session_id)
                        socketio_instance.emit('download_complete', {
                            'filename': final_filename_basename,
                            'file_url': f'/downloads/{final_filename_basename}',
                            'message': 'Download completed successfully!'
                        }, room=session_id)
                        app_logger.info(f"Download finished: {final_filename_basename}")

            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{clean_title}.%(ext)s"),
                'progress_hooks': [progress_hook],
                'logger': YtDlpLogger(
                    'yt_dlp_logger',
                    socketio_instance=socketio_instance,
                    session_id=session_id,
                    app_instance=app_instance,
                ),
                'quiet': False, # Set to False to allow yt-dlp logger to work
                'verbose': True, # Verbose will send more messages to logger
                'no_warnings': False,
            }

            app_logger.info(f"Starting yt-dlp download with opts: {ydl_opts}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            app_logger.info(f"yt-dlp download process completed for {video_url}.")

        except yt_dlp.utils.DownloadError as e:
            app_logger.error(f"yt-dlp Download Error in task for {video_url}: {e}", exc_info=True)
            with app_instance.app_context():
                # Emit to 'download_error' as per your original JS expectations
                socketio_instance.emit('download_error', {'message': f'Download failed: {str(e)}'}, room=session_id)
        except Exception as e:
            app_logger.error(f"An unexpected error occurred during download for {video_url}: {e}", exc_info=True)
            with app_instance.app_context():
                # Emit to 'download_error' as per your original JS expectations
                socketio_instance.emit('download_error', {'message': f'An unexpected error occurred during download: {str(e)}'}, room=session_id)


# --- File Serving for Downloads ---
@app.route('/downloads/<path:filename>')
def serve_downloaded_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


# --- Main Application Run Block ---
if __name__ == '__main__':
    app_logger.info("Starting Flask-SocketIO application...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)