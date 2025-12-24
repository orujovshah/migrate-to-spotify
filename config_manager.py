"""
Configuration manager for persistent settings storage
Handles loading, saving, and validating user configuration from JSON file
"""

import json
import os
import stat
import logging
from typing import Dict, Tuple, List, Optional

logger = logging.getLogger(__name__)

# Valid embedding model options
VALID_MODELS = [
    'string_only',  # No model, use string matching only
    'paraphrase-MiniLM-L3-v2',  # ~60MB, very fast, decent accuracy
    'all-MiniLM-L6-v2',  # ~80MB, fast, good accuracy
    'all-MiniLM-L12-v2',  # ~120MB, balanced, very good accuracy
    'all-mpnet-base-v2'  # ~420MB, slower, best accuracy (default)
]


class ConfigManager:
    """Manages application configuration with persistent JSON storage"""

    DEFAULT_SETTINGS_PATH = '.app_settings.json'

    def __init__(self, settings_path: str = DEFAULT_SETTINGS_PATH):
        """
        Initialize configuration manager

        Args:
            settings_path: Path to JSON settings file
        """
        self.settings_path = settings_path

    def settings_exist(self) -> bool:
        """
        Check if settings file exists

        Returns:
            True if settings file exists
        """
        return os.path.exists(self.settings_path)

    def load_settings(self) -> Dict:
        """
        Load settings from JSON file

        Returns:
            Dictionary with settings

        Raises:
            FileNotFoundError: If settings file doesn't exist
            json.JSONDecodeError: If settings file is invalid JSON
        """
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
            logger.info(f"Loaded settings from {self.settings_path}")
            return settings
        except FileNotFoundError:
            logger.warning(f"Settings file not found: {self.settings_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            raise

    def save_settings(self, settings: Dict) -> bool:
        """
        Save settings to JSON file with validation and secure permissions

        Args:
            settings: Dictionary with configuration values

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate before saving
            is_valid, errors = self.validate_settings(settings)
            if not is_valid:
                logger.error(f"Settings validation failed: {errors}")
                return False

            # Write JSON file
            with open(self.settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            # Set restrictive file permissions (owner read/write only)
            # This only works on Unix-like systems
            if os.name != 'nt':  # Not Windows
                os.chmod(self.settings_path, stat.S_IRUSR | stat.S_IWUSR)

            logger.info(f"Settings saved successfully to {self.settings_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def validate_settings(self, settings: Dict) -> Tuple[bool, List[str]]:
        """
        Validate configuration settings

        Args:
            settings: Dictionary with configuration values

        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []

        # Required fields
        if not settings.get('youtube_api_key', '').strip():
            errors.append("YouTube API Key is required")
        elif settings.get('youtube_api_key') == 'your_actual_youtube_api_key_here':
            errors.append("Please enter a valid YouTube API Key (not the placeholder)")

        if not settings.get('spotify_client_id', '').strip():
            errors.append("Spotify Client ID is required")
        elif settings.get('spotify_client_id') == 'your_actual_spotify_client_id_here':
            errors.append("Please enter a valid Spotify Client ID (not the placeholder)")

        if not settings.get('spotify_client_secret', '').strip():
            errors.append("Spotify Client Secret is required")
        elif settings.get('spotify_client_secret') == 'your_actual_spotify_client_secret_here':
            errors.append("Please enter a valid Spotify Client Secret (not the placeholder)")

        # Optional fields with type validation
        if settings.get('spotify_redirect_uri'):
            redirect = settings['spotify_redirect_uri'].strip()
            if redirect and not redirect.startswith(('http://', 'https://')):
                errors.append("Redirect URI must start with http:// or https://")

        if settings.get('max_videos') is not None:
            max_vids = settings['max_videos']
            if not isinstance(max_vids, (int, float)) or max_vids < 1:
                errors.append("Maximum videos must be a positive integer")

        if 'create_public_playlists' in settings:
            if not isinstance(settings['create_public_playlists'], bool):
                errors.append("Create public playlists must be true or false")

        # Validate embedding model
        if 'embedding_model' in settings:
            if settings['embedding_model'] not in VALID_MODELS:
                errors.append(f"Invalid embedding model. Must be one of: {', '.join(VALID_MODELS)}")

        if 'matching_threshold' in settings:
            threshold = settings['matching_threshold']
            if not isinstance(threshold, (int, float)) or not 0.0 <= float(threshold) <= 1.0:
                errors.append("Matching confidence threshold must be a number between 0.0 and 1.0")

        return (len(errors) == 0, errors)

    def get_settings(self) -> Optional[Dict]:
        """
        Get settings from JSON file only.
        Returns None if file doesn't exist or is invalid.

        Returns:
            Dictionary with settings if file exists and is valid, None otherwise
        """
        if not self.settings_exist():
            logger.info("Settings file does not exist")
            return None

        try:
            settings = self.load_settings()
            # Validate loaded settings
            is_valid, errors = self.validate_settings(settings)
            if is_valid:
                logger.info("Using settings from .app_settings.json")
                return settings
            else:
                logger.warning(f"Settings validation failed: {errors}")
                return None
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return None
