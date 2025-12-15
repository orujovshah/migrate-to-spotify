"""
Main script to transfer YouTube playlist to Spotify
"""

import logging
import sys
from typing import List, Dict, Tuple
from datetime import datetime

# Import our modules
from youtube_handler import YouTubeHandler
from spotify_handler import SpotifyHandler
from utils import (
    build_search_queries,
    verify_match,
    format_track_info,
    extract_playlist_id
)
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'transfer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PlaylistTransfer:
    """Main class to handle YouTube to Spotify playlist transfer"""
    
    def __init__(self):
        """Initialize YouTube and Spotify handlers"""
        logger.info("Initializing playlist transfer...")
        
        # Initialize YouTube handler
        try:
            self.youtube = YouTubeHandler(config.YOUTUBE_API_KEY)
            logger.info("✓ YouTube API initialized")
        except Exception as e:
            logger.error(f"✗ Failed to initialize YouTube API: {e}")
            raise
        
        # Initialize Spotify handler
        try:
            self.spotify = SpotifyHandler(
                client_id=config.SPOTIFY_CLIENT_ID,
                client_secret=config.SPOTIFY_CLIENT_SECRET,
                redirect_uri=config.SPOTIFY_REDIRECT_URI,
                scope=config.SPOTIFY_SCOPE
            )
            user = self.spotify.get_current_user()
            logger.info(f"✓ Spotify API initialized (User: {user['display_name']})")
        except Exception as e:
            logger.error(f"✗ Failed to initialize Spotify API: {e}")
            raise
    
    def fetch_youtube_playlist(self, playlist_id: str) -> Tuple[Dict, List[Dict]]:
        """
        Fetch YouTube playlist information and videos.
        
        Args:
            playlist_id: YouTube playlist ID
            
        Returns:
            Tuple of (playlist_info, videos_list)
        """
        logger.info(f"\n{'='*60}")
        logger.info("STEP 1: Fetching YouTube playlist...")
        logger.info(f"{'='*60}")
        
        # Get playlist info
        playlist_info = self.youtube.get_playlist_info(playlist_id)
        if not playlist_info:
            raise ValueError(f"Could not find playlist with ID: {playlist_id}")
        
        logger.info(f"Playlist: {playlist_info['title']}")
        logger.info(f"Channel: {playlist_info['channel']}")
        
        # Get videos
        videos = self.youtube.get_playlist_videos(
            playlist_id,
            max_results=config.MAX_VIDEOS
        )
        
        logger.info(f"✓ Found {len(videos)} videos")
        return playlist_info, videos
    
    def match_tracks(self, videos: List[Dict]) -> List[Tuple[Dict, Dict, str]]:
        """
        Match YouTube videos to Spotify tracks.
        
        Args:
            videos: List of YouTube video dictionaries
            
        Returns:
            List of tuples (youtube_video, spotify_track, status)
        """
        logger.info(f"\n{'='*60}")
        logger.info("STEP 2: Matching tracks on Spotify...")
        logger.info(f"{'='*60}")
        
        matches = []
        
        for i, video in enumerate(videos, 1):
            video_title = video['title']
            logger.info(f"\n[{i}/{len(videos)}] YouTube: {video_title}")
            
            # Build search queries
            queries = build_search_queries(video_title)
            
            # Search on Spotify
            spotify_track = self.spotify.search_track_best_match(queries)
            
            if spotify_track:
                # Verify match quality
                if verify_match(video_title, spotify_track):
                    matches.append((video, spotify_track, 'matched'))
                    logger.info(f"         ✓ Spotify: {format_track_info(spotify_track)}")
                else:
                    matches.append((video, spotify_track, 'low_confidence'))
                    logger.warning(f"         ? Spotify: {format_track_info(spotify_track)} (low confidence)")
            else:
                matches.append((video, None, 'not_found'))
                logger.warning(f"         ✗ Not found on Spotify")
        
        # Summary
        matched = sum(1 for m in matches if m[2] == 'matched')
        low_conf = sum(1 for m in matches if m[2] == 'low_confidence')
        not_found = sum(1 for m in matches if m[2] == 'not_found')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"MATCHING SUMMARY:")
        logger.info(f"  ✓ High confidence matches: {matched}")
        logger.info(f"  ? Low confidence matches:  {low_conf}")
        logger.info(f"  ✗ Not found:              {not_found}")
        logger.info(f"  Total:                    {len(matches)}")
        logger.info(f"{'='*60}")
        
        return matches
    
    def create_spotify_playlist(
        self,
        playlist_name: str,
        matches: List[Tuple[Dict, Dict, str]],
        include_low_confidence: bool = True,
        description: str = ''
    ) -> str:
        """
        Create Spotify playlist and add matched tracks.
        
        Args:
            playlist_name: Name for the new playlist
            matches: List of match tuples from match_tracks()
            include_low_confidence: Whether to include low confidence matches
            description: Playlist description
            
        Returns:
            Spotify playlist ID
        """
        logger.info(f"\n{'='*60}")
        logger.info("STEP 3: Creating Spotify playlist...")
        logger.info(f"{'='*60}")
        
        # Filter matches based on confidence
        if include_low_confidence:
            valid_matches = [m for m in matches if m[1] is not None]
        else:
            valid_matches = [m for m in matches if m[2] == 'matched']
        
        track_ids = [match[1]['id'] for match in valid_matches]
        
        logger.info(f"Creating playlist: {playlist_name}")
        logger.info(f"Adding {len(track_ids)} tracks...")
        
        # Create playlist
        playlist_id = self.spotify.create_playlist(
            name=playlist_name,
            description=description,
            public=config.CREATE_PUBLIC_PLAYLISTS
        )
        
        if not playlist_id:
            raise Exception("Failed to create Spotify playlist")
        
        # Add tracks
        if track_ids:
            success = self.spotify.add_tracks_to_playlist(playlist_id, track_ids)
            if not success:
                logger.warning("Some tracks may not have been added")
        
        playlist_url = self.spotify.get_playlist_url(playlist_id)
        logger.info(f"\n✓ Playlist created successfully!")
        logger.info(f"  URL: {playlist_url}")
        
        return playlist_id
    
    def transfer(
        self,
        youtube_playlist_url: str,
        spotify_playlist_name: str = None,
        include_low_confidence: bool = True
    ) -> str:
        """
        Complete transfer from YouTube to Spotify.
        
        Args:
            youtube_playlist_url: YouTube playlist URL or ID
            spotify_playlist_name: Name for Spotify playlist (uses YouTube name if None)
            include_low_confidence: Include low confidence matches
            
        Returns:
            Spotify playlist URL
        """
        try:
            # Extract playlist ID
            playlist_id = extract_playlist_id(youtube_playlist_url)
            logger.info(f"Processing YouTube playlist: {playlist_id}")
            
            # Fetch YouTube playlist
            playlist_info, videos = self.fetch_youtube_playlist(playlist_id)
            
            if not videos:
                logger.error("No videos found in playlist")
                return None
            
            # Match tracks
            matches = self.match_tracks(videos)
            
            # Create Spotify playlist
            if spotify_playlist_name is None:
                spotify_playlist_name = f"{playlist_info['title']} (from YouTube)"
            
            description = f"Transferred from YouTube playlist: {playlist_info['title']}"
            
            playlist_id = self.create_spotify_playlist(
                playlist_name=spotify_playlist_name,
                matches=matches,
                include_low_confidence=include_low_confidence,
                description=description
            )
            
            playlist_url = self.spotify.get_playlist_url(playlist_id)
            
            logger.info(f"\n{'='*60}")
            logger.info("TRANSFER COMPLETE!")
            logger.info(f"{'='*60}")
            logger.info(f"Spotify Playlist: {playlist_url}")
            
            return playlist_url
            
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            raise


def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("YouTube to Spotify Playlist Transfer")
    print("="*60 + "\n")
    
    # Get YouTube playlist URL from user
    youtube_url = input("Enter YouTube playlist URL or ID: ").strip()
    
    if not youtube_url:
        print("Error: No URL provided")
        return
    
    # Optional: custom Spotify playlist name
    custom_name = input("Enter Spotify playlist name (leave empty to use YouTube name): ").strip()
    spotify_name = custom_name if custom_name else None
    
    # Ask about low confidence matches
    include_low = input("Include low confidence matches? (y/n, default: y): ").strip().lower()
    include_low_confidence = include_low != 'n'
    
    print("\n" + "="*60)
    print("Starting transfer...")
    print("="*60 + "\n")
    
    # Perform transfer
    try:
        transfer = PlaylistTransfer()
        playlist_url = transfer.transfer(
            youtube_playlist_url=youtube_url,
            spotify_playlist_name=spotify_name,
            include_low_confidence=include_low_confidence
        )
        
        print(f"\n✓ Success! Your playlist is ready:")
        print(f"  {playlist_url}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.exception("Transfer failed with exception:")
        sys.exit(1)


if __name__ == '__main__':
    main()
