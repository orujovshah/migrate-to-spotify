"""
Gradio Web UI for YouTube to Spotify Playlist Transfer
Beautiful browser-based interface for playlist migration
"""

import gradio as gr
import logging
import sys
import os
import requests
import threading
from typing import Tuple, Dict, List, Optional, Generator
from datetime import datetime

from transfer import PlaylistTransfer
from utils import extract_playlist_id
    
from io import BytesIO
from colorthief import ColorThief

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging for UI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/transfer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Track per-session fetch cancellation signals.
_FETCH_CANCEL_EVENTS: Dict[str, threading.Event] = {}
_FETCH_CANCEL_LOCK = threading.Lock()


# Model size information
MODEL_SIZES = {
    'paraphrase-MiniLM-L3-v2': '~60MB',
    'all-MiniLM-L6-v2': '~80MB',
    'all-MiniLM-L12-v2': '~120MB',
    'all-mpnet-base-v2': '~420MB'
}

# Model information for UI display
MODEL_INFO = {
    'string_only': {
        'name': 'String Matching Only',
        'size': '0MB',
        'description': 'Uses basic text similarity without AI models',
        'benefits': 'Fastest matching, no download required, basic accuracy'
    },
    'paraphrase-MiniLM-L3-v2': {
        'name': 'MiniLM-L3',
        'size': '~60MB',
        'description': 'Lightweight sentence transformer model',
        'benefits': 'Very fast matching with decent accuracy'
    },
    'all-MiniLM-L6-v2': {
        'name': 'MiniLM-L6',
        'size': '~80MB',
        'description': 'Balanced sentence transformer model',
        'benefits': 'Fast matching with good accuracy'
    },
    'all-MiniLM-L12-v2': {
        'name': 'MiniLM-L12',
        'size': '~120MB',
        'description': 'Enhanced sentence transformer model',
        'benefits': 'Balanced performance with very good accuracy'
    },
    'all-mpnet-base-v2': {
        'name': 'MPNet Base',
        'size': '~420MB',
        'description': 'Advanced sentence transformer model',
        'benefits': 'Best matching accuracy (slower due to larger size)'
    }
}


def _get_settings():
    """
    Get application settings from config file.

    Returns:
        Settings dictionary or None if not configured
    """
    from config_manager import ConfigManager
    config_mgr = ConfigManager()
    return config_mgr.get_settings()


def _initialize_transfer(settings: dict):
    """
    Initialize PlaylistTransfer with settings.

    Args:
        settings: Configuration dictionary

    Returns:
        Tuple of (transfer_object, error_message)
        If successful: (PlaylistTransfer, None)
        If failed: (None, error_message_string)
    """
    try:
        transfer = PlaylistTransfer(
            youtube_api_key=settings['youtube_api_key'],
            spotify_client_id=settings['spotify_client_id'],
            spotify_client_secret=settings['spotify_client_secret'],
            spotify_redirect_uri=settings['spotify_redirect_uri'],
            spotify_scope=settings['spotify_scope']
        )
        return (transfer, None)
    except Exception as e:
        error_msg = (
            f"❌ Error: Failed to initialize with provided settings.\n\n"
            f"Please check your API credentials in Settings.\n\n"
            f"Details: {str(e)}"
        )
        return (None, error_msg)


def get_model_info_markdown(model_name: str = None) -> str:
    """
    Generate dynamic Markdown for model information display.

    Args:
        model_name: Name of the selected model (e.g., 'all-mpnet-base-v2')
                   If None, loads from settings or uses default

    Returns:
        Markdown string with model information
    """
    # Get model name from settings if not provided
    if model_name is None:
        settings = _get_settings()
        if settings and 'embedding_model' in settings:
            model_name = settings['embedding_model']
        else:
            model_name = 'all-mpnet-base-v2'  # Default

    # Get model info from dictionary
    info = MODEL_INFO.get(model_name, MODEL_INFO['all-mpnet-base-v2'])

    # Special handling for string_only mode
    if model_name == 'string_only':
        return f"""
### About the Matching Method

This application uses **{info['name']}** (no AI model) for track matching.

**Details:**
- **Size:** {info['size']}
- **Download:** Not required
- **Method:** {info['description']}
- **Trade-off:** {info['benefits']}

⚠️ **Note:** String matching is faster but less accurate than semantic models. Consider using a sentence transformer model for better results.
"""

    # For sentence transformer models
    return f"""
### About the Semantic Matching Model

This application uses **{model_name}** ({info['name']}), a sentence transformer model for improved track matching accuracy.

**Model Details:**
- **Size:** {info['size']}
- **Download:** One-time, automatic on first use
- **Purpose:** Semantic similarity matching between YouTube titles and Spotify tracks
- **Benefits:** {info['benefits']}

The model will download automatically when you fetch tracks for the first time.
"""


def validate_cover_image(image_path: str) -> Tuple[bool, str]:
    """
    Validate cover image meets Spotify requirements.

    Args:
        image_path: Path to uploaded image file

    Returns:
        Tuple of (is_valid, error_message)
    """
    from PIL import Image

    if not image_path or not os.path.exists(image_path):
        return True, ""  # No image provided, that's fine

    try:
        # Check file size (max 256KB)
        file_size = os.path.getsize(image_path)
        max_size = 256 * 1024  # 256KB in bytes

        if file_size > max_size:
            size_kb = file_size / 1024
            return False, f"Image too large: {size_kb:.1f}KB (max 256KB). Please compress or resize your image."

        # Check format (JPEG/PNG only)
        with Image.open(image_path) as img:
            if img.format not in ['JPEG', 'PNG']:
                return False, f"Invalid format: {img.format}. Only JPEG and PNG are supported."

            # Check dimensions (Spotify recommends square images)
            width, height = img.size
            if width < 300 or height < 300:
                return False, f"Image too small: {width}x{height}. Minimum recommended size is 300x300 pixels."

        return True, ""

    except Exception as e:
        return False, f"Failed to validate image: {str(e)}"

def _get_session_id(request: Optional[gr.Request]) -> Optional[str]:
    return getattr(request, "session_hash", None) if request else None

def _cancel_current_fetch(request: Optional[gr.Request]) -> None:
    session_id = _get_session_id(request)
    if not session_id:
        return
    with _FETCH_CANCEL_LOCK:
        cancel_event = _FETCH_CANCEL_EVENTS.get(session_id)
        if cancel_event:
            cancel_event.set()

def _start_fetch_run(request: Optional[gr.Request]) -> threading.Event:
    cancel_event = threading.Event()
    session_id = _get_session_id(request)
    if not session_id:
        return cancel_event
    with _FETCH_CANCEL_LOCK:
        previous_event = _FETCH_CANCEL_EVENTS.get(session_id)
        if previous_event:
            previous_event.set()
        _FETCH_CANCEL_EVENTS[session_id] = cancel_event
    return cancel_event

def prepare_fetch(request: gr.Request = None) -> Tuple[str, List, dict, str, gr.update, gr.update, gr.update, gr.update]:
    """
    Cancel any in-flight fetch and immediately reset the UI.
    Runs outside the queue so cancellation can happen immediately.
    """
    _cancel_current_fetch(request)
    return (
        "⏳ Fetching tracks...",
        [],
        {},
        "",
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=True, value="⏳ Fetching... Click to restart", interactive=True),
        gr.update(visible=False)
    )

