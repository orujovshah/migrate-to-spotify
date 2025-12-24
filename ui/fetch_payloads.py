from typing import Tuple

import gradio as gr

from ui.constants import FETCH_STATE_ERROR

_FETCH_KEEP = object()


def fetch_payload(
    fetch_status=_FETCH_KEEP,
    tracks_table=_FETCH_KEEP,
    state_dict=_FETCH_KEEP,
    fetch_stats=_FETCH_KEEP,
    step2_placeholder=_FETCH_KEEP,
    step2_content=_FETCH_KEEP,
    custom_progress=_FETCH_KEEP,
    fetch_state: str = "",
) -> Tuple[
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    str,
]:
    def normalize(value):
        return gr.update() if value is _FETCH_KEEP else value

    return (
        normalize(fetch_status),
        normalize(tracks_table),
        normalize(state_dict),
        normalize(fetch_stats),
        normalize(step2_placeholder),
        normalize(step2_content),
        normalize(custom_progress),
        fetch_state,
    )


def fetch_reset_payload(
    info_panel_text: str,
    progress_text: str,
    fetch_state: str,
) -> Tuple[
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    str,
]:
    return fetch_payload(
        fetch_status="",
        tracks_table=[],
        state_dict={},
        fetch_stats=info_panel_text,
        step2_placeholder=gr.update(visible=True),
        step2_content=gr.update(visible=False),
        custom_progress=gr.update(value=progress_text, visible=True),
        fetch_state=fetch_state,
    )


def fetch_error_payload(
    info_panel_text: str,
    message: str,
) -> Tuple[
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    gr.update,
    str,
]:
    return fetch_reset_payload(info_panel_text, message, FETCH_STATE_ERROR)
