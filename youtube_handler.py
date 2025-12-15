"""
YouTube API handler for fetching playlist data
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class YouTubeHandler:
    """Handler for YouTube Data API v3 operations"""
    
    def __init__(self, api_key: str):
        """
        Initialize YouTube API client.
        
        Args:
            api_key: YouTube Data API key
        """
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
    
    def get_playlist_info(self, playlist_id: str) -> Optional[Dict]:
        """
        Get basic playlist information.
        
        Args:
            playlist_id: YouTube playlist ID
            
        Returns:
            Dictionary with playlist info or None if error
        """
        try:
            request = self.youtube.playlists().list(
                part='snippet',
                id=playlist_id,
                maxResults=1
            )
            response = request.execute()
            
            if response['items']:
                snippet = response['items'][0]['snippet']
                return {
                    'id': playlist_id,
                    'title': snippet['title'],
                    'description': snippet.get('description', ''),
                    'channel': snippet['channelTitle']
                }
            return None
            
        except HttpError as e:
            logger.error(f"Error fetching playlist info: {e}")
            return None
    
    def get_playlist_videos(self, playlist_id: str, max_results: Optional[int] = None) -> List[Dict]:
        """
        Fetch all videos from a YouTube playlist.
        
        Args:
            playlist_id: YouTube playlist ID
            max_results: Maximum number of videos to fetch (None for all)
            
        Returns:
            List of video dictionaries with title, video_id, and position
        """
        videos = []
        next_page_token = None
        
        try:
            while True:
                request = self.youtube.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=playlist_id,
                    maxResults=50,  # API max per request
                    pageToken=next_page_token
                )
                
                response = request.execute()
                
                for item in response['items']:
                    snippet = item['snippet']
                    
                    # Skip deleted/private videos
                    if snippet['title'] == 'Deleted video' or snippet['title'] == 'Private video':
                        logger.warning(f"Skipping deleted/private video at position {snippet['position']}")
                        continue
                    
                    video_data = {
                        'title': snippet['title'],
                        'video_id': snippet['resourceId']['videoId'],
                        'position': snippet['position'],
                        'channel': snippet.get('videoOwnerChannelTitle', 'Unknown')
                    }
                    videos.append(video_data)
                    
                    # Check if we've reached max_results
                    if max_results and len(videos) >= max_results:
                        logger.info(f"Reached maximum of {max_results} videos")
                        return videos
                
                # Check for next page
                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break
                
                logger.debug(f"Fetched {len(videos)} videos so far...")
            
            logger.info(f"Successfully fetched {len(videos)} videos from playlist")
            return videos
            
        except HttpError as e:
            logger.error(f"Error fetching playlist videos: {e}")
            raise
    
    def get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        Get detailed information for multiple videos.
        Useful for getting duration, tags, etc.
        
        Args:
            video_ids: List of YouTube video IDs (max 50 per call)
            
        Returns:
            List of video detail dictionaries
        """
        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails',
                id=','.join(video_ids)
            )
            response = request.execute()
            return response.get('items', [])
            
        except HttpError as e:
            logger.error(f"Error fetching video details: {e}")
            return []
