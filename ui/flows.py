import logging
import time
import os
import sys
import threading
from typing import Dict, Tuple

import gradio as gr

from ui.constants import MODEL_INFO, MODEL_SIZES
from ui.services import get_settings, initialize_transfer
from ui.table_utils import normalize_table_rows

logger = logging.getLogger(__name__)


def _success_html(message: str, detail: str = "") -> str:
    nonce = f"{time.time():.6f}"
    if detail:
        detail_html = f"<br><br>{detail}"
    else:
        detail_html = ""
    return f"<div class=\"flash-success\" data-nonce=\"{nonce}\">✅ {message}{detail_html}</div>"


def clear_flash_message() -> str:
    return ""


def _hide_playlist_url():
    return gr.update(value="", visible=False)


def _show_playlist_url(url: str):
    return gr.update(value=url, visible=True)


def get_model_info_markdown(model_name: str = None) -> str:
    """
    Generate dynamic Markdown for model information display.
    """
    # Get model name from settings if not provided
    if model_name is None:
        settings = get_settings()
        if settings and 'embedding_model' in settings:
            model_name = settings['embedding_model']
        else:
            model_name = 'all-mpnet-base-v2'  # Default

    # Get model info from dictionary
    info = MODEL_INFO.get(model_name, MODEL_INFO['all-mpnet-base-v2'])

    # Special case for string-only
    if model_name == 'string_only':
        return f"""
### ✅ String Matching Mode Enabled

This application uses **{info['name']}** (no AI model) for track matching.

**Model Details:**
- **Size:** {info['size']}
- **Download:** Not required
- **Purpose:** Basic text similarity matching
- **Benefits:** {info['benefits']}

⚠️ **Note:** String matching is faster but less accurate than semantic models. Consider using a sentence transformer model for better results.
"""

    # For sentence transformer models
    return f"""
### 🤖 AI Semantic Matching Model

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


def create_playlist(
    spotify_name: str,
    description: str,
    cover_image,
    make_public: bool,
    tracks_dataframe,
    state_dict,
    progress=gr.Progress()
) -> Tuple[str, gr.update]:
    """
    Create Spotify playlist with selected tracks, description, and cover image.
    """
    try:
        # Validate state
        if not state_dict or 'matches' not in state_dict:
            return (
                "❌ Error: Please fetch tracks first before creating playlist",
                _hide_playlist_url(),
            )

        # Validate cover image if provided
        if cover_image is not None:
            is_valid, error_msg = validate_cover_image(cover_image)
            if not is_valid:
                return (
                    f"❌ Cover Image Error: {error_msg}",
                    _hide_playlist_url(),
                )

        progress(0.1, desc="Initializing...")

        # Load configuration
        settings = get_settings()

        # Check if settings exist
        if settings is None:
            return (
                "❌ Error: API keys not configured. Please configure in Settings first.",
                _hide_playlist_url(),
            )

        # Initialize transfer with settings
        transfer, error = initialize_transfer(settings)
        if error:
            return (error, _hide_playlist_url())

        # Get selected tracks from dataframe
        selected_indices = []

        rows = normalize_table_rows(tracks_dataframe)
        if rows:
            # Handle both list and DataFrame types
            try:
                for row in rows:
                    # Check if selected (first column is checkbox)
                    if row and row[0]:  # Truthy check handles True, 'True', 1, etc.
                        match_id = row[4] if len(row) > 4 else None
                        if match_id is not None:
                            selected_indices.append(match_id)

                logger.info(
                    "Processing %s tracks: %s selected, %s unchecked",
                    len(rows),
                    len(selected_indices),
                    len(rows) - len(selected_indices),
                )

            except Exception as e:
                logger.error("Error processing dataframe: %s", e)
                return (
                    f"❌ Error: Failed to process track selection\n\nDetails: {str(e)}",
                    _hide_playlist_url(),
                )

        if not selected_indices:
            return (
                "❌ Error: No tracks selected. Please select at least one track.",
                _hide_playlist_url(),
            )

        # Filter matches to only selected ones
        matches_by_id = state_dict.get('matches_by_id', {})
        selected_matches = []
        for match_id in selected_indices:
            try:
                selected_matches.append(matches_by_id[int(match_id)])
            except (KeyError, TypeError, ValueError):
                logger.warning("Skipping unknown match id: %s", match_id)

        # Build track IDs list
        track_ids = [match['track']['id'] for match in selected_matches]

        logger.info("Creating playlist with %s tracks", len(track_ids))

        progress(0.3, desc="Creating Spotify playlist...")

        # Determine playlist name
        playlist_info = state_dict['playlist_info']
        if not spotify_name or not spotify_name.strip():
            spotify_name = f"{playlist_info['title']} (from YouTube)"

        # Validate playlist name
        if len(spotify_name) > 100:
            return (
                f"❌ Error: Playlist name too long ({len(spotify_name)} characters). Maximum is 100 characters.",
                _hide_playlist_url(),
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
                    _hide_playlist_url(),
                )

        except Exception as e:
            return (
                f"❌ Error: Failed to create playlist\n\nDetails: {str(e)}",
                _hide_playlist_url(),
            )

        progress(0.5, desc="Adding tracks to playlist...")

        # Add tracks to playlist
        try:
            transfer.spotify.add_tracks_to_playlist(playlist_id, track_ids)
        except Exception as e:
            return (
                f"❌ Error: Failed to add tracks to playlist\n\nDetails: {str(e)}",
                _hide_playlist_url(),
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
                logger.warning("Failed to upload cover image: %s", e)
                # Continue anyway, cover image is optional

        progress(1.0, desc="Complete!")

        playlist_url = transfer.spotify.get_playlist_url(playlist_id)

        status_msg = f"""## 🎉 Playlist Created Successfully!

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

        return (status_msg, _show_playlist_url(playlist_url))

    except PermissionError as e:
        logger.exception("Permission error during playlist creation")
        return (
            f"❌ Permission Error: Cannot access files. Please check file permissions.\n\nDetails: {str(e)}",
            _hide_playlist_url(),
        )
    except ConnectionError as e:
        logger.exception("Connection error during playlist creation")
        return (
            f"❌ Network Error: Cannot connect to Spotify. Please check your internet connection.\n\nDetails: {str(e)}",
            _hide_playlist_url(),
        )
    except Exception as e:
        logger.exception("Unexpected error during playlist creation")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            _hide_playlist_url(),
        )


