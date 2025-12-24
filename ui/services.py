from typing import Optional, Tuple

from transfer import PlaylistTransfer


def get_settings() -> Optional[dict]:
    """
    Get application settings from config file.

    Returns:
        Settings dictionary or None if not configured
    """
    from config_manager import ConfigManager

    config_mgr = ConfigManager()
    return config_mgr.get_settings()


def initialize_transfer(settings: dict) -> Tuple[Optional[PlaylistTransfer], Optional[str]]:
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
            "❌ Error: Failed to initialize with provided settings.\n\n"
            "Please check your API credentials in Settings.\n\n"
            f"Details: {str(e)}"
        )
        return (None, error_msg)