def fetch_tracks(
        youtube_url: str,
        include_low_confidence: bool,
        progress=gr.Progress(),
        request: gr.Request = None
) -> Generator[Tuple[str, List, dict, str, gr.update, gr.update, gr.update, gr.update], None, None]:
    """
    Fetch and match tracks from YouTube playlist.
    includes progress bar and standard table structure.
    """
    try:
        cancel_event = _start_fetch_run(request)

        def is_cancelled() -> bool:
            return cancel_event.is_set()

        # 1. Immediate Reset: Clear UI instantly on click
        yield (
            "⏳ Fetching tracks...",  # Show status
            [],  # Clear table
            {},  # Clear state
            "",  # Clear stats
            gr.update(visible=True),  # Show loading placeholder
            gr.update(visible=False),  # Hide content
            gr.update(visible=True, value="⏳ Fetching... Click to restart", interactive=True),  # Allow restart while running
            gr.update(visible=False)
        )

        if is_cancelled():
            return

        # Validate input
        if not youtube_url or not youtube_url.strip():
            yield (
                "❌ Error: Please enter a YouTube playlist URL or ID",
                [], {}, "", gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
                gr.update(visible=False)
            )
            return

        progress(0.1, desc="Initializing...")

        if is_cancelled():
            return

        # Load settings
        settings = _get_settings()
        if settings is None:
            yield (
                "❌ Error: API keys not configured. Please check Settings.",
                [], {}, "", gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
                gr.update(visible=False)
            )
            return

        if is_cancelled():
            return

        # Initialize transfer
        transfer, error = _initialize_transfer(settings)
        if error:
            yield (
                error, [], {}, "", gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
                gr.update(visible=False)
            )
            return

        progress(0.2, desc="Fetching YouTube playlist...")

        if is_cancelled():
            return

        # Get Playlist
        playlist_id = extract_playlist_id(youtube_url)
        try:
            playlist_info, videos = transfer.fetch_youtube_playlist(
                playlist_id,
                max_videos=settings.get('max_videos')
            )
        except Exception as e:
            yield (
                f"❌ Error: Could not fetch YouTube playlist\n{str(e)}",
                [], {}, "", gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
                gr.update(visible=False)
            )
            return

        if is_cancelled():
            return

        if not videos:
            yield (
                "❌ Error: No videos found in playlist",
                [], {}, "", gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
                gr.update(visible=False)
            )
            return

        progress(0.4, desc=f"Found {len(videos)} videos. Starting matching...")

        # Progress callback wrapper
        def update_matching_progress(current, total, title):
            if is_cancelled():
                return
            # Map matching progress (0% to 100%) to overall bar (40% to 90%)
            base = 0.4
            scale = 0.5
            overall = base + ((current / total) * scale)
            short_title = title[:40] + "..." if len(title) > 40 else title
            progress(overall, desc=f"Matching {current}/{total}: {short_title}")

        # Match tracks
        matches = transfer.match_tracks(
            videos,
            progress_callback=update_matching_progress,
            cancel_check=is_cancelled
        )

        if is_cancelled():
            return

        progress(0.95, desc="Finalizing matches...")

        # 2. Build Table Data (Restored Structure)
        # Structure: [Checkbox, YouTube Title, Spotify Match, Confidence]
        tracks_data = []
        state_data = {
            'playlist_info': playlist_info,
            'matches': []
        }

        for i, (video, track, status) in enumerate(matches):
            if status == 'matched' or (status == 'low_confidence' and include_low_confidence):
                # Column 1: YouTube Title
                video_title = video['title']

                # Column 2: Spotify Track Info
                track_info = f"{', '.join([a['name'] for a in track['artists']])} - {track['name']}"

                # Column 3: Confidence Label
                confidence = "✓ High" if status == 'matched' else "? Low"

                # Row Structure: [Selected, Col 1, Col 2, Col 3]
                tracks_data.append([
                    True,  # Checkbox
                    video_title,  # YouTube Title
                    track_info,  # Spotify Match
                    confidence  # Confidence
                ])

                # Save full objects to state for the click handler
                state_data['matches'].append({
                    'index': i,
                    'video': video,
                    'track': track,
                    'status': status
                })

        # Calculate Stats
        total = len(matches)
        high = sum(1 for m in matches if m[2] == 'matched')
        low = sum(1 for m in matches if m[2] == 'low_confidence')
        missing = sum(1 for m in matches if m[2] == 'not_found')

        stats_text = f"""
### Fetched Tracks
- **Total:** {total}
- **High Confidence:** {high}
- **Low Confidence:** {low}
- **Not Found:** {missing}
"""

        status_msg = f"""
## ✅ Success!
**Playlist:** {playlist_info['title']}
**Matched:** {len(tracks_data)} tracks
"""

        progress(1.0, desc="Done!")

        # Final Yield
        yield (
            status_msg,
            tracks_data,
            state_data,
            stats_text,
            gr.update(visible=False),  # Hide placeholder
            gr.update(visible=True),  # Show content
            gr.update(visible=False),
            gr.update(visible=True, value="🔄 Fetch Again", interactive=True)  # Show fetch again after display
        )

    except Exception as e:
        yield (
            f"❌ Unexpected Error: {str(e)}",
            [], {}, "", gr.update(visible=True), gr.update(visible=False),
            gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True),
            gr.update(visible=False)
        )