def load_current_settings() -> Dict:
    """
    Load current settings for display in UI.
    """
    from config_manager import ConfigManager

    config_mgr = ConfigManager()
    if config_mgr.settings_exist():
        try:
            settings = config_mgr.load_settings()
            # Ensure defaults for new settings
            if 'embedding_model' not in settings:
                settings['embedding_model'] = 'all-mpnet-base-v2'
            if 'matching_threshold' not in settings:
                settings['matching_threshold'] = 0.6
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
        'embedding_model': 'all-mpnet-base-v2',
        'matching_threshold': 0.6
    }


def populate_settings_ui():
    """
    Load settings from config file and return values for UI population.
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
        settings.get('embedding_model', 'all-mpnet-base-v2'),
        settings.get('matching_threshold', 0.6)
    )


def check_model_status() -> str:
    """
    Check if embedding model is downloaded and return status message.
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

        # Get model size info
        size = MODEL_SIZES.get(selected_model, 'Unknown')
        progress(0.3, desc=f"Downloading {selected_model} ({size})...")
        logger.info("Downloading model: %s", selected_model)

        # Download model
        SentenceTransformer(selected_model)

        logger.info("✓ Model %s downloaded successfully", selected_model)
        return (
            f"✅ **Download Complete!**\n\nModel `{selected_model}` has been downloaded and cached.\n\n"
            "To use it: Save settings and restart the app."
        )

    except Exception as e:
        logger.error("Failed to download model %s: %s", selected_model, e)
        return f"❌ Error downloading model: {str(e)}"


