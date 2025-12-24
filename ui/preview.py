from typing import Tuple

from io import BytesIO

import gradio as gr
import requests
from colorthief import ColorThief

from ui.table_utils import normalize_table_rows


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


def _show_row() -> gr.update:
    return gr.update(visible=True)


def _hide_row() -> gr.update:
    return gr.update(visible=False)


def update_spotify_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update Spotify preview with content and show row"""
    return content, "", "", _show_row()


def update_youtube_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update YouTube preview with content and hide Spotify/lyrics row"""
    return "", content, "", _hide_row()


def update_lyrics_modal(content: str) -> Tuple[str, str, str, dict]:
    """Update lyrics preview with content"""
    return "", "", content, _show_row()


def on_track_table_click(state_dict: dict, tracks_dataframe, evt: gr.SelectData):
    """
    Handle clicks on the tracks table with a delayed spinner.
    The spinner is sent immediately but remains invisible via CSS for 0.5s.
    """
    # 1. Reset previews immediately on click
    yield "", "", "", _hide_row()

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

    rows = normalize_table_rows(tracks_dataframe)
    if row_idx >= len(rows):
        return
    row = rows[row_idx]
    if len(row) < 5:
        return

    match_id = row[4]
    if match_id is None:
        return

    matches_by_id = state_dict.get('matches_by_id', {})
    try:
        match = matches_by_id[int(match_id)]
    except (KeyError, TypeError, ValueError):
        return

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
        yield "", youtube_spinner, "", _hide_row()

        # Generate content (blocking operation). If this finishes in <0.5s,
        # the spinner above is replaced before it becomes visible.
        video_id = match['video']['video_id']
        youtube_content = generate_youtube_preview(video_id, match['video'])

        yield "", youtube_content, "", _hide_row()

    # --- Column 2: Spotify ---
    elif col_idx == 2:
        if match['status'] != 'matched':
            no_match_content = "<div style='padding: 40px; text-align: center; color: #666;'>This track was not matched to Spotify</div>"
            yield no_match_content, "", "", _show_row()
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
        yield spotify_spinner, "", "", _show_row()

        # Load content
        track_id = match['track']['id']
        spotify_content, lyrics_content = show_track_preview(track_id, match['track'])

        # Yield result
        yield spotify_content, "", lyrics_content, _show_row()

    else:
        yield "", "", "", _hide_row()
