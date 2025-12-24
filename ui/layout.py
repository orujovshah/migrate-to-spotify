import gradio as gr

from ui.constants import FETCH_STATE_INITIAL, INFO_PANEL_TEXT
from ui.fetch import fetch_button_update, fetch_tracks, prepare_fetch
from ui.flows import (
    clear_flash_message,
    check_config_status,
    check_model_status,
    check_model_status_for_selection,
    create_playlist,
    delete_selected_model,
    download_selected_model_with_progress,
    get_model_info_markdown,
    populate_settings_ui,
    prepare_create_playlist,
    restart_application,
    exit_application,
    save_api_settings_handler,
    save_settings_handler,
)
from ui.preview import on_track_table_click
from ui.table_utils import normalize_table_rows, sanitize_selection_column


def create_ui():
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

    /* Style custom progress display to make it highly visible */
    #custom-progress {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        padding: 12px 20px !important;
        border-radius: 8px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4) !important;
        margin: 0 0 !important;
        text-align: center !important;
    }

    /* Force all text inside custom progress to be bright white */
    #custom-progress *,
    #custom-progress p,
    #custom-progress strong,
    #custom-progress em,
    #custom-progress .markdown {
        color: white !important;
        opacity: 1 !important;
    }

    /* Hide ALL Gradio progress elements everywhere, but NOT our custom content */
    .progress-container,
    .progress-level-inner,
    .progress-bar-wrap,
    div[class*="Progress"]:not(#custom-progress) {
        display: none !important;
    }

    /* Only hide Gradio's auto-generated progress bars, not our Markdown content */
    .gradio-container .progress-bar:not(#custom-progress) {
        display: none !important;
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

    /* Hide internal Match ID column used for stable row mapping */
    #tracks-table table th:nth-child(5),
    #tracks-table table td:nth-child(5) {
        display: none;
    }

    /* Fix first column (checkbox) width to prevent it from expanding */
    #tracks-table table th:nth-child(1),
    #tracks-table table td:nth-child(1) {
        width: 80px !important;
        min-width: 80px !important;
        max-width: 80px !important;
        text-align: center !important;
    }

    #tracks-table .tabulator-header .tabulator-col:first-child,
    #tracks-table .tabulator-header .tabulator-col:first-child .tabulator-col-content,
    #tracks-table .tabulator-header .tabulator-col:first-child .tabulator-col-title,
    #tracks-table .tabulator-header .tabulator-col:first-child .tabulator-col-title-holder,
    #tracks-table .tabulator-header .tabulator-col:first-child .select-all-checkbox,
    #tracks-table .tabulator-header .tabulator-col:first-child .select-all-checkbox label {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        padding: 0 !important;
    }

    #tracks-table .tabulator-header .tabulator-col:first-child input[type="checkbox"],
    #tracks-table .tabulator-header .tabulator-col:first-child input[data-testid="checkbox"] {
        margin: 0 auto !important;
    }

    /* Make Confidence column completely non-interactive and fixed width */
    #tracks-table table th:nth-child(4),
    #tracks-table table td:nth-child(4) {
        pointer-events: none;
        user-select: none;
        width: 120px !important;
        min-width: 120px !important;
        max-width: 120px !important;
    }

    /* Hide transient string values ("true"/"false") in selection column */
    #tracks-table table td:nth-child(1) {
        color: transparent !important;
        text-shadow: none !important;
    }

    #notes-divider {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }

    #notes-section {
        margin-top: 0 !important;
    }
    """

    def coerce_table_selection(rows):
        normalized = normalize_table_rows(rows)
        cleaned, changed = sanitize_selection_column(normalized)
        if not changed:
            return gr.update()
        return gr.update(value=cleaned)

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
        fetch_state = gr.State(FETCH_STATE_INITIAL)

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

                    gr.Markdown("#### Advanced Settings")
                    spotify_redirect_uri_input = gr.Textbox(
                        label="Spotify Redirect URI",
                        placeholder="http://127.0.0.1:8080/callback",
                        info="Must match what you set in Spotify app settings"
                    )

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

            spotify_scope_input = gr.Textbox(
                label="Spotify API Scopes",
                placeholder="playlist-modify-public playlist-modify-private ugc-image-upload",
                info="OAuth permissions (keep default unless you know what you're doing)"
            )

            save_settings_btn = gr.Button("💾 Save API Configuration", variant="primary", size="lg")
            api_settings_status = gr.Markdown()

        with gr.Accordion("Semantic Matching Model Settings and Status", open=False):
            gr.Markdown("#### Playlist and Model Settings")
            with gr.Row():
                with gr.Column():
                    create_public_input = gr.Checkbox(
                        label="Create Public Playlists by Default",
                        value=False,
                        info="Uncheck for private playlists"
                    )
                with gr.Column():
                    max_videos_input = gr.Number(
                        label="Maximum Videos to Process",
                        value=None,
                        precision=0,
                        info="Leave empty for unlimited"
                    )

            with gr.Row():
                with gr.Column():
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
                with gr.Column():
                    matching_threshold_input = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.6,
                        step=0.01,
                        label="Matching confidence threshold",
                        info="Higher = stricter matching, fewer results; lower = more aggressive matching."
                    )

            gr.Markdown("#### Semantic Matching Model Status")
            model_info_display = gr.Markdown(get_model_info_markdown())

            with gr.Row():
                check_model_btn = gr.Button("🔍 Check Model Status", size="sm")
                download_model_btn = gr.Button("⬇️ Download Selected Model", size="sm", variant="primary")
                delete_model_btn = gr.Button("🗑️ Delete Selected Model", size="sm", variant="stop")

            model_status_display = gr.Markdown("**Status:** Click button to check")

            save_model_settings_btn = gr.Button("💾 Save Settings", variant="primary", size="lg")
            model_settings_status = gr.Markdown()

        gr.Markdown("---", elem_id="notes-divider")

        # Step 1: Fetch Tracks
        gr.Markdown("## Step 1: Fetch Tracks from YouTube")

        with gr.Row():
            with gr.Column(scale=2):
                youtube_input = gr.Textbox(
                    label="YouTube Playlist URL or ID",
                    placeholder="By URL: https://www.youtube.com/playlist?list=PLxxxxxx\nBy ID: PLxxxxxx",
                    lines=2,
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
                fetch_stats = gr.Markdown(value=INFO_PANEL_TEXT)

        fetch_status = gr.Markdown(
            value="Ready to fetch tracks. Enter a YouTube playlist URL above."
        )

        # Custom progress display - shows detailed progress during fetching
        custom_progress = gr.Markdown(
            value="",
            visible=False,
            elem_id="custom-progress"
        )

        gr.Markdown("---", elem_id="notes-divider")

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
                    headers=["Pick", "YouTube Title", "Spotify Match", "Confidence", "Match ID"],
                    datatype=["bool", "str", "str", "str", "number"],
                    column_count=(5, "fixed"),
                    interactive=True,
                    static_columns=[1, 2, 3, 4],
                    wrap=True,
                    label="Matched Tracks (uncheck any you don't want)",
                    elem_id="tracks-table"
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
            interactive=False,
            visible=False,
        )

        gr.Markdown(
            """### 📝 Notes