def delete_selected_model(selected_model: str) -> str:
    """
    Delete the selected embedding model from disk cache.
    """
    from utils import _embedding_matcher

    try:
        if selected_model == 'string_only':
            return "ℹ️ **No Model to Delete**\n\nString-only mode doesn't use a model."

        # Check if model is actually downloaded
        if not _embedding_matcher.is_model_downloaded(selected_model):
            return f"ℹ️ **Model Not Downloaded**\n\nModel `{selected_model}` is not in your cache."

        # Delete the model
        success, message = _embedding_matcher.delete_model(selected_model)
        if success:
            logger.info("Successfully deleted model: %s", selected_model)
            return f"✅ **Model Deleted**\n\n{message}\n\nModel `{selected_model}` has been removed from your cache."

        logger.warning("Failed to delete model %s: %s", selected_model, message)
        return f"❌ Failed to delete model: {message}"

    except Exception as e:
        logger.error("Error deleting model %s: %s", selected_model, e)
        return f"❌ Error deleting model: {str(e)}"


def check_config_status() -> str:
    """
    Check if API configuration is saved and return status message.
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
    """
    import time

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
    """
    import time

    def shutdown():
        time.sleep(1.5)
        os._exit(0)

    # Use a separate thread to allow response to be sent
    threading.Thread(target=shutdown, daemon=True).start()

    return """
<div style="max-width: 100%; padding: 10px; text-align: center; word-wrap: break-word;">
    <h3 style="font-size: 1em; margin: 0 0 8px 0;">✅ App Closed</h3>
    <p style="font-size: 0.85em; margin: 0 0 5px 0;">You can close this browser tab now.</p>
</div>
"""


def save_settings_handler(
    youtube_api_key: str,
    spotify_client_id: str,
    spotify_client_secret: str,
    spotify_redirect_uri: str,
    spotify_scope: str,
    create_public_playlists: bool,
    max_videos: int,
    embedding_model: str,
    matching_threshold: float
) -> str:
    """
    Save settings from UI inputs to config file and validate.
    """
    from config_manager import ConfigManager

    config_mgr = ConfigManager()

    # Create settings dict
    settings = {
        'youtube_api_key': youtube_api_key,
        'spotify_client_id': spotify_client_id,
        'spotify_client_secret': spotify_client_secret,
        'spotify_redirect_uri': spotify_redirect_uri,
        'spotify_scope': spotify_scope,
        'create_public_playlists': create_public_playlists,
        'max_videos': max_videos,
        'embedding_model': embedding_model,
        'matching_threshold': matching_threshold
    }

    try:
        is_valid, errors = config_mgr.validate_settings(settings)

        if not is_valid:
            error_msg = "❌ **Configuration Errors:**\n\n"
            for error in errors:
                error_msg += f"- {error}\n"
            return error_msg

        # Save settings
        config_mgr.save_settings(settings)

        return _success_html("Settings saved successfully!", "Restart the app to apply model changes.")
    except Exception as e:
        logger.error("Error saving settings: %s", e)
        return f"❌ **Error saving settings:** {str(e)}"


def save_api_settings_handler(
    youtube_api_key: str,
    spotify_client_id: str,
    spotify_client_secret: str,
    spotify_redirect_uri: str,
    spotify_scope: str,
    create_public_playlists: bool,
    max_videos: int,
    embedding_model: str,
    matching_threshold: float,
) -> None:
    """
    Save API settings and return a lightweight success message for the API accordion.
    """
    result = save_settings_handler(
        youtube_api_key,
        spotify_client_id,
        spotify_client_secret,
        spotify_redirect_uri,
        spotify_scope,
        create_public_playlists,
        max_videos,
        embedding_model,
        matching_threshold,
    )
    if isinstance(result, str) and result.startswith("❌"):
        return result
    return _success_html("API Configuration saved successfully!")


def prepare_create_playlist() -> Tuple[str, gr.update]:
    """
    Provide immediate feedback while the playlist is being created.
    """
    return ("⏳ **Creating playlist...**", _hide_playlist_url())
