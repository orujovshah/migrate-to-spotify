"""
Configuration file for YouTube to Spotify Playlist Transfer
Fill in your API credentials here
"""

# YouTube Data API v3 Configuration
# Get from: https://console.cloud.google.com/
YOUTUBE_API_KEY = 'your_actual_youtube_api_key_here'

# Spotify API Configuration
# Get from: https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = 'your_actual_spotify_client_id_here'
SPOTIFY_CLIENT_SECRET = 'your_actual_spotify_client_secret_here'
SPOTIFY_REDIRECT_URI = 'redirect_uri_specified_when_creating_spotify_api_key'

# Spotify API Scopes
SPOTIFY_SCOPE = 'playlist-modify-public playlist-modify-private ugc-image-upload'

# Optional: Set to True to make playlists public by default
CREATE_PUBLIC_PLAYLISTS = False

# Optional: Maximum number of videos to process (None for no limit)
MAX_VIDEOS = None
