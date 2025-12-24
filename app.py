"""
Gradio Web UI for YouTube to Spotify Playlist Transfer
Beautiful browser-based interface for playlist migration
"""

import logging
import os
import sys
from datetime import datetime

from config_manager import ConfigManager
from ui.layout import create_ui

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


def main():
    """Launch the Gradio app."""
    print("\n" + "="*60)
    print("YouTube to Spotify Playlist Transfer - Web UI")
    print("="*60 + "\n")

    # Check for saved settings
    try:
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
    app.queue()
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
