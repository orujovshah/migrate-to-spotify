"""
Utility functions for YouTube to Spotify playlist transfer
Includes title cleaning, parsing, and matching algorithms
"""

import re
from typing import Tuple, Optional
from difflib import SequenceMatcher


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
    Verify if Spotify track is a good match for YouTube video.
    
    Args:
        youtube_title: Original YouTube video title
        spotify_track: Spotify track object
        threshold: Minimum similarity score (0.0 to 1.0)
        
    Returns:
        True if match is above threshold
    """
    artist, title = parse_artist_title(youtube_title)
    
    # Get Spotify track details
    spotify_name = spotify_track['name']
    spotify_artists = ' '.join([a['name'] for a in spotify_track['artists']])
    spotify_full = f"{spotify_artists} {spotify_name}"
    
    # Calculate similarity scores
    cleaned_yt = clean_youtube_title(youtube_title)
    
    scores = [
        similarity_score(cleaned_yt, spotify_full),
        similarity_score(cleaned_yt, spotify_name),
    ]
    
    # If we parsed artist and title, check those too
    if artist and title:
        scores.append(similarity_score(title, spotify_name))
        scores.append(similarity_score(artist, spotify_artists))
    
    return max(scores) >= threshold


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
