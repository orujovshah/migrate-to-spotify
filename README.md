# YouTube to Spotify Playlist Transfer

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitLab](https://img.shields.io/badge/gitlab-migrate--to--spotify-orange.svg)](https://gitlab.com/orujovshahmurad/migrate-to-spotify)

Automatically transfer your YouTube playlists to Spotify with intelligent track matching. Features both a command-line interface and a beautiful web UI.

**🔗 Repository:** [gitlab.com/orujovshahmurad/migrate-to-spotify](https://gitlab.com/orujovshahmurad/migrate-to-spotify)

## Features

- ✅ **Web UI Interface** - Beautiful browser-based interface with 4-step workflow
- ✅ **Track Preview & Selection** - Review and remove tracks before creating playlist
- ✅ **Custom Cover Images** - Upload your own playlist cover art
- ✅ **Custom Descriptions** - Write personalized playlist descriptions
- ✅ **CLI Interface** - Interactive command-line tool
- ✅ Batch transfer entire YouTube playlists to Spotify
- ✅ Intelligent title parsing and matching
- ✅ Multiple search query strategies for better matches
- ✅ Confidence scoring for match quality
- ✅ Detailed logging of transfer process
- ✅ Handles deleted/private videos gracefully
- ✅ Rate limit handling
- ✅ OAuth authentication for Spotify
- ✅ **Comprehensive test suite** - 77 tests covering all functionality
- ✅ **Python 3.13 compatible**

## Prerequisites

- Python 3.7 or higher (Python 3.13 supported)
- A Google Cloud account (for YouTube API)
- A Spotify Developer account

## Quick Start

### 1. Clone the Repository

```bash
git clone https://gitlab.com/orujovshahmurad/migrate-to-spotify.git
cd migrate-to-spotify
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** For Python 3.13 users, all required compatibility packages will be installed automatically.

### 3. Get YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy your API key

### 4. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in app details:
   - App name: "YouTube to Spotify Transfer" (or any name)
   - App description: "Transfer playlists from YouTube"
   - Redirect URI: `http://127.0.0.1:8080/callback` (or you can use custom redirect URI)
5. Click "Create"
6. You'll see your **Client ID** and **Client Secret** on the app page

### 5. Configure API Keys

Edit `config.py` and add your credentials:

```python
# YouTube Data API v3 Configuration
YOUTUBE_API_KEY = 'your_actual_youtube_api_key_here'

# Spotify API Configuration
SPOTIFY_CLIENT_ID = 'your_actual_spotify_client_id_here'
SPOTIFY_CLIENT_SECRET = 'your_actual_spotify_client_secret_here'
SPOTIFY_REDIRECT_URI = 'redirect_uri_specified_when_creating_spotify_api_key'
```

**Important**: Keep `config.py` private and never commit it to version control!

## Usage

### Web UI (Recommended)

Launch the beautiful web interface:

```bash
python app.py
```

The app will automatically open in your default browser at `http://localhost:7860`

**Workflow:**
1. **Step 1**: Enter YouTube playlist URL → Click "Fetch Tracks"
2. **Step 2**: Review matched tracks in the interactive table → Uncheck any you don't want
3. **Step 3**: (Optional) Upload cover image, customize name and description
4. **Step 4**: Click "Create Spotify Playlist"

**Features:**
- **Two-step workflow**: Fetch tracks first, then review before creating playlist
- **Track preview & selection**: Review all matched tracks and uncheck any you don't want
- **Custom cover images**: Upload your own playlist cover (JPEG/PNG, max 256KB)
- **Custom descriptions**: Write a personalized description for your playlist
- **Real-time progress tracking**: See progress for both fetching and creating steps
- **Statistics dashboard**: View match quality and confidence levels
- **Visual track table**: Interactive table with confidence indicators
- **Direct Spotify links**: Click to open your created playlist
- **Error handling and validation**: Clear error messages and input validation

### Command Line Interface

Run the interactive CLI:

```bash
python transfer.py
```

You'll be prompted to:
1. Enter YouTube playlist URL or ID
2. (Optional) Enter custom Spotify playlist name
3. Choose whether to include low-confidence matches

### Programmatic Usage

Use the transfer functionality in your own Python scripts:

```python
from transfer import PlaylistTransfer

# Initialize
transfer = PlaylistTransfer()

# Transfer playlist
playlist_url = transfer.transfer(
    youtube_playlist_url='PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    spotify_playlist_name='My Custom Playlist Name',  # Optional
    include_low_confidence=True  # Include uncertain matches
)

print(f"Created playlist: {playlist_url}")
```

## First-Time Spotify Authentication

When you run the script for the first time:
1. A browser window will open
2. Log in to Spotify and authorize the app
3. You'll be redirected to `http://localhost:8080`
4. Copy the entire URL from the browser
5. Paste it back into the terminal

After first authentication, credentials are cached in `.spotify_cache`.

## YouTube Playlist Formats

You can provide the YouTube playlist in any of these formats:

```
Full URL:
https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Playlist ID only:
PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Configuration Options

Edit `config.py` to customize behavior:

```python
# Make playlists public by default
CREATE_PUBLIC_PLAYLISTS = True  # Default: False

# Limit number of videos to process
MAX_VIDEOS = 50  # Default: None (process all)
```

## How Track Matching Works

The script uses multiple strategies to find the best match:

1. **Title Parsing**: Extracts artist and song title from YouTube video titles
   - Formats: "Artist - Song", "Artist: Song", "Song by Artist"

2. **Title Cleaning**: Removes common YouTube clutter
   - Keywords: "official video", "lyrics", "HD", etc.
   - Brackets and parentheses content

3. **Multiple Search Queries**: Tries several query variations
   - Parsed artist + title
   - Spotify advanced syntax (artist:X track:Y)
   - Cleaned full title
   - Original title

4. **Confidence Scoring**: Verifies match quality
   - Compares similarity between YouTube and Spotify titles
   - Flags low-confidence matches for review

## Understanding Output

### Match Statuses

- **✓ High confidence**: Strong match based on title similarity
- **? Low confidence**: Possible match but uncertain (review recommended)
- **✗ Not found**: No match found on Spotify

### Log Files

Each transfer creates a single timestamped log file in the `logs/` directory:
- Location: `logs/transfer_YYYYMMDD_HHMMSS.log`
- Contains detailed information about each track match
- One log file per operation (whether using Web UI or CLI)
- The logs directory is automatically created when the app runs

## Testing

The project includes a comprehensive test suite with 77 tests covering all functionality.

### Run All Tests

```bash
python test_all_functionality.py
```

### Test Coverage

- **28 tests** - Utility functions (title parsing, cleaning, matching)
- **7 tests** - YouTube API handler
- **14 tests** - Spotify API handler (including cover image upload)
- **6 tests** - Playlist transfer logic
- **7 tests** - Edge cases
- **15 tests** - Web UI and CLI functionality (two-step workflow, track selection, cover images, logs directory creation)

All tests use mocking, so they run without requiring API credentials and don't consume API quotas.

## File Structure

```
.
├── config.py                  # API credentials configuration template
├── transfer.py                # Main CLI script
├── app.py                     # Web UI application (Gradio)
├── youtube_handler.py         # YouTube API wrapper
├── spotify_handler.py         # Spotify API wrapper
├── utils.py                   # Helper functions
├── test_all_functionality.py  # Comprehensive test suite (77 tests)
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
├── LICENSE                    # MIT License
└── README.md                  # This file
```

## Python 3.13 Compatibility

This project is fully compatible with Python 3.13. The required dependencies include:

- `audioop-lts` - Provides compatibility for the removed `audioop` module
- `gradio>=6.1.0` - Latest version with Python 3.13 support

All dependencies are automatically installed via `requirements.txt`.

## API Rate Limits

### YouTube Data API v3
- **Quota**: 10,000 units/day
- **Cost per request**: 1-3 units per video
- **Limit**: ~3,000-10,000 videos per day

### Spotify Web API
- **Rate Limit**: ~180 requests per minute
- **The script includes delays to stay within limits**

## Troubleshooting

### "Invalid API Key" Error

- Verify your YouTube API key in `config.py`
- Make sure YouTube Data API v3 is enabled in Google Cloud Console
- Check that there are no extra spaces or quotes

### "Authentication Failed" Error (Spotify)

- Verify your Spotify Client ID and Secret
- Make sure Redirect URI is set to `http://localhost:8080`
- Delete `.spotify_cache` and try again

### "Quota Exceeded" Error (YouTube)

YouTube API has a daily quota of 10,000 units:
- Each playlist items request costs ~1 unit per video
- If you hit the limit, wait until the next day
- Consider setting `MAX_VIDEOS` to limit requests

### "Not Found" for Many Tracks

If many tracks aren't found:
- The playlist might contain non-music content (podcasts, talks, etc.)
- Some tracks may not be available in your Spotify region
- Video titles might be poorly formatted

### Web UI Not Opening

The app automatically opens in your default browser when launched. If it doesn't open:
1. Look for the URL in the console output (usually `http://localhost:7860`)
2. Manually copy and paste it into your browser
3. Check if a browser window opened in the background

### Python 3.13 Import Errors

If you encounter import errors with Python 3.13:
```bash
pip install audioop-lts
pip install --upgrade gradio
```

## Privacy & Security

- **Never share** your API credentials
- **Never commit** filled `config.py` to version control
- The repository includes a `.gitignore` file that protects:
  - `config_personal.py` - Your personal credentials file
  - `.spotify_cache` - Spotify authentication cache
  - `logs/` - Transfer log files directory
- All processing happens locally on your machine
- Your API credentials never leave your computer
- Spotify OAuth is handled securely via official libraries

## Limitations

- YouTube videos that don't correspond to music tracks won't match
- Spotify may not have all songs (regional restrictions, unavailable tracks)
- Title parsing depends on consistent YouTube title formatting
- Deleted or private YouTube videos are skipped

## Advanced Usage

### Custom Match Verification

Adjust the similarity threshold in `utils.py`:

```python
def verify_match(youtube_title: str, spotify_track: dict, threshold: float = 0.6):
    # Lower threshold = more lenient matching
    # Higher threshold = stricter matching
```

### Batch Transfer Multiple Playlists

```python
from transfer import PlaylistTransfer

playlists = [
    'PLxxxxxxxxxxxxxx',
    'PLyyyyyyyyyyyyyy',
    'PLzzzzzzzzzzzzzz'
]

transfer = PlaylistTransfer()
for playlist_id in playlists:
    transfer.transfer(youtube_playlist_url=playlist_id)
```

### Share Web UI Publicly

To create a public link accessible from anywhere, edit `app.py`:

```python
app.launch(
    share=True,  # Change to True
    ...
)
```

This creates a temporary public URL that you can share with others.

## Contributing

Contributions are welcome! Feel free to:

- 🐛 [Report bugs](https://gitlab.com/orujovshahmurad/migrate-to-spotify/-/issues) via GitLab Issues
- 💡 [Suggest features](https://gitlab.com/orujovshahmurad/migrate-to-spotify/-/issues) via GitLab Issues
- 🔧 Submit merge requests for:
  - Improved title parsing algorithms
  - Better match verification
  - Additional features
  - Bug fixes
  - Documentation improvements

### Development Setup

```bash
# Clone the repository
git clone https://gitlab.com/orujovshahmurad/migrate-to-spotify.git
cd migrate-to-spotify

# Install dependencies
pip install -r requirements.txt

# Run tests
python test_all_functionality.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Make sure to comply with:
- [YouTube API Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [Spotify Developer Terms](https://developer.spotify.com/terms)

## Built With

- [google-api-python-client](https://github.com/googleapis/google-api-python-client) - YouTube API
- [spotipy](https://github.com/plamere/spotipy) - Spotify API
- [gradio](https://github.com/gradio-app/gradio) - Web UI framework

## Support

If you encounter issues:
1. Check the log file for detailed error messages
2. Verify your API credentials are correct
3. Ensure all dependencies are installed
4. Run the test suite to verify functionality
5. Check API quotas haven't been exceeded

---

Made with ❤️ for music lovers who want to migrate their playlists seamlessly.
