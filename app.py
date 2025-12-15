"""
Gradio Web UI for YouTube to Spotify Playlist Transfer
Beautiful browser-based interface for playlist migration
"""

import gradio as gr
import logging
import sys
from typing import Tuple, Dict
from datetime import datetime

from transfer import PlaylistTransfer
from utils import extract_playlist_id

# Configure logging for UI
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'transfer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def format_statistics(matches: list) -> str:
    """Format match statistics for display"""
    total = len(matches)
    if total == 0:
        return "No videos processed."

    high_conf = sum(1 for m in matches if m[2] == 'matched')
    low_conf = sum(1 for m in matches if m[2] == 'low_confidence')
    not_found = sum(1 for m in matches if m[2] == 'not_found')

    success_rate = (high_conf / total * 100) if total > 0 else 0

    stats = f"""
### Transfer Statistics

- **Total Videos Processed:** {total}
- **High Confidence Matches:** {high_conf} ({high_conf/total*100:.1f}%)
- **Low Confidence Matches:** {low_conf} ({low_conf/total*100:.1f}%)
- **Not Found:** {not_found} ({not_found/total*100:.1f}%)
- **Success Rate:** {success_rate:.1f}%
"""
    return stats


def format_track_list(matches: list, include_low_confidence: bool) -> str:
    """Format track list for display"""
    if not matches:
        return "No tracks to display."

    output = "### Matched Tracks\n\n"

    for i, (video, track, status) in enumerate(matches, 1):
        video_title = video['title']

        if status == 'matched':
            track_info = f"{', '.join([a['name'] for a in track['artists']])} - {track['name']}"
            output += f"{i}. ✓ **{video_title}**\n   → {track_info}\n\n"
        elif status == 'low_confidence' and include_low_confidence:
            track_info = f"{', '.join([a['name'] for a in track['artists']])} - {track['name']}"
            output += f"{i}. ? **{video_title}** (Low Confidence)\n   → {track_info}\n\n"
        elif status == 'not_found':
            output += f"{i}. ✗ **{video_title}**\n   → Not found on Spotify\n\n"

    return output


def transfer_playlist(
    youtube_url: str,
    spotify_name: str,
    include_low_confidence: bool,
    progress=gr.Progress()
) -> Tuple[str, str, str, str]:
    """
    Main transfer function for Gradio UI

    Returns:
        Tuple of (status_message, statistics, track_list, playlist_url)
    """
    try:
        # Validate input
        if not youtube_url or not youtube_url.strip():
            return (
                "❌ Error: Please enter a YouTube playlist URL or ID",
                "",
                "",
                ""
            )

        progress(0.1, desc="Initializing...")

        # Initialize transfer
        try:
            transfer = PlaylistTransfer()
        except Exception as e:
            return (
                f"❌ Error: Failed to initialize. Please check your API credentials in config.py\n\nDetails: {str(e)}",
                "",
                "",
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
                "",
                "",
                ""
            )

        if not videos:
            return (
                "❌ Error: No videos found in playlist",
                "",
                "",
                ""
            )

        progress(0.4, desc=f"Found {len(videos)} videos. Matching tracks on Spotify...")

        # Match tracks
        matches = transfer.match_tracks(videos)

        progress(0.7, desc="Creating Spotify playlist...")

        # Determine playlist name
        if not spotify_name or not spotify_name.strip():
            spotify_name = f"{playlist_info['title']} (from YouTube)"

        # Create Spotify playlist
        description = f"Transferred from YouTube playlist: {playlist_info['title']}"

        try:
            playlist_id = transfer.create_spotify_playlist(
                playlist_name=spotify_name,
                matches=matches,
                include_low_confidence=include_low_confidence,
                description=description
            )

            playlist_url = transfer.spotify.get_playlist_url(playlist_id)
        except Exception as e:
            return (
                f"❌ Error: Failed to create Spotify playlist\n\nDetails: {str(e)}",
                format_statistics(matches),
                format_track_list(matches, include_low_confidence),
                ""
            )

        progress(1.0, desc="Complete!")

        # Format results
        status_msg = f"""
## ✅ Transfer Complete!

**YouTube Playlist:** {playlist_info['title']}
**Spotify Playlist:** {spotify_name}
**Channel:** {playlist_info['channel']}

[🎵 Open Playlist on Spotify]({playlist_url})
"""

        statistics = format_statistics(matches)
        track_list = format_track_list(matches, include_low_confidence)

        return (status_msg, statistics, track_list, playlist_url)

    except Exception as e:
        logger.exception("Unexpected error during transfer")
        return (
            f"❌ Unexpected Error: {str(e)}\n\nPlease check the log file for details.",
            "",
            "",
            ""
        )