def rgb_to_hex(rgb):
    """Convert (R, G, B) tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def adjust_brightness(rgb, factor=0.85):
    """Slightly darken or brighten an RGB color by factor."""
    r, g, b = rgb
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return (r, g, b)

def get_contrast_text_color(rgb):
    """Return 'white' or 'black' depending on brightness of RGB."""
    r, g, b = rgb
    # Calculate relative luminance
    luminance = (0.2126*r + 0.7152*g + 0.0722*b) / 255
    return 'black' if luminance > 0.6 else 'white'

def generate_youtube_preview(video_id: str, video_info: dict) -> str:
    """
    Generate YouTube video preview HTML with embedded player only.

    Args:
        video_id: YouTube video ID
        video_info: Video metadata (unused)

    Returns:
        HTML string with embedded YouTube player
    """
    try:
        html = f"""
        <iframe
            width="100%"
            height="360"
            src="https://www.youtube.com/embed/{video_id}"
            title="YouTube video player"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowfullscreen
            style="border-radius: 8px;">
        </iframe>
        """
        return html

    except Exception as e:
        return f"<div style='padding: 20px; color: #dc2626;'>❌ Error: {str(e)}</div>"


def show_track_preview(track_id: str, track: dict) -> Tuple[str, str]:
    """
    Generate separate Spotify iframe and lyrics HTML.

    Args:
        track_id: Spotify track ID
        track: Spotify track object with 'name', 'artists', 'album'

    Returns:
        Tuple of (spotify_iframe_html, lyrics_html)
    """
    try:
        track_name = track.get("name", "")
        artists = track.get("artists", [])
        artist_name = artists[0]['name'] if artists else ""
        album_images = track.get("album", {}).get("images", [])
        album_url = album_images[0]["url"] if album_images else None

        # Extract dominant color from album art
        dominant_color = (29, 185, 84)  # fallback green
        if album_url:
            try:
                img_response = requests.get(album_url, timeout=5)
                img_response.raise_for_status()
                color_thief = ColorThief(BytesIO(img_response.content))
                dominant_color = color_thief.get_color(quality=1)
                # Slightly adjust brightness for UI
                dominant_color = adjust_brightness(dominant_color, 0.85)
            except Exception:
                pass

        # Decide text color
        text_color = get_contrast_text_color(dominant_color)
        bg_color_hex = rgb_to_hex(dominant_color)

        # Spotify iframe HTML
        spotify_html = f"""
        <iframe 
            src="https://open.spotify.com/embed/track/{track_id}" 
            width="100%" height="380" frameborder="0" 
            allowtransparency="true" allow="encrypted-media">
        </iframe>
        """

        # Fetch lyrics from lrclib.net
        lyrics = "Lyrics not found"
        try:
            response = requests.get(
                "https://lrclib.net/api/search",
                params={"track_name": track_name, "artist_name": artist_name},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                first_result = data[0]
                lyrics = first_result.get("plainLyrics") or first_result.get("syncedLyrics") or "Lyrics not available"
            else:
                lyrics = "No lyrics found for this track"
        except Exception:
            lyrics = "Could not load lyrics"

        # Lyrics panel HTML
        lyrics_html = f"""
        <div style="max-height: 350px; overflow-y: auto; padding: 15px;
                    border: 1px solid {bg_color_hex}; border-radius: 8px; 
                    background: {bg_color_hex};">
            <pre style="white-space: pre-wrap; color: {text_color}; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;">{lyrics}</pre>
        </div>
        """

        return spotify_html, lyrics_html

    except Exception as e:
        error_html = f"<div style='padding: 20px; color: #dc2626;'>❌ Error: {str(e)}</div>"
        return error_html, error_html


def update_spotify_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update Spotify preview with content and show row"""
    return content, "", "", gr.update(visible=True)


def update_youtube_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update YouTube preview with content and hide Spotify/lyrics row"""
    return "", content, "", gr.update(visible=False)


def update_lyrics_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update lyrics preview with content"""
    return "", "", content, gr.update(visible=True)

def on_track_table_click(state_dict: dict, evt: gr.SelectData):
    """
    Handle clicks on the tracks table with a delayed spinner.
    The spinner is sent immediately but remains invisible via CSS for 0.5s.
    """
    # 1. Reset previews immediately on click
    yield "", "", "", gr.update(visible=False)

    # Basic validations
    if not state_dict or 'matches' not in state_dict:
        return
    if not evt or not hasattr(evt, 'index'):
        return
    if not isinstance(evt.index, (list, tuple)) or len(evt.index) != 2:
        return

    row_idx, col_idx = evt.index

    if not isinstance(row_idx, int) or not isinstance(col_idx, int):
        return
    if row_idx < 0 or col_idx < 0:
        return

    matches = state_dict['matches']
    if row_idx >= len(matches):
        return

    match = matches[row_idx]

    # Shared CSS for delayed visibility
    # This animation keeps opacity at 0 for 0.5s, then sets it to 1
    delayed_fade_in_css = """
        @keyframes delayedFadeIn {
            0% { opacity: 0; }
            99% { opacity: 0; }
            100% { opacity: 1; }
        }
    """

    # --- Column 1: YouTube ---
    if col_idx == 1:
        # YouTube Spinner with CSS Delay
        youtube_spinner = f"""
        <style>
            {delayed_fade_in_css}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .youtube-spinner-container {{
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 400px;
                /* Start hidden, show after 0.5s */
                opacity: 0; 
                animation: delayedFadeIn 0.1s linear 0.5s forwards; 
            }}
            .youtube-spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #FF0000;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
            }}
        </style>
        <div class="youtube-spinner-container">
            <div class="youtube-spinner"></div>
        </div>
        """

        # Yield the (initially invisible) spinner immediately
        yield "", youtube_spinner, "", gr.update(visible=False)

        # Generate content (blocking operation). If this finishes in <0.5s,
        # the spinner above is replaced before it becomes visible.
        video_id = match['video']['video_id']
        youtube_content = generate_youtube_preview(video_id, match['video'])

        yield "", youtube_content, "", gr.update(visible=False)

    # --- Column 2: Spotify ---
    elif col_idx == 2:
        if match['status'] != 'matched':
            no_match_content = "<div style='padding: 40px; text-align: center; color: #666;'>This track was not matched to Spotify</div>"
            yield no_match_content, "", "", gr.update(visible=True)
            return

        # Spotify Spinner with CSS Delay
        spotify_spinner = f"""
        <style>
            {delayed_fade_in_css}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .spotify-lyrics-spinner-container {{
                position: relative;
                min-height: 400px;
                /* Start hidden, show after 0.5s */
                opacity: 0;
                animation: delayedFadeIn 0.1s linear 0.5s forwards;
            }}
            .spotify-lyrics-spinner {{
                position: absolute;
                left: calc(100% - 25px);
                top: calc(50% - 25px);
                border: 4px solid #f3f3f3;
                border-top: 4px solid #1DB954;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
            }}
        </style>
        <div class="spotify-lyrics-spinner-container">
            <div class="spotify-lyrics-spinner"></div>
        </div>
        """

        # Yield the (initially invisible) spinner immediately
        yield spotify_spinner, "", "", gr.update(visible=True)

        # Load content
        track_id = match['track']['id']
        spotify_content, lyrics_content = show_track_preview(track_id, match['track'])

        # Yield result
        yield spotify_content, "", lyrics_content, gr.update(visible=True)

    else:
        yield "", "", "", gr.update(visible=False)

