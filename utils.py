import os
import re
import logging
from datetime import datetime
from urllib.parse import urlparse, parse_qs

def setup_logging(log_dir='logs', log_level='INFO'):
    """
    Sets up application logging to a file and console.
    Logs will be stored in the specified log_dir.
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    # Convert string log level to logging constant
    log_level_constant = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level_constant,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file), # Log to file
            logging.StreamHandler()        # Log to console
        ]
    )
    logging.getLogger(__name__).info(f"Logging setup complete. Level: {log_level}")

def extract_video_id(url):
    """
    Extracts the YouTube video ID from various YouTube URL formats.
    """
    # Regex patterns for different YouTube URL structures
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)', # Standard watch?v= or /v/
        r'(?:embed\/)([0-9A-Za-z_-]{11})',         # Embed URLs
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',     # Shortened youtu.be URLs
        # Add more patterns if other specific formats are encountered
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1) # Return the captured video ID
    return None # Return None if no ID is found

def format_file_size(size_bytes):
    """
    Formats a file size in bytes into a human-readable string (e.g., KB, MB, GB).
    """
    if size_bytes is None or size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"] # Added TB, PB for larger files
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def validate_youtube_url(url):
    """
    Validates if the given URL is a valid YouTube video URL.
    Checks for common YouTube domains and the presence of a valid video ID.
    """
    # Standard YouTube domains
    youtube_domains = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove 'www.' prefix if present for consistent domain checking
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check if the domain is a recognized YouTube domain
        is_youtube_domain = domain in youtube_domains
        
        # Check if a valid video ID can be extracted
        has_video_id = extract_video_id(url) is not None
        
        return is_youtube_domain and has_video_id
    except Exception as e:
        logging.getLogger(__name__).error(f"Error validating URL {url}: {e}")
        return False