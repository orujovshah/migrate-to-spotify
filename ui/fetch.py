import threading
from typing import Dict, Generator, List, Optional, Tuple

import gradio as gr

from ui.constants import (
    FETCH_STATE_ERROR,
    FETCH_STATE_FETCHING,
    FETCH_STATE_INITIAL,
    FETCH_STATE_SUCCESS,
    INFO_PANEL_TEXT,
)
from ui.fetch_payloads import fetch_error_payload, fetch_payload, fetch_reset_payload
from ui.services import get_settings, initialize_transfer
from utils import extract_playlist_id

# Track per-session fetch cancellation signals.
_FETCH_CANCEL_EVENTS: Dict[str, threading.Event] = {}
_FETCH_CANCEL_LOCK = threading.Lock()
_FETCH_RUN_IDS: Dict[str, int] = {}


def _get_session_id(request: Optional[gr.Request]) -> Optional[str]:
    if request is None:
        return None
    return getattr(request, "session_hash", None)


def _cancel_current_fetch(request: Optional[gr.Request]) -> None:
    session_id = _get_session_id(request)
    if session_id is None:
        return
    with _FETCH_CANCEL_LOCK:
        cancel_event = _FETCH_CANCEL_EVENTS.get(session_id)
        if cancel_event is not None:
            cancel_event.set()


def _start_fetch_run(request: Optional[gr.Request]) -> Tuple[threading.Event, int]:
    session_id = _get_session_id(request)
    cancel_event = threading.Event()
    with _FETCH_CANCEL_LOCK:
        previous_event = _FETCH_CANCEL_EVENTS.get(session_id)
        if previous_event is not None:
            previous_event.set()
        _FETCH_CANCEL_EVENTS[session_id] = cancel_event
        _FETCH_RUN_IDS[session_id] = _FETCH_RUN_IDS.get(session_id, 0) + 1
        run_id = _FETCH_RUN_IDS[session_id]
    return cancel_event, run_id


def _is_latest_fetch_run(request: Optional[gr.Request], run_id: int) -> bool:
    session_id = _get_session_id(request)
    if session_id is None:
        return True
    with _FETCH_CANCEL_LOCK:
        return _FETCH_RUN_IDS.get(session_id, 0) == run_id


def fetch_button_update(state: str) -> gr.update:
    if state == FETCH_STATE_FETCHING:
        return gr.update(visible=True, value="⏳ Fetching... Click to restart", interactive=True)
    if state == FETCH_STATE_ERROR:
        return gr.update(visible=True, value="❌ Error Encountered... Click to Try Again", interactive=True)
    if state == FETCH_STATE_SUCCESS:
        return gr.update(visible=True, value="🔄 Fetch Again", interactive=True)
    return gr.update(visible=True, value="🔍 Fetch Tracks", interactive=True)


def prepare_fetch(
    fetch_state: str,
    request: gr.Request = None,
) -> Tuple[str, List, dict, str, gr.update, gr.update, gr.update, str]:
    """
    Cancel any in-flight fetch and immediately reset the UI.
    Runs outside the queue so cancellation can happen immediately.
    """
    _cancel_current_fetch(request)
    return fetch_reset_payload(INFO_PANEL_TEXT, "🔄 **Starting fetch...**", FETCH_STATE_FETCHING)