def create_playlist(
    spotify_name: str,
    description: str,
    cover_image,
    make_public: bool,
    tracks_dataframe,
    state_dict,
    progress=gr.Progress()
) -> Tuple[str, str]:
    """
    Create Spotify playlist with selected tracks, description, and cover image.

    Args:
        spotify_name: Name for the Spotify playlist
        description: Playlist description
        cover_image: Path to cover image file (optional)
        make_public: Override default playlist visibility (True=public, False=private, None=use default)
        tracks_dataframe: Dataframe with selected tracks
        state_dict: State dictionary containing playlist data
        progress: Gradio progress tracker

    Returns:
        Tuple of (status_message, playlist_url)
    """
    try:
        # Validate state
        if not state_dict or 'matches' not in state_dict:
            return (
                "❌ Error: Please fetch tracks first before creating playlist",
                ""
            )

        # Validate cover image if provided
        if cover_image is not None:
            is_valid, error_msg = validate_cover_image(cover_image)
            if not is_valid:
                return (
                    f"❌ Cover Image Error: {error_msg}",
                    ""
                )

        progress(0.1, desc="Initializing...")

        # Load configuration
        settings = _get_settings()

        # Check if settings exist
        if settings is None:
            return (
                "❌ Error: API keys not configured. Please configure in Settings first.",
                ""
            )

        # Initialize transfer with settings
        transfer, error = _initialize_transfer(settings)
        if error:
            return (error, "")

        # Get selected tracks from dataframe
        selected_indices = []

        if tracks_dataframe is not None and len(tracks_dataframe) > 0:
            # Handle both list and DataFrame types
            try:
                # Try to convert to list if it's a DataFrame
                if hasattr(tracks_dataframe, 'values'):
                    # It's a pandas DataFrame
                    dataframe_list = tracks_dataframe.values.tolist()
                else:
                    # It's already a list
                    dataframe_list = tracks_dataframe

                for i, row in enumerate(dataframe_list):
                    # Check if selected (first column is checkbox)
                    if row[0]:  # Truthy check handles True, 'True', 1, etc.
                        selected_indices.append(i)

                logger.info(f"Processing {len(dataframe_list)} tracks: {len(selected_indices)} selected, {len(dataframe_list) - len(selected_indices)} unchecked")

            except Exception as e:
                logger.error(f"Error processing dataframe: {e}")
                return (
                    f"❌ Error: Failed to process track selection\n\nDetails: {str(e)}",
                    ""
                )

        if not selected_indices:
            return (
                "❌ Error: No tracks selected. Please select at least one track.",
                ""
            )

        # Filter matches to only selected ones
        selected_matches = [state_dict['matches'][i] for i in selected_indices]

        # Build track IDs list
        track_ids = [match['track']['id'] for match in selected_matches]

        logger.info(f"Creating playlist with {len(track_ids)} tracks")

        progress(0.3, desc="Creating Spotify playlist...")

        # Determine playlist name
        playlist_info = state_dict['playlist_info']
        if not spotify_name or not spotify_name.strip():
            spotify_name = f"{playlist_info['title']} (from YouTube)"

        # Validate playlist name
        if len(spotify_name) > 100:
            return (
                f"❌ Error: Playlist name too long ({len(spotify_name)} characters). Maximum is 100 characters.",
                ""
            )

        # Use custom description if provided, otherwise default
        if not description or not description.strip():
            description = f"Transferred from YouTube playlist: {playlist_info['title']}"

        # Create playlist
        try:
            # Determine playlist visibility:
            # 1. Use checkbox value if explicitly set (True or False)
            # 2. Otherwise, use global setting from Settings
            if make_public is None:
                is_public = settings.get('create_public_playlists', False)
            else:
                is_public = make_public

            playlist_id = transfer.spotify.create_playlist(
                name=spotify_name,
                description=description,
                public=is_public
            )

            if not playlist_id:
                return (
                    "❌ Error: Failed to create playlist",
                    ""
                )

        except Exception as e:
            return (
                f"❌ Error: Failed to create playlist\n\nDetails: {str(e)}",
                ""
            )

        progress(0.5, desc="Adding tracks to playlist...")

        # Add tracks to playlist
        try:
            transfer.spotify.add_tracks_to_playlist(playlist_id, track_ids)
        except Exception as e:
            return (
                f"❌ Error: Failed to add tracks to playlist\n\nDetails: {str(e)}",
                ""
            )

        progress(0.7, desc="Uploading cover image...")

        # Upload cover image if provided
        if cover_image is not None:
            try:
                success = transfer.spotify.upload_playlist_cover(playlist_id, cover_image)
                if success:
                    logger.info("Cover image uploaded successfully")
                else:
                    logger.warning("Failed to upload cover image")
            except Exception as e:
                logger.warning(f"Failed to upload cover image: {e}")
                # Continue anyway, cover image is optional

        progress(1.0, desc="Complete!")

        playlist_url = transfer.spotify.get_playlist_url(playlist_id)

        status_msg = f"""
## 🎉 Playlist Created Successfully!

**Spotify Playlist:** {spotify_name}
**Tracks Added:** {len(track_ids)}
**Description:** {description}

[🎵 Open Playlist on Spotify]({playlist_url})

---

### What's Next?

- Open the playlist in Spotify to enjoy your music
- Share the playlist with friends
- Customize it further in Spotify (reorder tracks, add more songs, etc.)
"""

        return (status_msg, playlist_url)

    except PermissionError as e:
        logger.exception("Permission error during playlist creation")
        return (
            f"❌ Permission Error: Cannot access files. Please check file permissions.\n\nDetails: {str(e)}",
            ""
        )
    except ConnectionError as e:
        logger.exception("Connection error during playlist creation")
        return (
            f"❌ Network Error: Cannot connect to Spotify. Please check your internet connection.\n\nDetails: {str(e)}",
            ""
        )
    except Exception as e:
        logger.exception("Unexpected error during playlist creation")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            ""
        )


def load_current_settings() -> Dict:
    """
    Load current settings for display in UI

    Returns:
        Dictionary with current configuration values
    """
    from config_manager import ConfigManager

    config_mgr = ConfigManager()
    if config_mgr.settings_exist():
        try:
            settings = config_mgr.load_settings()
            # Ensure embedding_model has a default value
            if 'embedding_model' not in settings:
                settings['embedding_model'] = 'all-mpnet-base-v2'
            return settings
        except Exception:
            pass

    # Return empty/default values for new users
    return {
        'youtube_api_key': '',
        'spotify_client_id': '',
        'spotify_client_secret': '',
        'spotify_redirect_uri': 'http://127.0.0.1:8080/callback',
        'spotify_scope': 'playlist-modify-public playlist-modify-private ugc-image-upload',
        'create_public_playlists': False,
        'max_videos': None,
        'embedding_model': 'all-mpnet-base-v2'
    }


def populate_settings_ui():
    """
    Load settings from config file and return values for UI population.

    Returns:
        Tuple of values matching Settings UI input fields order
    """
    settings = load_current_settings()

    return (
        settings.get('youtube_api_key', ''),
        settings.get('spotify_client_id', ''),
        settings.get('spotify_client_secret', ''),
        settings.get('spotify_redirect_uri', 'http://127.0.0.1:8080/callback'),
        settings.get('spotify_scope', 'playlist-modify-public playlist-modify-private ugc-image-upload'),
        settings.get('create_public_playlists', False),
        settings.get('max_videos'),
        settings.get('embedding_model', 'all-mpnet-base-v2')
    )


def check_model_status() -> str:
    """
    Check if embedding model is downloaded and return status message.

    Returns:
        Markdown formatted status message
    """
    from utils import _embedding_matcher

    try:
        model_name = _embedding_matcher._model_name or 'all-mpnet-base-v2'
        status = _embedding_matcher.get_model_status()

        if model_name == 'string_only':
            return f"""
### 🔤 String Matching Mode

**Status:** {status}

**Details:**
- **No model download required**
- **Matching method:** Traditional string similarity (SequenceMatcher)
- **Pros:** Instant startup, no disk space needed, very fast
- **Cons:** Lower accuracy than AI models, misses semantic similarities

**Note:** This mode is fastest but may miss valid matches. Consider using an AI model for better results.
"""

        # Get model size info
        size = MODEL_SIZES.get(model_name, 'Unknown')

        return f"""
### 🤖 Semantic Matching Model Status

**Current Model:** `{model_name}` &nbsp;&nbsp;&nbsp; **Size:** {size} &nbsp;&nbsp;&nbsp; **Status:** {status}

**How it works:**
- Converts track titles to semantic embeddings (vector representations)
- Compares similarity using cosine distance (0.0 to 1.0)
- Threshold: 0.6 (adjustable in utils.py)

**First-time use:** Model downloads automatically when you fetch tracks.
**Subsequent uses:** Model loads from cache instantly.

**Change model:** Update selection in Settings and restart the app.
"""

    except Exception as e:
        return f"""
### ❌ Error Checking Model Status

Could not check model status: {str(e)}

The model will still attempt to download automatically when needed.
        """


