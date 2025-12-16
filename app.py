"""
Gradio Web UI for YouTube to Spotify Playlist Transfer
Beautiful browser-based interface for playlist migration
"""

import gradio as gr
import logging
import sys
import json
import os
from typing import Tuple, Dict, List, Optional
from datetime import datetime

from transfer import PlaylistTransfer
from utils import extract_playlist_id

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


def validate_cover_image(image_path: str) -> Tuple[bool, str]:
    """
    Validate cover image meets Spotify requirements.

    Args:
        image_path: Path to uploaded image file

    Returns:
        Tuple of (is_valid, error_message)
    """
    import os
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


def fetch_tracks(
    youtube_url: str,
    include_low_confidence: bool,
    progress=gr.Progress()
) -> Tuple[str, List, dict, str, gr.update, gr.update]:
    """
    Fetch and match tracks from YouTube playlist.

    Returns:
        Tuple of (status_message, tracks_dataframe, state_dict, statistics, placeholder_visibility, content_visibility)
    """
    try:
        # Validate input
        if not youtube_url or not youtube_url.strip():
            return (
                "❌ Error: Please enter a YouTube playlist URL or ID",
                [],
                {},
                "",
                gr.update(visible=True),   # Show placeholder
                gr.update(visible=False)   # Hide content
            )

        progress(0.1, desc="Initializing...")

        # Load configuration
        from config_manager import ConfigManager
        config_mgr = ConfigManager()
        settings = config_mgr.get_settings()

        # Check if settings exist
        if settings is None:
            return (
                "❌ Error: API keys not configured.\n\n"
                "Please configure your YouTube and Spotify API keys in the Settings section above before fetching tracks.",
                [],
                {},
                "",
                gr.update(visible=True),   # Show placeholder
                gr.update(visible=False)   # Hide content
            )

        # Initialize transfer with settings
        try:
            transfer = PlaylistTransfer(
                youtube_api_key=settings['youtube_api_key'],
                spotify_client_id=settings['spotify_client_id'],
                spotify_client_secret=settings['spotify_client_secret'],
                spotify_redirect_uri=settings['spotify_redirect_uri'],
                spotify_scope=settings['spotify_scope']
            )
        except Exception as e:
            return (
                f"❌ Error: Failed to initialize with provided settings.\n\n"
                f"Please check your API credentials in Settings.\n\nDetails: {str(e)}",
                [],
                {},
                "",
                gr.update(visible=True),   # Show placeholder
                gr.update(visible=False)   # Hide content
            )

        progress(0.2, desc="Fetching YouTube playlist...")

        # Extract playlist ID
        playlist_id = extract_playlist_id(youtube_url)

        # Fetch YouTube playlist
        try:
            playlist_info, videos = transfer.fetch_youtube_playlist(playlist_id)
        except Exception as e:
            return (
                f"❌ Error: Could not fetch YouTube playlist\n\nDetails: {str(e)}",
                [],
                {},
                "",
                gr.update(visible=True),   # Show placeholder
                gr.update(visible=False)   # Hide content
            )

        if not videos:
            return (
                "❌ Error: No videos found in playlist",
                [],
                {},
                "",
                gr.update(visible=True),   # Show placeholder
                gr.update(visible=False)   # Hide content
            )

        progress(0.4, desc=f"Found {len(videos)} videos. Starting track matching...")

        # Define progress callback for per-track updates
        def update_matching_progress(current, total, title):
            # Calculate progress from 0.4 to 0.9 (50% of the bar)
            base_progress = 0.4
            track_progress = (current / total) * 0.5
            overall_progress = base_progress + track_progress

            # Truncate long titles for display
            short_title = title[:60] + "..." if len(title) > 60 else title
            progress(
                overall_progress,
                desc=f"Matching track {current}/{total}: {short_title}"
            )

        # Match tracks with progress callback
        matches = transfer.match_tracks(videos, progress_callback=update_matching_progress)

        progress(0.95, desc="Finalizing matches...")
        progress(1.0, desc="Complete!")

        # Build dataframe for track selection
        tracks_data = []
        state_data = {
            'playlist_info': playlist_info,
            'matches': [],
            'transfer': None  # Will be set during create
        }

        for i, (video, track, status) in enumerate(matches):
            video_title = video['title']

            if status == 'matched' or (status == 'low_confidence' and include_low_confidence):
                track_info = f"{', '.join([a['name'] for a in track['artists']])} - {track['name']}"
                confidence = "✓ High" if status == 'matched' else "? Low"

                tracks_data.append([
                    True,  # Selected by default
                    video_title,
                    track_info,
                    confidence
                ])

                # Store in state
                state_data['matches'].append({
                    'index': i,
                    'video': video,
                    'track': track,
                    'status': status
                })

        # Calculate statistics
        total = len(matches)
        high_conf = sum(1 for m in matches if m[2] == 'matched')
        low_conf = sum(1 for m in matches if m[2] == 'low_confidence')
        not_found = sum(1 for m in matches if m[2] == 'not_found')

        stats = f"""
### Fetched Tracks

- **Total Videos:** {total}
- **High Confidence Matches:** {high_conf} ({high_conf/total*100:.1f}%)
- **Low Confidence Matches:** {low_conf} ({low_conf/total*100:.1f}%)
- **Not Found:** {not_found} ({not_found/total*100:.1f}%)

**📝 Review the tracks below and uncheck any you don't want to include.**
"""

        status_msg = f"""
## ✅ Tracks Fetched Successfully!

**YouTube Playlist:** {playlist_info['title']}
**Channel:** {playlist_info['channel']}
**Matched Tracks:** {len(tracks_data)}

**Next Steps:**
1. Review the tracks below
2. Uncheck any tracks you don't want
3. (Optional) Upload a cover image
4. (Optional) Edit the playlist description
5. Click "Create Spotify Playlist"
"""

        return (
            status_msg,
            tracks_data,
            state_data,
            stats,
            gr.update(visible=False),  # Hide placeholder
            gr.update(visible=True)    # Show content
        )

    except Exception as e:
        logger.exception("Unexpected error during fetch")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            [],
            {},
            "",
            gr.update(visible=True),   # Show placeholder
            gr.update(visible=False)   # Hide content
        )