def fetch_tracks(
    youtube_url: str,
    include_low_confidence: bool,
    fetch_state: str,
    progress=gr.Progress(),
    request: gr.Request = None,
) -> Generator[Tuple[str, List, dict, str, gr.update, gr.update, gr.update, str], None, None]:
    """
    Fetch and match tracks from YouTube playlist.
    includes progress bar and standard table structure.
    """
    try:
        current_state = fetch_state or FETCH_STATE_INITIAL
        cancel_event, run_id = _start_fetch_run(request)

        def is_cancelled() -> bool:
            return cancel_event.is_set()

        def is_stale() -> bool:
            return not _is_latest_fetch_run(request, run_id)

        def cancelled_payload():
            return fetch_reset_payload(INFO_PANEL_TEXT, "⏳ **Restarting fetch...**", current_state)

        # 1. Immediate Reset: Clear UI instantly on click
        if is_stale():
            return
        yield fetch_reset_payload(INFO_PANEL_TEXT, "🔄 **Initializing...**", FETCH_STATE_FETCHING)

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        # Validate input
        if not youtube_url or not youtube_url.strip():
            if is_stale():
                return
            yield fetch_error_payload(INFO_PANEL_TEXT, "❌ **Error:** Please enter a YouTube playlist URL or ID")
            return

        progress(0.1, desc="Initializing...")

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        # Load settings
        settings = get_settings()
        if settings is None:
            if is_stale():
                return
            yield fetch_error_payload(INFO_PANEL_TEXT, "❌ **Error:** API keys not configured. Please check Settings.")
            return
        match_threshold = float(settings.get('matching_threshold', 0.6))

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        # Initialize transfer
        transfer, error = initialize_transfer(settings)
        if error:
            if is_stale():
                return
            yield fetch_error_payload(INFO_PANEL_TEXT, f"❌ **Error:** {error}")
            return

        if is_stale():
            return
        yield fetch_payload(
            custom_progress=gr.update(value="⏳ **Fetching playlist...**", visible=True),
            fetch_state=FETCH_STATE_FETCHING,
        )

        progress(0.2, desc="Fetching YouTube playlist...")

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        # Get Playlist
        playlist_id = extract_playlist_id(youtube_url)
        try:
            playlist_info, videos = transfer.fetch_youtube_playlist(
                playlist_id,
                max_videos=settings.get('max_videos')
            )
        except Exception as e:
            if is_stale():
                return
            yield fetch_error_payload(
                INFO_PANEL_TEXT,
                f"❌ **Error:** Could not fetch YouTube playlist - {str(e)}",
            )
            return

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        if not videos:
            if is_stale():
                return
            yield fetch_error_payload(INFO_PANEL_TEXT, "❌ **Error:** No videos found in playlist")
            return

        progress(0.4, desc=f"Found {len(videos)} videos. Starting matching...")

        # Match tracks manually with per-track progress updates
        from utils import build_search_queries, verify_match

        matches = []
        total_videos = len(videos)

        for i, video in enumerate(videos, 1):
            if is_cancelled():
                if is_stale():
                    return
                yield cancelled_payload()
                return

            video_title = video['title']
            short_title = video_title[:50] + "..." if len(video_title) > 50 else video_title

            # Update custom progress for THIS track
            percentage = int((i / total_videos) * 100)
            if is_stale():
                return
            yield fetch_reset_payload(
                INFO_PANEL_TEXT,
                f"🎵 **Matching Track {i}/{total_videos}** ({percentage}%) - {short_title}",
                FETCH_STATE_FETCHING,
            )

            # Build search queries
            queries = build_search_queries(video_title)

            # Search on Spotify
            spotify_track = transfer.spotify.search_track_best_match(
                queries=queries,
                youtube_title=video_title,
                match_threshold=match_threshold
            )

            if spotify_track:
                # Verify match quality
                if verify_match(video_title, spotify_track, threshold=match_threshold):
                    matches.append((video, spotify_track, 'matched'))
                else:
                    matches.append((video, spotify_track, 'low_confidence'))
            else:
                matches.append((video, None, 'not_found'))

        if is_cancelled():
            if is_stale():
                return
            yield cancelled_payload()
            return

        progress(0.95, desc="Finalizing matches...")

        # 2. Build Table Data (Restored Structure)
        # Structure: [Checkbox, YouTube Title, Spotify Match, Confidence]
        tracks_data = []
        state_data = {
            'playlist_info': playlist_info,
            'matches': [],
            'matches_by_id': {}
        }

        for i, (video, track, status) in enumerate(matches):
            if status == 'matched' or (status == 'low_confidence' and include_low_confidence):
                # Column 1: YouTube Title
                video_title = video['title']

                # Column 2: Spotify Track Info
                track_info = f"{', '.join([a['name'] for a in track['artists']])} - {track['name']}"

                # Column 3: Confidence Label
                confidence = "✓ High" if status == 'matched' else "? Low"

                # Row Structure: [Selected, Col 1, Col 2, Col 3, Match ID]
                tracks_data.append([
                    True,  # Checkbox
                    video_title,  # YouTube Title
                    track_info,  # Spotify Match
                    confidence,  # Confidence
                    i  # Match ID for stable mapping
                ])

                # Save full objects to state for the click handler
                match_entry = {
                    'index': i,
                    'video': video,
                    'track': track,
                    'status': status
                }
                state_data['matches'].append(match_entry)
                state_data['matches_by_id'][i] = match_entry

        # Calculate Stats
        total = len(matches)
        high = sum(1 for m in matches if m[2] == 'matched')
        low = sum(1 for m in matches if m[2] == 'low_confidence')
        missing = sum(1 for m in matches if m[2] == 'not_found')

        stats_text = f"""
## ✅ Success!
**Playlist:** {playlist_info['title']}
**Matched:** {len(tracks_data)} tracks

### Fetched Tracks
- **Total:** {total}
- **High Confidence:** {high}
- **Low Confidence:** {low}
- **Not Found:** {missing}
"""

        status_msg = ""

        progress(1.0, desc="Done!")

        # Final Yield
        if is_stale():
            return
        yield fetch_payload(
            fetch_status=status_msg,
            tracks_table=tracks_data,
            state_dict=state_data,
            fetch_stats=stats_text,
            step2_placeholder=gr.update(visible=False),
            step2_content=gr.update(visible=True),
            custom_progress=gr.update(value="✅ **Matching complete!**", visible=True),
            fetch_state=FETCH_STATE_SUCCESS,
        )

    except Exception as e:
        if _is_latest_fetch_run(request, run_id):
            yield fetch_error_payload(INFO_PANEL_TEXT, f"❌ **Unexpected Error:** {str(e)}")
        return
