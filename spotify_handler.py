"""
Spotify API handler for searching tracks and creating playlists
"""

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from typing import List, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)


class SpotifyHandler:
    """Handler for Spotify Web API operations"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, scope: str):
        """
        Initialize Spotify API client with OAuth authentication.
        
        Args:
            client_id: Spotify application client ID
            client_secret: Spotify application client secret
            redirect_uri: OAuth redirect URI
            scope: Spotify API scopes
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        
        # Initialize Spotify client with OAuth
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                cache_path='.spotify_cache'
            )
        )
        
        logger.info("Spotify authentication successful")
    
    def get_current_user(self) -> Dict:
        """
        Get current user's Spotify profile.
        
        Returns:
            User profile dictionary
        """
        return self.sp.current_user()
    
    def search_track(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for tracks on Spotify.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of track dictionaries
        """
        try:
            results = self.sp.search(q=query, type='track', limit=limit)
            return results['tracks']['items']
        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []
    
    def search_track_best_match(
        self,
        queries: List[str],
        youtube_title: str = ""
    ) -> Optional[Dict]:
        """
        Search Spotify with multiple queries and return best match using embeddings.

        Flow:
            1. Collect top 10-20 results from all queries
            2. Remove duplicates by track ID
            3. Use match_by_embeddings() to find best match via cosine similarity
            4. Return best match above threshold

        Args:
            queries: List of search query strings to try
            youtube_title: Original YouTube video title (for embedding matching)

        Returns:
            Best matching track dictionary or None if no match above threshold
        """
        from utils import match_by_embeddings

        all_candidates = []
        seen_ids = set()

        # Spotify Search (Top 10-20)
        # Collect candidates from all query variations
        for query in queries:
            tracks = self.search_track(query, limit=10)  # Get top 10 results per query

            # Add unique tracks only (dedup by Spotify track ID)
            for track in tracks:
                if track['id'] not in seen_ids:
                    seen_ids.add(track['id'])
                    all_candidates.append(track)

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        if not all_candidates:
            logger.debug("No Spotify results found for any query")
            return None

        # If no title provided, return first result (backward compatibility)
        if not youtube_title:
            logger.debug("No YouTube title provided, returning first result")
            return all_candidates[0]

        # Sentence Embedding + Cosine Similarity + Best Match + Threshold
        # Delegate to utils.match_by_embeddings()
        result = match_by_embeddings(
            youtube_title=youtube_title,
            spotify_tracks=all_candidates,
            threshold=0.6
        )

        if result:
            best_track, similarity_score = result
            return best_track

        logger.debug("No match above threshold")
        return None
    
    def get_track_info(self, track_id: str) -> Optional[Dict]:
        """
        Get detailed track information.
        
        Args:
            track_id: Spotify track ID
            
        Returns:
            Track dictionary or None
        """
        try:
            return self.sp.track(track_id)
        except Exception as e:
            logger.error(f"Error fetching track {track_id}: {e}")
            return None
    
    def create_playlist(self, name: str, description: str = '', public: bool = False) -> Optional[str]:
        """
        Create a new Spotify playlist.
        
        Args:
            name: Playlist name
            description: Playlist description
            public: Whether playlist should be public
            
        Returns:
            Playlist ID or None if error
        """
        try:
            user_id = self.sp.current_user()['id']
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            logger.info(f"Created playlist: {name} (ID: {playlist['id']})")
            return playlist['id']
        except Exception as e:
            logger.error(f"Error creating playlist: {e}")
            return None
    
    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """
        Add tracks to an existing playlist.
        Spotify API allows max 100 tracks per request.
        
        Args:
            playlist_id: Spotify playlist ID
            track_ids: List of Spotify track IDs
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add tracks in batches of 100
            batch_size = 100
            for i in range(0, len(track_ids), batch_size):
                batch = track_ids[i:i + batch_size]
                self.sp.playlist_add_items(playlist_id, batch)
                logger.debug(f"Added batch of {len(batch)} tracks")
                time.sleep(0.2)  # Small delay between batches
            
            logger.info(f"Successfully added {len(track_ids)} tracks to playlist")
            return True
            
        except Exception as e:
            logger.error(f"Error adding tracks to playlist: {e}")
            return False
    
    def get_playlist_url(self, playlist_id: str) -> str:
        """
        Generate Spotify web URL for playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            
        Returns:
            Full Spotify URL
        """
        return f"https://open.spotify.com/playlist/{playlist_id}"
    
    def playlist_exists(self, name: str) -> Optional[str]:
        """
        Check if a playlist with given name exists for current user.

        Args:
            name: Playlist name to search for

        Returns:
            Playlist ID if exists, None otherwise
        """
        try:
            user_id = self.sp.current_user()['id']
            playlists = self.sp.user_playlists(user_id)

            for playlist in playlists['items']:
                if playlist['name'].lower() == name.lower():
                    return playlist['id']

            return None
        except Exception as e:
            logger.error(f"Error checking playlist existence: {e}")
            return None

    def upload_playlist_cover(self, playlist_id: str, image_path: str) -> bool:
        """
        Upload cover image to a Spotify playlist.

        Args:
            playlist_id: Spotify playlist ID
            image_path: Path to image file (JPEG format, max 256KB)

        Returns:
            True if successful, False otherwise
        """
        try:
            import base64

            # Read and encode image
            with open(image_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            # Upload to Spotify
            self.sp.playlist_upload_cover_image(playlist_id, image_data)
            logger.info(f"Successfully uploaded cover image for playlist {playlist_id}")
            return True

        except Exception as e:
            logger.error(f"Error uploading playlist cover: {e}")
            return False