def check_model_status_for_selection(selected_model: str) -> str:
    """
    Check status for a specific model selection (not necessarily loaded).

    Args:
        selected_model: Model name from dropdown selection

    Returns:
        Markdown formatted status message
    """
    from utils import _embedding_matcher

    try:
        # Check if this is the currently configured model
        current_model = _embedding_matcher._model_name or 'all-mpnet-base-v2'
        is_current = (selected_model == current_model)

        # String-only mode
        if selected_model == 'string_only':
            return f"""
### 🔤 String Matching Mode {"**(Currently Active)**" if is_current else ""}

**Status:** No model needed

**Details:**
- **No model download required**
- **Matching method:** Traditional string similarity (SequenceMatcher)
- **Pros:** Instant startup, no disk space needed, very fast
- **Cons:** Lower accuracy than AI models, misses semantic similarities

{"**Note:** This is your current active mode." if is_current else "**Note:** Save settings and restart to activate this mode."}
"""

        # AI model mode
        size = MODEL_SIZES.get(selected_model, 'Unknown')

        # Check if model is downloaded
        is_downloaded = _embedding_matcher.is_model_downloaded(selected_model)

        if is_downloaded:
            status_icon = "✅"
            status_text = "Downloaded and ready"
        else:
            status_icon = "⬇️"
            status_text = "Not downloaded (will download on first use)"

        active_badge = " **(Currently Active)**" if is_current else ""

        return f"""
### 🤖 Semantic Matching Model{active_badge}

**Selected Model:** `{selected_model}`
**Size:** {size}
**Status:** {status_icon} {status_text}

**Model Info:**
- **Speed:** {"Very Fast" if "Mini" in selected_model else "Moderate"}
- **Accuracy:** {"Good" if "L6" in selected_model else "Best" if "mpnet" in selected_model else "Very Good"}
- **Download:** {"Not needed - already cached ✓" if is_downloaded else "Required (~" + size + " download)"}

{"**Note:** This is your current active model." if is_current else "**Note:** Save settings and restart app to activate this model."}
"""

    except Exception as e:
        return f"❌ Error checking model status: {str(e)}"


def download_selected_model_with_progress(selected_model: str, progress=gr.Progress()) -> str:
    """
    Download model with progress tracking.

    Args:
        selected_model: Model name to download
        progress: Gradio Progress object

    Returns:
        Status message markdown
    """
    from utils import _embedding_matcher
    from sentence_transformers import SentenceTransformer

    try:
        # Check if string_only
        if selected_model == 'string_only':
            return "ℹ️ **No Download Needed**\n\nString-only mode doesn't use a model."

        # Check if already downloaded
        if _embedding_matcher.is_model_downloaded(selected_model):
            return f"✅ **Already Downloaded**\n\nModel `{selected_model}` is already in your cache."

        # Show progress
        progress(0, desc="Starting download...")

        size = MODEL_SIZES.get(selected_model, 'Unknown')

        progress(0.3, desc=f"Downloading {selected_model} ({size})...")
        logger.info(f"Downloading model: {selected_model}")

        # Download model
        SentenceTransformer(selected_model)

        progress(1.0, desc="Download complete!")
        logger.info(f"✓ Model {selected_model} downloaded successfully")

        return f"✅ **Download Complete!**\n\nModel `{selected_model}` has been downloaded and cached.\n\nTo use it: Save settings and restart the app."

    except Exception as e:
        logger.error(f"Failed to download model {selected_model}: {e}")
        progress(0, desc="Download failed")
        return f"❌ **Download Failed**\n\nError: {str(e)}\n\nPlease check your internet connection and try again."


def delete_selected_model(selected_model: str) -> str:
    """
    Delete the selected embedding model from disk cache.

    Args:
        selected_model: Model name from dropdown selection

    Returns:
        Status message markdown
    """
    from utils import _embedding_matcher

    try:
        # Check if string_only
        if selected_model == 'string_only':
            return "ℹ️ **No Model to Delete**\n\nString-only mode doesn't use a model."

        # Check if model is actually downloaded
        if not _embedding_matcher.is_model_downloaded(selected_model):
            return f"ℹ️ **Model Not Downloaded**\n\nModel `{selected_model}` is not in your cache."

        # Delete the model
        success, message = _embedding_matcher.delete_model(selected_model)

        if success:
            logger.info(f"Successfully deleted model: {selected_model}")
            return f"✅ **Model Deleted**\n\n{message}\n\nModel `{selected_model}` has been removed from your cache."
        else:
            logger.warning(f"Failed to delete model {selected_model}: {message}")
            return f"❌ **Delete Failed**\n\n{message}"

    except Exception as e:
        logger.error(f"Error deleting model {selected_model}: {e}")
        return f"❌ **Delete Failed**\n\nError: {str(e)}"


def check_config_status() -> str:
    """
    Check if API configuration is saved and return status message.

    Returns:
        Markdown formatted status message
    """
    from config_manager import ConfigManager

    config_mgr = ConfigManager()

    if config_mgr.settings_exist():
        try:
            settings = config_mgr.load_settings()

            # Check if all required fields are present
            required_fields = ['youtube_api_key', 'spotify_client_id', 'spotify_client_secret']
            all_present = all(settings.get(field) for field in required_fields)

            if all_present:
                return """
✅ **Configuration Status:** API credentials are configured and saved in `.app_settings.json`

Your credentials are ready to use. You can update them below if needed.
"""
            else:
                return """
⚠️ **Configuration Status:** Incomplete configuration found

Some required API credentials are missing. Please complete the configuration below.
"""
        except Exception:
            return """
⚠️ **Configuration Status:** Error reading saved configuration

Please configure your API credentials below.
"""
    else:
        return """
❌ **Configuration Status:** No saved configuration found

Please configure your API credentials below to get started.
"""