def create_ui():
    """Create and configure Gradio interface"""

    # Custom CSS for better styling
    custom_css = """
    .container {
        max-width: 1200px;
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
            1. Enter your YouTube playlist URL or ID
            2. (Optional) Customize the Spotify playlist name
            3. Choose whether to include uncertain matches
            4. Click "Start Transfer" and wait for the magic!

            ---
            """
        )

        with gr.Row():
            with gr.Column(scale=2):
                youtube_input = gr.Textbox(
                    label="YouTube Playlist URL or ID",
                    placeholder="https://www.youtube.com/playlist?list=PLxxxxxx or PLxxxxxx",
                    lines=1,
                    info="Paste the full URL or just the playlist ID"
                )

                spotify_name_input = gr.Textbox(
                    label="Spotify Playlist Name (Optional)",
                    placeholder="Leave empty to use YouTube playlist name",
                    lines=1,
                    info="Custom name for your Spotify playlist"
                )

                include_low_conf = gr.Checkbox(
                    label="Include Low Confidence Matches",
                    value=True,
                    info="Include tracks that might not be exact matches"
                )

                transfer_btn = gr.Button(
                    "🚀 Start Transfer",
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
                    - Detailed logging

                    **Tips:**
                    - First run will open browser for Spotify auth
                    - Check log files for details
                    - High confidence matches are most accurate
                    """
                )

        gr.Markdown("---")

        # Output section
        with gr.Row():
            with gr.Column():
                status_output = gr.Markdown(
                    label="Status",
                    value="Ready to transfer. Enter a YouTube playlist URL above."
                )

        with gr.Row():
            with gr.Column(scale=1):
                statistics_output = gr.Markdown(label="Statistics")

            with gr.Column(scale=2):
                track_list_output = gr.Markdown(label="Track List")

        with gr.Row():
            playlist_url_output = gr.Textbox(
                label="Spotify Playlist URL",
                placeholder="URL will appear here after transfer",
                interactive=False
            )

        gr.Markdown(
            """
            ---

            ### 📝 Notes

            - **Deleted/Private Videos:** Automatically skipped
            - **Match Quality:** Green check (✓) = high confidence, Question mark (?) = low confidence, Red X (✗) = not found
            - **API Limits:** YouTube API has daily quota limits
            - **Log Files:** Check timestamped log files for detailed information

            ### 🔒 Privacy

            - Your credentials stay on your machine
            - No data is sent to external servers (except YouTube & Spotify APIs)
            - Spotify authentication is handled securely via OAuth
            """
        )

        # Connect the button to the transfer function
        transfer_btn.click(
            fn=transfer_playlist,
            inputs=[youtube_input, spotify_name_input, include_low_conf],
            outputs=[status_output, statistics_output, track_list_output, playlist_url_output],
        )

        # Add examples
        gr.Examples(
            examples=[
                ["PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "My Favorite Songs", True],
                ["https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "", True],
                ["PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "Workout Mix", False],
            ],
            inputs=[youtube_input, spotify_name_input, include_low_conf],
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
        if config.YOUTUBE_API_KEY == 'your_youtube_api_key_here' or \
           config.SPOTIFY_CLIENT_ID == 'your_spotify_client_id_here':
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
        quiet=False
    )


if __name__ == "__main__":
    main()
