"""
Utility functions for YouTube to Spotify playlist transfer
Includes title cleaning, parsing, and matching algorithms
"""

import re
from typing import Tuple, Optional, List
from difflib import SequenceMatcher
from sentence_transformers import SentenceTransformer, util
import logging

logger = logging.getLogger(__name__)


class EmbeddingMatcher:
    """
    Singleton class for managing sentence transformer model.
    Loads model once and reuses for all track matching.
    """
    _instance = None
    _model = None
    _model_name = None  # Track which model to load

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_model_name(self, model_name: str):
        """Set the model name to use (call before first access)"""
        self._model_name = model_name

    @property
    def model(self) -> Optional[SentenceTransformer]:
        """Lazy load the model on first access"""
        if self._model is None:
            # Check if string-only mode
            model_name = self._model_name or 'all-mpnet-base-v2'
            if model_name == 'string_only':
                logger.info("Using string matching only (no model download)")
                return None

            try:
                was_downloaded = self.is_model_downloaded(model_name)

                if not was_downloaded:
                    logger.info(f"Downloading sentence transformer model ({model_name})...")
                    logger.info("This is a one-time download. Please wait...")
                else:
                    logger.info(f"Loading sentence transformer model ({model_name})...")

                self._model = SentenceTransformer(model_name)

                if not was_downloaded:
                    logger.info(f"✓ Model {model_name} downloaded and loaded successfully")
                else:
                    logger.info(f"✓ Model {model_name} loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                logger.warning("Falling back to string similarity matching")
                return None
        return self._model

    def encode(self, text: str, normalize: bool = True):
        """Encode text to embedding vector"""
        if self.model is None:
            return None
        try:
            return self.model.encode(text, normalize_embeddings=normalize)
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            return None

    def is_model_downloaded(self, model_name: str) -> bool:
        """
        Check if model is already downloaded to disk cache.

        Args:
            model_name: Name of the sentence transformer model

        Returns:
            True if model exists in cache, False otherwise
        """
        import os
        from pathlib import Path

        # Special case: string_only has no model
        if model_name == 'string_only':
            return True

        # Check Hugging Face cache (primary location for newer versions)
        safe_model_name = model_name.replace('/', '--')
        hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub' / f'models--sentence-transformers--{safe_model_name}'
        if hf_cache.exists() and hf_cache.is_dir():
            return True

        # Check legacy torch cache location (fallback)
        torch_cache = Path.home() / '.cache' / 'torch' / 'sentence_transformers' / f'sentence-transformers_{safe_model_name}'
        if torch_cache.exists() and torch_cache.is_dir():
            return True

        return False

    def delete_model(self, model_name: str) -> tuple:
        """
        Delete a downloaded model from disk cache.

        Args:
            model_name: Name of the sentence transformer model

        Returns:
            Tuple of (success: bool, message: str)
        """
        import shutil
        from pathlib import Path

        # Special case: string_only has no model
        if model_name == 'string_only':
            return (False, "String-only mode has no model to delete")

        # Clear in-memory model if it's currently loaded
        if self._model is not None and self._model_name == model_name:
            self._model = None
            logger.info(f"Cleared in-memory model: {model_name}")

        deleted_locations = []
        safe_model_name = model_name.replace('/', '--')

        # Delete from Hugging Face cache
        hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub' / f'models--sentence-transformers--{safe_model_name}'
        if hf_cache.exists() and hf_cache.is_dir():
            try:
                shutil.rmtree(hf_cache)
                deleted_locations.append("HuggingFace cache")
                logger.info(f"Deleted model from HuggingFace cache: {hf_cache}")
            except Exception as e:
                logger.error(f"Failed to delete from HuggingFace cache: {e}")
                return (False, f"Failed to delete from HuggingFace cache: {str(e)}")

        # Delete from legacy torch cache
        torch_cache = Path.home() / '.cache' / 'torch' / 'sentence_transformers' / f'sentence-transformers_{safe_model_name}'
        if torch_cache.exists() and torch_cache.is_dir():
            try:
                shutil.rmtree(torch_cache)
                deleted_locations.append("Torch cache")
                logger.info(f"Deleted model from Torch cache: {torch_cache}")
            except Exception as e:
                logger.error(f"Failed to delete from Torch cache: {e}")
                return (False, f"Failed to delete from Torch cache: {str(e)}")

        if deleted_locations:
            locations_str = " and ".join(deleted_locations)
            return (True, f"Model deleted successfully from {locations_str}")
        else:
            return (False, "Model not found in cache (already deleted or never downloaded)")

    def get_model_status(self) -> str:
        """
        Get human-readable model status.

        Returns:
            Status string describing model state
        """
        model_name = self._model_name or 'all-mpnet-base-v2'

        if model_name == 'string_only':
            return "String matching only (no model)"

        if self._model is not None:
            return f"✓ {model_name} - Downloaded and loaded"
        elif self.is_model_downloaded(model_name):
            return f"✓ {model_name} - Downloaded (ready to load)"
        else:
            return f"⬇ {model_name} - Not downloaded (will download on first use)"


# Global instance
_embedding_matcher = EmbeddingMatcher()


def format_spotify_track_text(track: dict) -> str:
    """
    Format Spotify track for embedding.

    Args:
        track: Spotify track dictionary

    Returns:
        Formatted string: "Artist - Track Name"
    """
    artists = ' '.join([a['name'] for a in track['artists']])
    return f"{artists} - {track['name']}"


def match_by_embeddings(
    youtube_title: str,
    spotify_tracks: List[dict],
    threshold: float = 0.6
) -> Optional[Tuple[dict, float]]:
    """
    Match YouTube title to best Spotify track using sentence embeddings.

    Flow:
        1. Clean YouTube title with regex
        2. Encode cleaned title to embedding
        3. Encode all Spotify tracks to embeddings
        4. Compute cosine similarity
        5. Return best match above threshold

    Args:
        youtube_title: Original YouTube video title
        spotify_tracks: List of Spotify track dictionaries
        threshold: Minimum cosine similarity (0.0 to 1.0)

    Returns:
        Tuple of (best_track, similarity_score) or None if no match above threshold
    """
    if not spotify_tracks:
        return None

    # Step 1: Rule-based cleanup (regex)
    yt_clean = clean_youtube_title(youtube_title)

    # Step 2: Sentence embedding (YouTube)
    yt_embedding = _embedding_matcher.encode(yt_clean)

    if yt_embedding is None:
        # Fallback to string similarity if model unavailable
        logger.debug("Model unavailable, falling back to string similarity")
        best_track = None
        best_score = 0.0

        for track in spotify_tracks:
            sp_text = format_spotify_track_text(track)
            score = similarity_score(yt_clean, sp_text)
            if score > best_score:
                best_score = score
                best_track = track

        if best_score >= threshold:
            return (best_track, best_score)
        return None

    # Step 3: Sentence embeddings (Spotify tracks)
    spotify_texts = [format_spotify_track_text(track) for track in spotify_tracks]
    sp_embeddings = _embedding_matcher.model.encode(
        spotify_texts,
        normalize_embeddings=True
    )

    # Step 4: Cosine similarity
    similarities = util.cos_sim(yt_embedding, sp_embeddings)[0]

    # Step 5: Best match + threshold
    best_idx = similarities.argmax().item()
    best_score = similarities[best_idx].item()

    if best_score >= threshold:
        best_track = spotify_tracks[best_idx]
        logger.debug(
            f"Best match: {format_spotify_track_text(best_track)} "
            f"(cosine similarity: {best_score:.3f})"
        )
        return (best_track, float(best_score))

    logger.debug(f"No match above threshold {threshold} (best: {best_score:.3f})")
    return None


def clean_youtube_title(title: str) -> str:
    """
    Clean YouTube video title by removing common clutter.
    
    Args:
        title: Raw YouTube video title
        
    Returns:
        Cleaned title suitable for Spotify search
    """
    # Remove content in brackets and parentheses
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    
    # Remove common YouTube keywords (case insensitive)
    keywords = [
        'official video', 'official audio', 'official music video',
        'lyrics', 'lyric video', 'audio', 'video',
        'hd', 'hq', '4k', '1080p', '720p',
        'official', 'original', 'explicit',
        'music video', 'full album', 'full song',
        'ft.', 'feat.', 'featuring'
    ]
    
    for keyword in keywords:
        title = re.sub(rf'\b{keyword}\b', '', title, flags=re.IGNORECASE)
    
    # Remove common symbols and clean up
    title = re.sub(r'[|]', '-', title)
    title = re.sub(r'[•●]', '-', title)
    title = re.sub(r'\s+', ' ', title)  # Multiple spaces to single space
    
    return title.strip()


def parse_artist_title(video_title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to parse artist and song title from YouTube video title.
    Common formats: "Artist - Song", "Artist: Song", "Song by Artist"
    
    Args:
        video_title: YouTube video title
        
    Returns:
        Tuple of (artist, title) or (None, cleaned_title) if parsing fails
    """
    cleaned = clean_youtube_title(video_title)
    
    # Pattern 1: "Artist - Song Title" (most common)
    if ' - ' in cleaned:
        parts = cleaned.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    
    # Pattern 2: "Artist: Song Title"
    if ': ' in cleaned:
        parts = cleaned.split(': ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    
    # Pattern 3: "Song Title by Artist"
    by_match = re.search(r'^(.+?)\s+by\s+(.+)$', cleaned, re.IGNORECASE)
    if by_match:
        return by_match.group(2).strip(), by_match.group(1).strip()
    
    # Pattern 4: "Artist "Song Title""
    quote_match = re.search(r'^(.+?)\s+["""](.+?)["""]', cleaned)
    if quote_match:
        return quote_match.group(1).strip(), quote_match.group(2).strip()
    
    # If no pattern matches, return None for artist
    return None, cleaned


def build_search_queries(video_title: str) -> list:
    """
    Build multiple search query variations to improve match success rate.
    
    Args:
        video_title: YouTube video title
        
    Returns:
        List of search queries ordered by specificity
    """
    queries = []
    
    # Try parsed artist and title
    artist, title = parse_artist_title(video_title)
    if artist and title:
        queries.append(f"{artist} {title}")
        queries.append(f'artist:"{artist}" track:"{title}"')
    
    # Add cleaned full title
    cleaned = clean_youtube_title(video_title)
    if cleaned not in queries:
        queries.append(cleaned)
    
    # Add original title as last resort
    if video_title not in queries:
        queries.append(video_title)
    
    return queries


def similarity_score(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings (0.0 to 1.0).
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def verify_match(youtube_title: str, spotify_track: dict, threshold: float = 0.6) -> bool:
    """
    Verify if Spotify track is a good match for YouTube video using embeddings.

    Flow:
        1. Clean YouTube title with regex
        2. Encode to embeddings (YouTube + Spotify)
        3. Compute cosine similarity
        4. Return True if above threshold

    Args:
        youtube_title: Original YouTube video title
        spotify_track: Spotify track object
        threshold: Minimum cosine similarity (0.0 to 1.0)

    Returns:
        True if match is above threshold
    """
    # Step 1: Rule-based cleanup (regex)
    yt_clean = clean_youtube_title(youtube_title)

    # Step 2 & 3: Sentence embeddings + Cosine similarity
    sp_text = format_spotify_track_text(spotify_track)
    yt_embedding = _embedding_matcher.encode(yt_clean)

    if yt_embedding is None:
        # Fallback to string similarity if model unavailable
        return similarity_score(yt_clean, sp_text) >= threshold

    sp_embedding = _embedding_matcher.encode(sp_text)
    if sp_embedding is None:
        return similarity_score(yt_clean, sp_text) >= threshold

    # Step 4: Cosine similarity + threshold
    similarity = util.cos_sim(yt_embedding, sp_embedding).item()
    return float(similarity) >= threshold


def format_track_info(track: dict) -> str:
    """
    Format Spotify track info for display.
    
    Args:
        track: Spotify track object
        
    Returns:
        Formatted string with artist and title
    """
    artists = ', '.join([a['name'] for a in track['artists']])
    return f"{artists} - {track['name']}"


def extract_playlist_id(url_or_id: str) -> str:
    """
    Extract playlist ID from YouTube URL or return ID if already provided.
    
    Args:
        url_or_id: YouTube playlist URL or ID
        
    Returns:
        Playlist ID
        
    Examples:
        'PLxxxxxx' -> 'PLxxxxxx'
        'https://www.youtube.com/playlist?list=PLxxxxxx' -> 'PLxxxxxx'
    """
    # If it's already just an ID
    if url_or_id.startswith('PL') and 'youtube.com' not in url_or_id:
        return url_or_id
    
    # Extract from URL
    match = re.search(r'[?&]list=([^&]+)', url_or_id)
    if match:
        return match.group(1)
    
    return url_or_id
