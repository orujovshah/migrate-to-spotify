FETCH_STATE_INITIAL = "initial"
FETCH_STATE_FETCHING = "fetching"
FETCH_STATE_ERROR = "error"
FETCH_STATE_SUCCESS = "success"

INFO_PANEL_TEXT = """
### ℹ️ Information

**Requirements:**
- YouTube API key
- Spotify API credentials
- Configure in **Settings** tab

**Features:**
- Semantic similarity matching
- Track preview & selection
- Playlist customization
"""

MODEL_SIZES = {
    'paraphrase-MiniLM-L3-v2': '~60MB',
    'all-MiniLM-L6-v2': '~80MB',
    'all-MiniLM-L12-v2': '~120MB',
    'all-mpnet-base-v2': '~420MB'
}

MODEL_INFO = {
    'string_only': {
        'name': 'String Matching Only',
        'size': '0MB',
        'description': 'Uses basic text similarity without AI models',
        'benefits': 'Fastest matching, no download required, basic accuracy'
    },
    'paraphrase-MiniLM-L3-v2': {
        'name': 'MiniLM-L3',
        'size': '~60MB',
        'description': 'Lightweight sentence transformer model',
        'benefits': 'Very fast matching with decent accuracy'
    },
    'all-MiniLM-L6-v2': {
        'name': 'MiniLM-L6',
        'size': '~80MB',
        'description': 'Balanced sentence transformer model',
        'benefits': 'Fast matching with good accuracy'
    },
    'all-MiniLM-L12-v2': {
        'name': 'MiniLM-L12',
        'size': '~120MB',
        'description': 'Enhanced sentence transformer model',
        'benefits': 'Balanced performance with very good accuracy'
    },
    'all-mpnet-base-v2': {
        'name': 'MPNet Base',
        'size': '~420MB',
        'description': 'Advanced sentence transformer model',
        'benefits': 'Best matching accuracy (slower due to larger size)'
    }
}
