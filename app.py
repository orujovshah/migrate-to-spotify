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


def fetch_tracks(
    youtube_url: str,
    include_low_confidence: bool,
    progress=gr.Progress()
) -> Tuple[str, List, dict, str]:
    """
    Fetch and match tracks from YouTube playlist.

    Returns:
        Tuple of (status_message, tracks_dataframe, state_dict, statistics)
    """
    try:
        # Validate input
        if not youtube_url or not youtube_url.strip():
            return (
                "❌ Error: Please enter a YouTube playlist URL or ID",
                [],
                {},
                ""
            )

        progress(0.1, desc="Initializing...")

        # Initialize transfer
        try:
            transfer = PlaylistTransfer()
        except Exception as e:
            return (
                f"❌ Error: Failed to initialize. Please check your API credentials in config.py\n\nDetails: {str(e)}",
                [],
                {},
                ""
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
                ""
            )

        if not videos:
            return (
                "❌ Error: No videos found in playlist",
                [],
                {},
                ""
            )

        progress(0.4, desc=f"Found {len(videos)} videos. Matching tracks on Spotify...")

        # Match tracks
        matches = transfer.match_tracks(videos)

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

        return (status_msg, tracks_data, state_data, stats)

    except Exception as e:
        logger.exception("Unexpected error during fetch")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            [],
            {},
            ""
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
        if not state_dict or 'matches' not in state_dict:
            return (
                "❌ Error: Please fetch tracks first before creating playlist",
                ""
            )

        progress(0.1, desc="Initializing...")

        # Initialize transfer
        transfer = PlaylistTransfer()

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

        # Use custom description if provided, otherwise default
        if not description or not description.strip():
            description = f"Transferred from YouTube playlist: {playlist_info['title']}"

        # Create playlist
        try:
            import config
            playlist_id = transfer.spotify.create_playlist(
                name=spotify_name,
                description=description,
                public=config.CREATE_PUBLIC_PLAYLISTS
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

    except Exception as e:
        logger.exception("Unexpected error during playlist creation")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            ""
        )


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
                    - Configure in `config.py`

                    **Features:**
                    - Intelligent title parsing
                    - Multiple search strategies
                    - Confidence scoring
                    - Track preview & selection
                    """
                )

        fetch_status = gr.Markdown(
            value="Ready to fetch tracks. Enter a YouTube playlist URL above."
        )

        fetch_stats = gr.Markdown()

        gr.Markdown("---")

        # Step 2: Review and Select Tracks
        gr.Markdown("## Step 2: Review & Select Tracks")

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
            outputs=[fetch_status, tracks_table, state, fetch_stats],
        )

        # Connect the create button
        create_btn.click(
            fn=create_playlist,
            inputs=[spotify_name_input, description_input, cover_image_input, tracks_table, state],
            outputs=[create_status, playlist_url_output],
        )

    return app


def main():
    """Launch the Gradio app"""
    print("\n" + "="*60)
    print("YouTube to Spotify Playlist Transfer - Web UI")
    print("="*60 + "\n")

    # Check if config is set up
    try:
        import config
        if config.YOUTUBE_API_KEY == 'your_actual_youtube_api_key_here' or \
           config.SPOTIFY_CLIENT_ID == 'your_actual_spotify_client_id_here':
            print("⚠️  WARNING: API credentials not configured!")
            print("Please edit config.py with your actual API keys.")
            print("The app will launch but transfers will fail.\n")
    except ImportError:
        print("❌ Error: config.py not found!")
        print("Please create config.py with your API credentials.\n")

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