- **Deleted/Private Videos:** Automatically skipped
- **Match Quality:** ✓ = high confidence, ? = low confidence
- **Cover Image:** Supports JPEG and PNG (max 256KB, will be resized by Spotify)
- **API Limits:** YouTube API has daily quota limits
- **Log Files:** Check timestamped log files for detailed information

### 🔒 Privacy

- Your credentials stay on your machine
- No data is sent to external servers (except YouTube & Spotify APIs)
- Spotify authentication is handled securely via OAuth
""",
            elem_id="notes-section"
        )

        # Connect the fetch button
        prepare_event = fetch_btn.click(
            fn=prepare_fetch,
            inputs=[fetch_state],
            outputs=[
                fetch_status,
                tracks_table,
                state,
                fetch_stats,
                step2_placeholder,
                step2_content,
                custom_progress,
                fetch_state,
            ],
            queue=False,
        )

        prepare_event.then(
            fn=fetch_tracks,
            inputs=[youtube_input, include_low_conf, fetch_state],
            outputs=[
                fetch_status,
                tracks_table,
                state,
                fetch_stats,
                step2_placeholder,
                step2_content,
                custom_progress,
                fetch_state,
            ],
            show_progress=False,
            trigger_mode="always_last",
        )

        fetch_state.change(
            fn=fetch_button_update,
            inputs=[fetch_state],
            outputs=[fetch_btn],
            show_progress=False,
        )

        tracks_table.change(
            fn=coerce_table_selection,
            inputs=[tracks_table],
            outputs=[tracks_table],
            show_progress=False,
        )

        # Connect track table cell clicks to show modals
        tracks_table.select(
            on_track_table_click,
            inputs=[state, tracks_table],
            outputs=[spotify_preview, youtube_preview, lyrics_preview, spotify_lyrics_row],
            show_progress=False
        )

        # Connect the create button
        create_btn.click(
            fn=prepare_create_playlist,
            inputs=[],
            outputs=[create_status, playlist_url_output],
            queue=False,
        ).then(
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
            fn=clear_flash_message,
            inputs=[],
            outputs=[api_settings_status],
            queue=False,
        ).then(
            fn=save_api_settings_handler,
            inputs=[
                youtube_api_key_input,
                spotify_client_id_input,
                spotify_client_secret_input,
                spotify_redirect_uri_input,
                spotify_scope_input,
                create_public_input,
                max_videos_input,
                embedding_model_input,
                matching_threshold_input
            ],
            outputs=[api_settings_status]
        )

        save_model_settings_btn.click(
            fn=clear_flash_message,
            inputs=[],
            outputs=[model_settings_status],
            queue=False,
        ).then(
            fn=save_settings_handler,
            inputs=[
                youtube_api_key_input,
                spotify_client_id_input,
                spotify_client_secret_input,
                spotify_redirect_uri_input,
                spotify_scope_input,
                create_public_input,
                max_videos_input,
                embedding_model_input,
                matching_threshold_input
            ],
            outputs=[model_settings_status]
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
        def _show_status():
            return gr.update(visible=True)

        restart_btn.click(
            fn=restart_application,
            outputs=[restart_status]
        ).then(
            _show_status,
            outputs=[restart_status]
        )

        # Exit button connection
        exit_btn.click(
            fn=exit_application,
            outputs=[exit_status]
        ).then(
            _show_status,
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
                embedding_model_input,
                matching_threshold_input
            ]
        )

        # Update model info display on page load
        app.load(
            fn=get_model_info_markdown,
            outputs=[model_info_display]
        )

    return app