def restart_application():
    """
    Restart the Gradio application and trigger auto-reload.

    This function uses os.execv() to restart the Python process in-place.
    A 3-second delay is added to allow the restart message to be displayed.
    Returns HTML with JavaScript to automatically reload the page.

    Returns:
        HTML message with JavaScript to reload page
    """
    import time
    import threading

    def delayed_restart():
        """Delay restart to allow message to be displayed"""
        time.sleep(3)  # Increased to 3 seconds
        # Restart the Python process in-place
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    # Start restart in background thread
    restart_thread = threading.Thread(target=delayed_restart, daemon=True)
    restart_thread.start()

    # Return HTML with embedded JavaScript to auto-reload
    return """
<div style="max-width: 100%; padding: 10px; text-align: center; word-wrap: break-word;">
    <h3 style="font-size: 1em; margin: 0 0 8px 0;">🔄 Restarting...</h3>
    <p style="font-size: 0.85em; margin: 0 0 5px 0;">Page will reload automatically.</p>
    <p style="font-size: 0.75em; margin: 0;"><small>If not, refresh manually.</small></p>
</div>

<script>
(function() {
    // Wait 4 seconds, then check if server is back every second
    setTimeout(() => {
        const checkInterval = setInterval(() => {
            fetch(window.top.location.href)
                .then(response => {
                    if (response.ok) {
                        clearInterval(checkInterval);
                        setTimeout(() => {
                            window.top.location.reload(true);  // Force reload in top-level window
                        }, 500);
                    }
                })
                .catch(() => {
                    // Server not ready yet, keep checking
                    console.log('Server not ready, checking again...');
                });
        }, 1000);
    }, 4000);
})();
</script>
"""


def exit_application():
    """
    Exit the Gradio application gracefully.

    Returns:
        HTML message indicating shutdown
    """
    import threading
    import time

    def delayed_exit():
        """Delay exit to allow message to be displayed"""
        time.sleep(2)
        import os
        os._exit(0)  # Force exit the process

    exit_thread = threading.Thread(target=delayed_exit, daemon=True)
    exit_thread.start()

    return """
<div style="max-width: 100%; padding: 10px; text-align: center; word-wrap: break-word;">
    <h3 style="font-size: 1em; margin: 0 0 8px 0;">👋 Shutting down...</h3>
    <p style="font-size: 0.85em; margin: 0 0 5px 0;">Application will close in 2 seconds.</p>
    <p style="font-size: 0.75em; margin: 0;"><small>You can close this browser tab.</small></p>
</div>
"""


def save_settings_handler(
    youtube_api_key: str,
    spotify_client_id: str,
    spotify_client_secret: str,
    spotify_redirect_uri: str,
    spotify_scope: str,
    create_public_playlists: bool,
    max_videos: Optional[float],
    embedding_model: str
) -> str:
    """
    Save settings and return status message

    Args:
        youtube_api_key: YouTube Data API key
        spotify_client_id: Spotify OAuth client ID
        spotify_client_secret: Spotify OAuth client secret
        spotify_redirect_uri: Spotify OAuth redirect URI
        spotify_scope: Spotify API scopes
        create_public_playlists: Whether to create public playlists by default
        max_videos: Maximum videos to process (None for unlimited)
        embedding_model: Semantic matching model to use

    Returns:
        Status message (success or error)
    """
    from config_manager import ConfigManager
    from datetime import datetime

    config_mgr = ConfigManager()

    # Build settings dictionary
    settings = {
        'youtube_api_key': youtube_api_key.strip() if youtube_api_key else '',
        'spotify_client_id': spotify_client_id.strip() if spotify_client_id else '',
        'spotify_client_secret': spotify_client_secret.strip() if spotify_client_secret else '',
        'spotify_redirect_uri': spotify_redirect_uri.strip() if spotify_redirect_uri else 'http://127.0.0.1:8080/callback',
        'spotify_scope': spotify_scope.strip() if spotify_scope else 'playlist-modify-public playlist-modify-private ugc-image-upload',
        'create_public_playlists': create_public_playlists,
        'max_videos': int(max_videos) if max_videos and max_videos > 0 else None,
        'embedding_model': embedding_model,
        'last_updated': datetime.now().isoformat()
    }

    # Validate
    is_valid, errors = config_mgr.validate_settings(settings)
    if not is_valid:
        error_msg = "❌ **Validation Error**\n\n**Please fix the following issues:**\n\n"
        error_msg += "\n".join(f"- {error}" for error in errors)
        return error_msg

    # Save
    success = config_mgr.save_settings(settings)
    if success:
        return """
### ✅ Settings Saved Successfully!

Your API credentials have been saved to `.app_settings.json`.

**What's next:**
- These settings will be used automatically for all future transfers
- You can now fetch and create playlists using the saved credentials
- The CLI (`transfer.py`) will also offer to use these settings

**Security Note:** The settings file is protected in `.gitignore` and will not be committed to version control.
"""
    else:
        return """
❌ **Error: Failed to save settings**

Please check:
- File permissions in the project directory
- Disk space availability
- Try running the app with appropriate permissions
"""