def create_playlist(
    spotify_name: str,
    description: str,
    cover_image,
    tracks_dataframe,
    state_dict,
    progress=gr.Progress()
) -> Tuple[str, str]:
    """
    Create Spotify playlist with selected tracks, description, and cover image.

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
        from config_manager import ConfigManager
        config_mgr = ConfigManager()
        settings = config_mgr.get_settings()

        # Check if settings exist
        if settings is None:
            return (
                "❌ Error: API keys not configured. Please configure in Settings first.",
                ""
            )

        # Initialize transfer with settings
        transfer = PlaylistTransfer(
            youtube_api_key=settings['youtube_api_key'],
            spotify_client_id=settings['spotify_client_id'],
            spotify_client_secret=settings['spotify_client_secret'],
            spotify_redirect_uri=settings['spotify_redirect_uri'],
            spotify_scope=settings['spotify_scope']
        )

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
                    # Handle both boolean and string representations
                    if row[0] is True or row[0] == True or row[0] == 'True' or row[0] == 1:
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
            playlist_id = transfer.spotify.create_playlist(
                name=spotify_name,
                description=description,
                public=settings.get('create_public_playlists', False)
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
            return config_mgr.load_settings()
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
        'max_videos': None
    }


def check_model_status() -> str:
    """
    Check if embedding model is downloaded and return status message.

    Returns:
        Markdown formatted status message
    """
    from utils import _embedding_matcher

    try:
        status = _embedding_matcher.get_model_status()

        status_msg = f"""
### 📊 Model Status Check

**Model:** all-mpnet-base-v2 &nbsp;&nbsp;&nbsp; **Size:** ~420MB &nbsp;&nbsp;&nbsp; **Status:** {status}

**What this means:**
- ✓ **Downloaded**: Model is ready to use
- **Not downloaded**: Model will download automatically on first use (one-time, ~2-3 minutes)

The model improves track matching accuracy using semantic similarity instead of simple text matching.
        """

        return status_msg

    except Exception as e:
        return f"""
### ❌ Error Checking Model Status

Could not check model status: {str(e)}

The model will still attempt to download automatically when needed.
        """


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


def save_settings_handler(
    youtube_api_key: str,
    spotify_client_id: str,
    spotify_client_secret: str,
    spotify_redirect_uri: str,
    spotify_scope: str,
    create_public_playlists: bool,
    max_videos: Optional[float]
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
    """

    with gr.Blocks(
        theme=gr.themes.Soft(),
        css=custom_css,
        title="YouTube to Spotify Playlist Transfer"
    ) as app:

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
                        value="http://127.0.0.1:8080/callback",
                        info="Must match what you set in Spotify app settings"
                    )
                    spotify_scope_input = gr.Textbox(
                        label="Spotify API Scopes",
                        value="playlist-modify-public playlist-modify-private ugc-image-upload",
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

            save_settings_btn = gr.Button("💾 Save Settings", variant="primary", size="lg")
            settings_status = gr.Markdown()

        # Model Status Section
        with gr.Accordion("🤖 Semantic Matching Model Status", open=False):
            gr.Markdown("""
### About the Semantic Matching Model

This application uses **all-mpnet-base-v2**, a sentence transformer model for improved track matching accuracy.

**Model Details:**
- **Size:** ~420MB
- **Download:** One-time, automatic on first use
- **Purpose:** Semantic similarity matching between YouTube titles and Spotify tracks
- **Benefits:** Better matching accuracy than simple text similarity

The model will download automatically when you fetch tracks for the first time.
            """)

            check_model_btn = gr.Button("🔍 Check Model Status", size="sm")
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
        with gr.Column(visible=True) as step2_section:
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
                gr.Markdown("Review the matched tracks below and uncheck any you don't want to include:")

                tracks_table = gr.Dataframe(
                    headers=["Include", "YouTube Title", "Spotify Match", "Confidence"],
                    datatype=["bool", "str", "str", "str"],
                    col_count=(4, "fixed"),
                    interactive=True,
                    wrap=True,
                    label="Matched Tracks (uncheck any you don't want)"
                )

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
                    height=250
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
        fetch_btn.click(
            fn=fetch_tracks,
            inputs=[youtube_input, include_low_conf],
            outputs=[fetch_status, tracks_table, state, fetch_stats, step2_placeholder, step2_content],
        )

        # Connect the create button
        create_btn.click(
            fn=create_playlist,
            inputs=[spotify_name_input, description_input, cover_image_input, tracks_table, state],
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
                max_videos_input
            ],
            outputs=[settings_status]
        )

        # Connect the model status check button
        check_model_btn.click(
            fn=check_model_status,
            outputs=[model_status_display]
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
