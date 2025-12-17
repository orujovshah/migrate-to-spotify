# YouTube to Spotify Playlist Transfer

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitLab](https://img.shields.io/badge/gitlab-migrate--to--spotify-orange.svg)](https://gitlab.com/orujovshahmurad/migrate-to-spotify)

Automatically transfer your YouTube playlists to Spotify with **AI-powered semantic matching**. Uses sentence transformers for intelligent track matching with higher accuracy than traditional text-based methods. Features both a command-line interface and a beautiful web UI.

**🔗 Repository:** [gitlab.com/orujovshahmurad/migrate-to-spotify](https://gitlab.com/orujovshahmurad/migrate-to-spotify)

## Features

- ✅ **Semantic Similarity Matching** - AI-powered track matching with 5 model options (from 60MB to 420MB)
- ✅ **Multiple Model Support** - Choose from 5 semantic matching models or string-only mode
- ✅ **Web UI Interface** - Beautiful browser-based interface with 4-step workflow
- ✅ **Settings UI** - Configure API keys and model selection directly in the web interface
- ✅ **Track Preview & Selection** - Review and remove tracks before creating playlist
- ✅ **Per-Playlist Visibility Control** - Set public/private per playlist, overriding global defaults
- ✅ **Custom Cover Images** - Upload your own playlist cover art (JPEG, 4KB-256KB)
- ✅ **Custom Descriptions** - Write personalized playlist descriptions
- ✅ **Graceful Exit** - Exit the application cleanly from the UI
- ✅ **CLI Interface** - Interactive command-line tool
- ✅ **Batch Processing** - Handle playlists with 100+ tracks efficiently
- ✅ Intelligent title parsing and matching
- ✅ Multiple search query strategies for better matches
- ✅ Confidence scoring for match quality
- ✅ Detailed logging of transfer process
- ✅ Handles deleted/private videos gracefully
- ✅ Rate limit handling with automatic delays
- ✅ OAuth authentication for Spotify
- ✅ **Python 3.13 compatible**
- ✅ **Comprehensive test suite** - 156+ tests covering all functionality

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

You'll configure your API keys through the web interface on first launch. The settings are saved to `.app_settings.json` and persist across sessions.

**For Web UI:**
1. Launch the app: `python app.py`
2. Click "⚙️ Settings" in the interface
3. Enter your API credentials (YouTube API Key, Spotify Client ID, Client Secret, and Redirect URI)
4. Click "Save Settings"
5. Settings are automatically loaded for future sessions

**For CLI:**
1. Launch the web UI first: `python app.py`
2. Configure settings through the Settings panel
3. Once configured, you can use the CLI: `python transfer.py`

**Important**: Keep `.app_settings.json` private and never commit it to version control!

## Usage

### Web UI (Recommended)

Launch the beautiful web interface:

```bash
python app.py
```

The app will automatically open in your default browser at `http://localhost:7860`

**First-Time Setup:**
1. Click "⚙️ Settings" to configure your API keys
2. Enter your YouTube and Spotify credentials
3. (Optional) Select your preferred semantic matching model (5 options: 60MB to 420MB, or string-only mode)
4. Click "Save Settings"
5. (Optional) Check "🤖 Semantic Matching Model Status" to verify model download status

**Workflow:**
1. **Step 1**: Enter YouTube playlist URL → Click "Fetch Tracks"
   - First use: Semantic matching model downloads automatically (60MB-420MB depending on model selected, one-time)
   - Subsequent uses: Model loads from cache instantly
2. **Step 2** (appears after fetching): Review matched tracks in the interactive table → Uncheck any you don't want
3. **Step 3**: (Optional) Upload cover image, customize name and description
   - (Optional) Check "🌐 Make this playlist public" to override the default visibility setting
4. **Step 4**: Click "Create Spotify Playlist"
5. **Exit**: Click "❌ Exit App" button to gracefully close the application

### Command Line Interface

Run the interactive CLI:

```bash
python transfer.py
```

**Note:** API keys must be configured first using the Web UI Settings panel. If settings aren't configured, you'll see an error message with instructions.

You'll be prompted to:
1. Enter YouTube playlist URL or ID
2. (Optional) Enter custom Spotify playlist name
3. Choose whether to include low-confidence matches

### Programmatic Usage

Use the transfer functionality in your own Python scripts:

```python
from transfer import PlaylistTransfer

# Initialize with explicit credentials
transfer = PlaylistTransfer(
    youtube_api_key='your_youtube_api_key',
    spotify_client_id='your_spotify_client_id',
    spotify_client_secret='your_spotify_client_secret',
    spotify_redirect_uri='http://127.0.0.1:8080/callback',
    spotify_scope='playlist-modify-private playlist-modify-public ugc-image-upload'
)

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

<details>
<summary><h2>📊 How Track Matching Works</h2></summary>

The script uses an advanced multi-stage matching pipeline for optimal accuracy:

### Stage 1: Title Preprocessing

1. **Title Parsing**: Extracts artist and song title from YouTube video titles
   - Formats: "Artist - Song", "Artist: Song", "Song by Artist", "Artist \"Song\""

2. **Title Cleaning**: Removes common YouTube clutter
   - Keywords: "official video", "lyrics", "HD", "4K", "audio", etc.
   - Brackets and parentheses content
   - Special symbols and normalization

### Stage 2: Spotify Search

3. **Multiple Search Queries**: Tries several query variations
   - Parsed artist + title
   - Spotify advanced syntax (artist:X track:Y)
   - Cleaned full title
   - Original title
   - Collects top 10-20 candidates from all queries

### Stage 3: AI-Powered Matching

4. **Semantic Similarity Matching**: Uses sentence transformers for intelligent matching
   - **Model Options**: 5 models available (paraphrase-MiniLM-L3-v2, all-MiniLM-L6-v2, all-MiniLM-L12-v2, all-mpnet-base-v2) or string-only mode
   - **Default Model**: all-mpnet-base-v2 (highest accuracy, ~420MB)
   - **Lightweight Models**: MiniLM variants available (60MB-120MB) for faster downloads and matching
   - **Method**: Encodes YouTube title and Spotify tracks into embeddings
   - **Comparison**: Computes cosine similarity between embeddings
   - **Threshold**: Matches above 0.6 similarity score
   - **Fallback**: Uses string similarity if model unavailable
   - **Auto-download**: Model downloads automatically on first use (size depends on selected model)

5. **Confidence Scoring**: Verifies match quality
   - Semantic similarity score (0.0 to 1.0)
   - High confidence: ≥0.6 similarity
   - Low confidence: Below threshold but possible match
   - Flags uncertain matches for user review

</details>

<details>
<summary><h2>📋 Understanding Output</h2></summary>

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

</details>

<details>
<summary><h2>📁 File Structure</h2></summary>

```
.
├── app.py                     # Web UI application (Gradio)
├── transfer.py                # Main CLI script
├── config_manager.py          # Configuration management and persistence
├── youtube_handler.py         # YouTube API wrapper
├── spotify_handler.py         # Spotify API wrapper
├── utils.py                   # Helper functions
├── requirements.txt           # Python dependencies
├── .app_settings.json         # User settings (created on first save, gitignored)
├── .gitignore                 # Git ignore rules
├── LICENSE                    # MIT License
└── README.md                  # This file
```

</details>

<details>
<summary><h2>🐍 Python 3.13 Compatibility</h2></summary>

This project is fully compatible with Python 3.13. The required dependencies include:

- `audioop-lts` - Provides compatibility for the removed `audioop` module
- `gradio>=6.1.0` - Latest version with Python 3.13 support
- `sentence-transformers` - AI model for semantic similarity matching
- `torch` - Required by sentence-transformers (CPU version)

All dependencies are automatically installed via `requirements.txt`.

**First-Time Model Download:**
- The semantic matching model downloads automatically on first use
- Model size depends on your selection (60MB-420MB, or no download for string-only mode)
- One-time download, cached locally for future use
- Download happens in the background when you fetch tracks
- **Model Options:**
  - `paraphrase-MiniLM-L3-v2` - Lightweight (~60MB), fast matching with decent accuracy
  - `all-MiniLM-L6-v2` - Balanced (~80MB), fast matching with good accuracy
  - `all-MiniLM-L12-v2` - Enhanced (~120MB), balanced performance with very good accuracy
  - `all-mpnet-base-v2` - Advanced (~420MB, default), best matching accuracy
  - `string_only` - No download required, basic text similarity matching

</details>

<details>
<summary><h2>⚡ API Rate Limits</h2></summary>

### YouTube Data API v3
- **Quota**: 10,000 units/day
- **Cost per request**: 1-3 units per video
- **Limit**: ~3,000-10,000 videos per day

### Spotify Web API
- **Rate Limit**: ~180 requests per minute
- **The script includes delays to stay within limits**

</details>

<details>
<summary><h2>🔧 Troubleshooting</h2></summary>

### "Invalid API Key" Error

- Verify your YouTube API key in the Settings UI
- Make sure YouTube Data API v3 is enabled in Google Cloud Console
- Check that there are no extra spaces in the Settings panel
- If needed, delete `.app_settings.json` and reconfigure through the Settings UI

### "Authentication Failed" Error (Spotify)

- Verify your Spotify Client ID and Secret in the Settings UI
- Make sure Redirect URI is set to `http://127.0.0.1:8080/callback` in both the Settings panel and Spotify Developer Dashboard
- Delete `.spotify_cache` and try again

### "Quota Exceeded" Error (YouTube)

YouTube API has a daily quota of 10,000 units:
- Each playlist items request costs ~1 unit per video
- If you hit the limit, wait until the next day

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

### Semantic Matching Model Issues

**Model Download Stuck:**
- The model downloads automatically on first track fetch (~420MB)
- Download time depends on your internet connection (2-5 minutes typical)
- Progress is logged in the console and UI
- Model is cached in `~/.cache/huggingface/` or `~/.cache/torch/`

**Model Won't Download:**
- Check internet connection
- Ensure you have ~500MB free disk space
- Try manually downloading:
  ```bash
  python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"
  ```

**Fallback Mode:**
- If the model fails to load, the app automatically falls back to string similarity
- Matching will still work but with slightly lower accuracy
- Check logs for "Falling back to string similarity matching"

</details>

<details>
<summary><h2>🔒 Privacy & Security</h2></summary>

- **Never share** your API credentials
- **Never commit** `.app_settings.json` to version control
- The repository includes a `.gitignore` file that protects:
  - `.app_settings.json` - Your API credentials and settings
  - `.spotify_cache` - Spotify authentication cache
  - `logs/` - Transfer log files directory
- All processing happens locally on your machine
- Your API credentials never leave your computer
- Settings are stored locally in `.app_settings.json` with restrictive file permissions
- Spotify OAuth is handled securely via official libraries

</details>

<details>
<summary><h2>⚠️ Limitations</h2></summary>

- YouTube videos that don't correspond to music tracks won't match
- Spotify may not have all songs (regional restrictions, unavailable tracks)
- Title parsing depends on consistent YouTube title formatting
- Deleted or private YouTube videos are skipped
- First-time use requires model download (60MB-420MB depending on selected model, one-time)
- Model requires RAM when loaded (60MB-500MB depending on selected model, CPU version)
- String-only mode has no download but lower accuracy than semantic models

</details>

<details>
<summary><h2>🔬 Advanced Usage</h2></summary>

### Custom Match Verification

Adjust the semantic similarity threshold in `utils.py`:

```python
def verify_match(youtube_title: str, spotify_track: dict, threshold: float = 0.6):
    # Lower threshold (e.g., 0.5) = more lenient matching (more matches, lower quality)
    # Higher threshold (e.g., 0.7) = stricter matching (fewer matches, higher quality)
    # Uses cosine similarity between embeddings (0.0 to 1.0)
```

Or adjust the threshold in `match_by_embeddings()`:

```python
def match_by_embeddings(youtube_title: str, spotify_tracks: List[dict], threshold: float = 0.6):
    # Default: 0.6 (balanced accuracy and recall)
    # Recommended range: 0.5-0.7
```

### Batch Transfer Multiple Playlists

```python
from transfer import PlaylistTransfer

# Initialize with credentials (from config_manager or manual input)
transfer = PlaylistTransfer(
    youtube_api_key='your_youtube_api_key',
    spotify_client_id='your_spotify_client_id',
    spotify_client_secret='your_spotify_client_secret',
    spotify_redirect_uri='http://127.0.0.1:8080/callback',
    spotify_scope='playlist-modify-private playlist-modify-public ugc-image-upload'
)

playlists = [
    'PLxxxxxxxxxxxxxx',
    'PLyyyyyyyyyyyyyy',
    'PLzzzzzzzzzzzzzz'
]

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

</details>

<details>
<summary><h2>🤝 Contributing</h2></summary>

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
```

</details>

<details>
<summary><h2>📄 License</h2></summary>

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Make sure to comply with:
- [YouTube API Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service)
- [Spotify Developer Terms](https://developer.spotify.com/terms)

</details>

<details>
<summary><h2>🛠️ Built With</h2></summary>

- [google-api-python-client](https://github.com/googleapis/google-api-python-client) - YouTube API
- [spotipy](https://github.com/plamere/spotipy) - Spotify API
- [gradio](https://github.com/gradio-app/gradio) - Web UI framework
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers) - Semantic similarity matching
- [PyTorch](https://pytorch.org/) - Deep learning framework for embeddings

</details>

<details>
<summary><h2>💬 Support</h2></summary>

If you encounter issues:
1. Check the log file for detailed error messages
2. Verify your API credentials are correct
3. Ensure all dependencies are installed
4. Check API quotas haven't been exceeded

</details>

---

Made with ❤️ for music lovers who want to migrate their playlists seamlessly.