def create_ui():
    """Create and configure Gradio interface"""

    # Initialize embedding model from config
    try:
        from utils import _embedding_matcher

        settings = _get_settings()
        if settings and 'embedding_model' in settings:
            model_name = settings['embedding_model']
            _embedding_matcher.set_model_name(model_name)
            logger.info(f"Configured to use embedding model: {model_name}")
        else:
            _embedding_matcher.set_model_name('all-mpnet-base-v2')
            logger.info("Using default embedding model: all-mpnet-base-v2")
    except Exception as e:
        logger.warning(f"Failed to initialize embedding model config: {e}")
        _embedding_matcher.set_model_name('all-mpnet-base-v2')

    # Custom CSS for better styling
    custom_css = """
    .container {
        max-width: 1400px;
        margin: auto;
    }
    .output-markdown {
        font-size: 16px;
    }
    .progress-bar {
        margin: 20px 0;
    }

    /* Remove white glow from all input fields */
    input[type="password"],
    input[type="text"],
    textarea {
        border: 1px solid #d0d0d0 !important;
        box-shadow: none !important;
    }

    input[type="password"]:focus,
    input[type="text"]:focus,
    textarea:focus {
        border-color: #7c3aed !important;
        box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.1) !important;
        outline: none !important;
    }
    """

    with gr.Blocks(
        theme=gr.themes.Soft(),
        css=custom_css,
        title="YouTube to Spotify Playlist Transfer"
    ) as app:

        # Main header with restart button in top-right corner
        with gr.Row():
            with gr.Column(scale=10):
                gr.Markdown(
                    """
                    # 🎵 YouTube to Spotify Playlist Transfer

                    Automatically transfer your YouTube playlists to Spotify with intelligent track matching.

                    ### How to use:
                    1. **Fetch Tracks**: Enter YouTube playlist URL and click "Fetch Tracks"
                    2. **Review & Select**: Review matched tracks and uncheck any you don't want
                    3. **Customize**: Add cover image and description (optional)
                    4. **Create**: Click "Create Spotify Playlist"

                    ---
                    """
                )
            with gr.Column(scale=1, min_width=200):
                restart_btn = gr.Button(
                    "🔄 Restart App",
                    variant="secondary",
                    size="lg"
                )
                restart_status = gr.HTML("", visible=False)

                exit_btn = gr.Button(
                    "❌ Exit App",
                    variant="stop",
                    size="lg"
                )
                exit_status = gr.HTML("", visible=False)

        # State to store matched tracks between steps
        state = gr.State({})

        # Settings Section
        gr.Markdown("## ⚙️ Settings & Configuration")

        with gr.Accordion("API Configuration", open=False):
            # Configuration status indicator
            config_status_display = gr.Markdown()

            gr.Markdown("""
### Configure Your API Credentials

Settings are saved locally and will be used for all future transfers.

**Need API keys?** Follow these guides:
- **YouTube Data API Key**: [Get it from Google Cloud Console →](https://console.cloud.google.com/apis/credentials)
- **Spotify Application**: [Create one on Spotify Dashboard →](https://developer.spotify.com/dashboard)
            """)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### YouTube API")
                    youtube_api_key_input = gr.Textbox(
                        label="YouTube API Key",
                        type="password",
                        placeholder="AIzaSy...",
                        info="Required for fetching YouTube playlists"
                    )
                    gr.Markdown("""
**How to get YouTube API Key:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing one)
3. Enable **YouTube Data API v3** in APIs & Services → Library
4. Go to Credentials → Create Credentials → API Key
5. Copy the API key and paste it above
                    """)

                with gr.Column():
                    gr.Markdown("#### Spotify API")
                    spotify_client_id_input = gr.Textbox(
                        label="Spotify Client ID",
                        placeholder="abc123...",
                        info="From your Spotify Developer app"
                    )
                    spotify_client_secret_input = gr.Textbox(
                        label="Spotify Client Secret",
                        type="password",
                        placeholder="xyz789...",
                        info="Keep this secret!"
                    )
                    gr.Markdown("""
**How to get Spotify Credentials:**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click **Create an App**
4. Fill in any name/description
5. Copy the **Client ID** and **Client Secret**
6. In app settings, add this Redirect URI: `http://127.0.0.1:8080/callback`
                    """)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Advanced Settings")
                    spotify_redirect_uri_input = gr.Textbox(
                        label="Spotify Redirect URI",
                        placeholder="http://127.0.0.1:8080/callback",
                        info="Must match what you set in Spotify app settings"
                    )
                    spotify_scope_input = gr.Textbox(
                        label="Spotify API Scopes",
                        placeholder="playlist-modify-public playlist-modify-private ugc-image-upload",
                        info="OAuth permissions (keep default unless you know what you're doing)"
                    )

                with gr.Column():
                    gr.Markdown("#### Playlist Options")
                    create_public_input = gr.Checkbox(
                        label="Create Public Playlists by Default",
                        value=False,
                        info="Uncheck for private playlists"
                    )
                    max_videos_input = gr.Number(
                        label="Maximum Videos to Process",
                        value=None,
                        precision=0,
                        info="Leave empty for unlimited"
                    )

                    embedding_model_input = gr.Dropdown(
                        choices=[
                            ("String matching only (0MB, fastest, basic accuracy)", "string_only"),
                            ("MiniLM-L3 (60MB, very fast, decent accuracy)", "paraphrase-MiniLM-L3-v2"),
                            ("MiniLM-L6 (80MB, fast, good accuracy)", "all-MiniLM-L6-v2"),
                            ("MiniLM-L12 (120MB, balanced, very good accuracy)", "all-MiniLM-L12-v2"),
                            ("MPNet Base (420MB, slower, best accuracy) [Default]", "all-mpnet-base-v2")
                        ],
                        value="all-mpnet-base-v2",
                        label="🧠 Semantic Matching Model",
                        info="⚠️ Restart app after changing. Smaller models = faster but less accurate matching."
                    )

            save_settings_btn = gr.Button("💾 Save Settings", variant="primary", size="lg")
            settings_status = gr.Markdown()

        # Model Status Section
        with gr.Accordion("🤖 Semantic Matching Model Status", open=False):
            model_info_display = gr.Markdown(get_model_info_markdown())

            with gr.Row():
                check_model_btn = gr.Button("🔍 Check Model Status", size="sm")
                download_model_btn = gr.Button("⬇️ Download Selected Model", size="sm", variant="primary")
                delete_model_btn = gr.Button("🗑️ Delete Selected Model", size="sm", variant="stop")

            model_status_display = gr.Markdown("**Status:** Click button to check")

        gr.Markdown("---")

        # Step 1: Fetch Tracks
        gr.Markdown("## Step 1: Fetch Tracks from YouTube")

        with gr.Row():
            with gr.Column(scale=2):
                youtube_input = gr.Textbox(
                    label="YouTube Playlist URL or ID",
                    placeholder="https://www.youtube.com/playlist?list=PLxxxxxx or PLxxxxxx",
                    lines=1,
                    info="Paste the full URL or just the playlist ID"
                )

                include_low_conf = gr.Checkbox(
                    label="Include Low Confidence Matches",
                    value=True,
                    info="Include tracks that might not be exact matches"
                )

                fetch_btn = gr.Button(
                    "🔍 Fetch Tracks",
                    variant="primary",
                    size="lg"
                )

                fetch_again_btn = gr.Button(
                    "🔄 Fetch Again",
                    variant="secondary",
                    size="lg",
                    visible=False
                )

            with gr.Column(scale=1):
                gr.Markdown(
                    """
                    ### ℹ️ Information

                    **Requirements:**
                    - YouTube API key
                    - Spotify API credentials
                    - Configure in **Settings** tab

                    **Features:**
                    - Semantic similarity matching
                    - Track preview & selection
                    - Playlist customization
                    """
                )

        fetch_status = gr.Markdown(
            value="Ready to fetch tracks. Enter a YouTube playlist URL above."
        )

        fetch_stats = gr.Markdown()

        gr.Markdown("---")

        # Step 2: Review and Select Tracks
        with gr.Column(visible=True):
            gr.Markdown("## Step 2: Review & Select Tracks")

            # Placeholder shown initially
            with gr.Row(visible=True) as step2_placeholder:
                gr.Markdown("""
### ⏳ Waiting for tracks...

Please complete **Step 1** to fetch and preprocess your YouTube playlist tracks.

Once processing is complete, this section will show:
- All matched tracks from your playlist
- Confidence levels for each match
- Ability to select/deselect tracks before creating your Spotify playlist
                """)

            # Actual tracks table (hidden initially)
            with gr.Column(visible=False) as step2_content:
                gr.Markdown("""
                ### Review Matched Tracks
                ✅ **Uncheck** any tracks you don't want to include
                🎵 **Click Spotify Match** to preview track with audio
                📺 **Click YouTube Title** to watch the original video
                """)

                tracks_table = gr.Dataframe(
                    headers=["Include", "YouTube Title", "Spotify Match", "Confidence"],
                    datatype=["bool", "str", "str", "str"],
                    col_count=(4, "fixed"),
                    interactive=True,
                    wrap=True,
                    label="Matched Tracks (uncheck any you don't want)"
                )

        # Informational text
        gr.Markdown("""
        💡 **Tip:** Click on any **YouTube Title** to watch the video, or **Spotify Match** to preview the track with album art and audio!
        """)
        # Modal containers (hidden by default)
        with gr.Row(visible=False) as spotify_lyrics_row:
            spotify_preview = gr.HTML(label="Spotify Player")
            lyrics_preview = gr.HTML(label="Lyrics")

        youtube_preview = gr.HTML(label="YouTube Preview")

        gr.Markdown("---")

        # Step 3: Customize Playlist
        gr.Markdown("## Step 3: Customize Your Playlist (Optional)")

        with gr.Row():
            with gr.Column():
                spotify_name_input = gr.Textbox(
                    label="Spotify Playlist Name",
                    placeholder="Leave empty to use YouTube playlist name",
                    lines=1,
                    info="Custom name for your Spotify playlist"
                )

                description_input = gr.Textbox(
                    label="Playlist Description",
                    placeholder="Add a custom description for your playlist...",
                    lines=3,
                    info="Describe your playlist (optional)"
                )

            with gr.Column():
                cover_image_input = gr.Image(
                    label="Playlist Cover Image (Optional) - JPEG/PNG, max 256KB",
                    type="filepath",
                    sources=["upload"],
                    image_mode="RGB",
                    height=190
                )

                make_playlist_public_input = gr.Checkbox(
                    label="🌐 Make this playlist public",
                    value=None,
                    info="Override default setting (leave unchecked to use Settings default)"
                )

        gr.Markdown("---")

        # Step 4: Create Playlist
        gr.Markdown("## Step 4: Create Spotify Playlist")

        create_btn = gr.Button(
            "🚀 Create Spotify Playlist",
            variant="primary",
            size="lg"
        )

        create_status = gr.Markdown()

        playlist_url_output = gr.Textbox(
            label="Spotify Playlist URL",
            placeholder="URL will appear here after creation",
            interactive=False
        )

        gr.Markdown(
            """
            ---

            ### 📝 Notes

            - **Deleted/Private Videos:** Automatically skipped
            - **Match Quality:** ✓ = high confidence, ? = low confidence
            - **Cover Image:** Supports JPEG and PNG (max 256KB, will be resized by Spotify)
            - **API Limits:** YouTube API has daily quota limits
            - **Log Files:** Check timestamped log files for detailed information

            ### 🔒 Privacy

            - Your credentials stay on your machine
            - No data is sent to external servers (except YouTube & Spotify APIs)
            - Spotify authentication is handled securely via OAuth
            """
        )

        # Connect the fetch button
        prepare_event = fetch_btn.click(
            fn=prepare_fetch,
            inputs=[],
            outputs=[fetch_status, tracks_table, state, fetch_stats, step2_placeholder, step2_content, fetch_btn, fetch_again_btn],
            queue=False,
        )

        prepare_event.then(
            fn=fetch_tracks,
            inputs=[youtube_input, include_low_conf],
            outputs=[fetch_status, tracks_table, state, fetch_stats, step2_placeholder, step2_content, fetch_btn, fetch_again_btn],
            show_progress="full",
            trigger_mode="always_last",
        )

        prepare_again_event = fetch_again_btn.click(
            fn=prepare_fetch,
            inputs=[],
            outputs=[fetch_status, tracks_table, state, fetch_stats, step2_placeholder, step2_content, fetch_btn, fetch_again_btn],
            queue=False,
        )

        prepare_again_event.then(
            fn=fetch_tracks,
            inputs=[youtube_input, include_low_conf],
            outputs=[fetch_status, tracks_table, state, fetch_stats, step2_placeholder, step2_content, fetch_btn, fetch_again_btn],
            show_progress="full",
            trigger_mode="always_last",
        )

        # Connect track table cell clicks to show modals
        tracks_table.select(
            on_track_table_click,
            inputs=[state],
            outputs=[spotify_preview, youtube_preview, lyrics_preview, spotify_lyrics_row],
            show_progress=False
        )

        # Connect the create button
        create_btn.click(
            fn=create_playlist,
            inputs=[
                spotify_name_input,
                description_input,
                cover_image_input,
                make_playlist_public_input,
                tracks_table,
                state
            ],
            outputs=[create_status, playlist_url_output],
        )

        # Connect the save settings button
        save_settings_btn.click(
            fn=save_settings_handler,
            inputs=[
                youtube_api_key_input,
                spotify_client_id_input,
                spotify_client_secret_input,
                spotify_redirect_uri_input,
                spotify_scope_input,
                create_public_input,
                max_videos_input,
                embedding_model_input
            ],
            outputs=[settings_status]
        )

        # Connect the model status check button
        check_model_btn.click(
            fn=check_model_status,
            outputs=[model_status_display]
        )

        # Update model status when dropdown changes
        embedding_model_input.change(
            fn=check_model_status_for_selection,
            inputs=[embedding_model_input],
            outputs=[model_status_display]
        )

        # Update model info display when dropdown changes
        embedding_model_input.change(
            fn=get_model_info_markdown,
            inputs=[embedding_model_input],
            outputs=[model_info_display]
        )

        # Download model button connection
        download_model_btn.click(
            fn=download_selected_model_with_progress,
            inputs=[embedding_model_input],
            outputs=[model_status_display]
        )

        # Delete model button connection
        delete_model_btn.click(
            fn=delete_selected_model,
            inputs=[embedding_model_input],
            outputs=[model_status_display]
        ).then(
            fn=check_model_status_for_selection,
            inputs=[embedding_model_input],
            outputs=[model_status_display]
        )

        # Restart button connection
        restart_btn.click(
            fn=restart_application,
            outputs=[restart_status]
        ).then(
            lambda: gr.update(visible=True),
            outputs=[restart_status]
        )

        # Exit button connection
        exit_btn.click(
            fn=exit_application,
            outputs=[exit_status]
        ).then(
            lambda: gr.update(visible=True),
            outputs=[exit_status]
        )

        # Check model status on page load
        app.load(
            fn=check_model_status,
            outputs=[model_status_display]
        )

        # Check config status on page load
        app.load(
            fn=check_config_status,
            outputs=[config_status_display]
        )

        # Populate settings form with saved values
        app.load(
            fn=populate_settings_ui,
            outputs=[
                youtube_api_key_input,
                spotify_client_id_input,
                spotify_client_secret_input,
                spotify_redirect_uri_input,
                spotify_scope_input,
                create_public_input,
                max_videos_input,
                embedding_model_input
            ]
        )

        # Update model info display on page load
        app.load(
            fn=get_model_info_markdown,
            outputs=[model_info_display]
        )

    return app


def main():
    """Launch the Gradio app"""
    print("\n" + "="*60)
    print("YouTube to Spotify Playlist Transfer - Web UI")
    print("="*60 + "\n")

    # Check for saved settings
    try:
        from config_manager import ConfigManager

        config_mgr = ConfigManager()
        if config_mgr.settings_exist():
            settings = config_mgr.load_settings()
            is_valid, errors = config_mgr.validate_settings(settings)
            if is_valid:
                print("✅ Configuration loaded from saved settings")
                print("Your API credentials are ready to use.\n")
            else:
                print("⚠️  WARNING: Saved settings have validation issues:")
                for error in errors:
                    print(f"   - {error}")
                print("Please update settings in the web interface.\n")
        else:
            print("ℹ️  No saved settings found.")
            print("Configure your API keys in the Settings panel (top of the web interface).")
            print("Settings will be saved and used automatically for future transfers.\n")
    except Exception as e:
        print(f"⚠️  Warning: Error checking configuration: {e}")
        print("You can configure settings in the web UI.\n")

    app = create_ui()

    # Launch the app
    app.queue()
    app.launch(
        server_name="0.0.0.0",  # Allow external access
        server_port=7860,
        share=False,  # Set to True to create a public link
        show_error=True,
        quiet=False,
        inbrowser=True  # Automatically open in default browser
    )


if __name__ == "__main__":
    main()
