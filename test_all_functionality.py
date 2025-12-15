"""
Comprehensive test suite for YouTube to Spotify Playlist Transfer
Tests every single functionality in the codebase with extensive coverage
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call, mock_open
import sys
import re
import os
from typing import Dict, List

# Import modules to test
from utils import (
    clean_youtube_title,
    parse_artist_title,
    build_search_queries,
    similarity_score,
    verify_match,
    format_track_info,
    extract_playlist_id
)


class TestUtilsFunctions(unittest.TestCase):
    """Test all utility functions in utils.py"""

    def test_clean_youtube_title_removes_brackets(self):
        """Test that brackets and their contents are removed"""
        title = "Artist - Song [Official Video]"
        result = clean_youtube_title(title)
        self.assertNotIn('[', result)
        self.assertNotIn(']', result)
        self.assertIn('Artist', result)
        self.assertIn('Song', result)

    def test_clean_youtube_title_removes_parentheses(self):
        """Test that parentheses and their contents are removed"""
        title = "Artist - Song (Official Music Video)"
        result = clean_youtube_title(title)
        self.assertNotIn('(', result)
        self.assertNotIn(')', result)
        self.assertIn('Artist', result)
        self.assertIn('Song', result)

    def test_clean_youtube_title_removes_keywords(self):
        """Test that common YouTube keywords are removed"""
        title = "Artist - Song Official Video Lyrics HD"
        result = clean_youtube_title(title)
        self.assertNotIn('Official Video', result.lower())
        self.assertNotIn('Lyrics', result.lower())
        self.assertNotIn('HD', result.lower())

    def test_clean_youtube_title_normalizes_spaces(self):
        """Test that multiple spaces are normalized to single space"""
        title = "Artist   -    Song     Title"
        result = clean_youtube_title(title)
        self.assertNotIn('  ', result)

    def test_clean_youtube_title_replaces_symbols(self):
        """Test that certain symbols are replaced with dashes"""
        title = "Artist | Song"
        result = clean_youtube_title(title)
        self.assertIn('-', result)

    def test_parse_artist_title_dash_separator(self):
        """Test parsing with dash separator (most common format)"""
        title = "The Beatles - Hey Jude"
        artist, song = parse_artist_title(title)
        self.assertEqual(artist, "The Beatles")
        self.assertEqual(song, "Hey Jude")

    def test_parse_artist_title_colon_separator(self):
        """Test parsing with colon separator"""
        title = "Pink Floyd: Comfortably Numb"
        artist, song = parse_artist_title(title)
        self.assertEqual(artist, "Pink Floyd")
        self.assertEqual(song, "Comfortably Numb")

    def test_parse_artist_title_by_keyword(self):
        """Test parsing with 'by' keyword"""
        title = "Bohemian Rhapsody by Queen"
        artist, song = parse_artist_title(title)
        self.assertEqual(artist, "Queen")
        self.assertEqual(song, "Bohemian Rhapsody")

    def test_parse_artist_title_quoted_format(self):
        """Test parsing with quoted song title"""
        title = 'Artist "Song Title"'
        artist, song = parse_artist_title(title)
        self.assertEqual(artist, "Artist")
        self.assertEqual(song, "Song Title")

    def test_parse_artist_title_no_pattern_match(self):
        """Test parsing when no pattern matches"""
        title = "Random Video Title Without Pattern"
        artist, song = parse_artist_title(title)
        self.assertIsNone(artist)
        self.assertIsNotNone(song)

    def test_parse_artist_title_with_clutter(self):
        """Test parsing with YouTube clutter"""
        title = "Metallica - Enter Sandman (Official Music Video) [HD]"
        artist, song = parse_artist_title(title)
        self.assertEqual(artist, "Metallica")
        self.assertIn("Enter Sandman", song)

    def test_build_search_queries_with_parsed_artist(self):
        """Test query building when artist and title are parsed"""
        title = "The Beatles - Hey Jude"
        queries = build_search_queries(title)

        self.assertIsInstance(queries, list)
        self.assertTrue(len(queries) > 0)

        # Should contain artist + title query
        self.assertTrue(any("Beatles" in q and "Hey Jude" in q for q in queries))

        # Should contain Spotify advanced syntax
        self.assertTrue(any('artist:' in q and 'track:' in q for q in queries))

    def test_build_search_queries_without_parsed_artist(self):
        """Test query building when artist cannot be parsed"""
        title = "Some Random Video Title"
        queries = build_search_queries(title)

        self.assertIsInstance(queries, list)
        self.assertTrue(len(queries) > 0)
        self.assertIn(title, queries)

    def test_build_search_queries_uniqueness(self):
        """Test that queries don't contain duplicates"""
        title = "Artist - Song"
        queries = build_search_queries(title)

        # Check no duplicates
        self.assertEqual(len(queries), len(set(queries)))

    def test_similarity_score_identical_strings(self):
        """Test similarity score for identical strings"""
        score = similarity_score("test string", "test string")
        self.assertEqual(score, 1.0)

    def test_similarity_score_completely_different(self):
        """Test similarity score for completely different strings"""
        score = similarity_score("abc", "xyz")
        self.assertLess(score, 0.5)

    def test_similarity_score_case_insensitive(self):
        """Test that similarity score is case insensitive"""
        score1 = similarity_score("Test String", "test string")
        score2 = similarity_score("test string", "test string")
        self.assertEqual(score1, score2)

    def test_similarity_score_partial_match(self):
        """Test similarity score for partial matches"""
        score = similarity_score("The Beatles - Hey Jude", "Hey Jude")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_verify_match_high_confidence(self):
        """Test match verification with high confidence match"""
        youtube_title = "The Beatles - Hey Jude"
        spotify_track = {
            'name': 'Hey Jude',
            'artists': [{'name': 'The Beatles'}]
        }

        result = verify_match(youtube_title, spotify_track, threshold=0.6)
        self.assertTrue(result)

    def test_verify_match_low_confidence(self):
        """Test match verification with low confidence match"""
        youtube_title = "The Beatles - Hey Jude"
        spotify_track = {
            'name': 'Some Other Song',
            'artists': [{'name': 'Different Artist'}]
        }

        result = verify_match(youtube_title, spotify_track, threshold=0.6)
        self.assertFalse(result)

    def test_verify_match_custom_threshold(self):
        """Test match verification with custom threshold"""
        youtube_title = "Song Title"
        spotify_track = {
            'name': 'Song',
            'artists': [{'name': 'Artist'}]
        }

        # Should pass with low threshold
        result_low = verify_match(youtube_title, spotify_track, threshold=0.3)
        # Might fail with high threshold
        result_high = verify_match(youtube_title, spotify_track, threshold=0.9)

        # At least verify the function accepts custom threshold
        self.assertIsInstance(result_low, bool)
        self.assertIsInstance(result_high, bool)

    def test_verify_match_multiple_artists(self):
        """Test match verification with multiple artists"""
        youtube_title = "Artist1 & Artist2 - Song Title"
        spotify_track = {
            'name': 'Song Title',
            'artists': [{'name': 'Artist1'}, {'name': 'Artist2'}]
        }

        result = verify_match(youtube_title, spotify_track, threshold=0.6)
        self.assertTrue(result)

    def test_format_track_info_single_artist(self):
        """Test track info formatting with single artist"""
        track = {
            'name': 'Hey Jude',
            'artists': [{'name': 'The Beatles'}]
        }

        result = format_track_info(track)
        self.assertIn('The Beatles', result)
        self.assertIn('Hey Jude', result)
        self.assertIn(' - ', result)

    def test_format_track_info_multiple_artists(self):
        """Test track info formatting with multiple artists"""
        track = {
            'name': 'Song Title',
            'artists': [{'name': 'Artist1'}, {'name': 'Artist2'}]
        }

        result = format_track_info(track)
        self.assertIn('Artist1', result)
        self.assertIn('Artist2', result)
        self.assertIn('Song Title', result)

    def test_extract_playlist_id_from_url(self):
        """Test playlist ID extraction from full URL"""
        url = "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        result = extract_playlist_id(url)
        self.assertEqual(result, "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    def test_extract_playlist_id_from_url_with_params(self):
        """Test playlist ID extraction from URL with additional parameters"""
        url = "https://www.youtube.com/playlist?v=video_id&list=PLyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy&index=5"
        result = extract_playlist_id(url)
        self.assertEqual(result, "PLyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy")

    def test_extract_playlist_id_already_id(self):
        """Test that function returns ID if already just an ID"""
        playlist_id = "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        result = extract_playlist_id(playlist_id)
        self.assertEqual(result, playlist_id)

    def test_extract_playlist_id_invalid_format(self):
        """Test handling of invalid format"""
        invalid = "not_a_valid_format"
        result = extract_playlist_id(invalid)
        # Should return as-is if no pattern matches
        self.assertEqual(result, invalid)


class TestYouTubeHandler(unittest.TestCase):
    """Test YouTubeHandler class from youtube_handler.py"""

    @patch('youtube_handler.build')
    def test_youtube_handler_initialization(self, mock_build):
        """Test YouTubeHandler initialization"""
        from youtube_handler import YouTubeHandler

        api_key = "test_api_key"
        handler = YouTubeHandler(api_key)

        self.assertEqual(handler.api_key, api_key)
        mock_build.assert_called_once_with('youtube', 'v3', developerKey=api_key)

    @patch('youtube_handler.build')
    def test_get_playlist_info_success(self, mock_build):
        """Test successful playlist info retrieval"""
        from youtube_handler import YouTubeHandler

        # Mock API response
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_response = {
            'items': [{
                'snippet': {
                    'title': 'Test Playlist',
                    'description': 'Test Description',
                    'channelTitle': 'Test Channel'
                }
            }]
        }

        mock_youtube.playlists().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        result = handler.get_playlist_info("PLtest")

        self.assertIsNotNone(result)
        self.assertEqual(result['title'], 'Test Playlist')
        self.assertEqual(result['channel'], 'Test Channel')
        self.assertEqual(result['id'], 'PLtest')

    @patch('youtube_handler.build')
    def test_get_playlist_info_not_found(self, mock_build):
        """Test playlist info when playlist not found"""
        from youtube_handler import YouTubeHandler

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_response = {'items': []}
        mock_youtube.playlists().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        result = handler.get_playlist_info("PLnotfound")

        self.assertIsNone(result)

    @patch('youtube_handler.build')
    def test_get_playlist_videos_single_page(self, mock_build):
        """Test fetching playlist videos from single page"""
        from youtube_handler import YouTubeHandler

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_response = {
            'items': [
                {
                    'snippet': {
                        'title': 'Video 1',
                        'position': 0,
                        'resourceId': {'videoId': 'vid1'},
                        'videoOwnerChannelTitle': 'Channel 1'
                    }
                },
                {
                    'snippet': {
                        'title': 'Video 2',
                        'position': 1,
                        'resourceId': {'videoId': 'vid2'},
                        'videoOwnerChannelTitle': 'Channel 2'
                    }
                }
            ]
        }

        mock_youtube.playlistItems().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        videos = handler.get_playlist_videos("PLtest")

        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0]['title'], 'Video 1')
        self.assertEqual(videos[1]['video_id'], 'vid2')

    @patch('youtube_handler.build')
    def test_get_playlist_videos_skip_deleted(self, mock_build):
        """Test that deleted/private videos are skipped"""
        from youtube_handler import YouTubeHandler

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_response = {
            'items': [
                {
                    'snippet': {
                        'title': 'Deleted video',
                        'position': 0,
                        'resourceId': {'videoId': 'deleted'},
                        'videoOwnerChannelTitle': 'Channel'
                    }
                },
                {
                    'snippet': {
                        'title': 'Valid Video',
                        'position': 1,
                        'resourceId': {'videoId': 'valid'},
                        'videoOwnerChannelTitle': 'Channel'
                    }
                },
                {
                    'snippet': {
                        'title': 'Private video',
                        'position': 2,
                        'resourceId': {'videoId': 'private'},
                        'videoOwnerChannelTitle': 'Channel'
                    }
                }
            ]
        }

        mock_youtube.playlistItems().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        videos = handler.get_playlist_videos("PLtest")

        # Should only have 1 valid video
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]['title'], 'Valid Video')

    @patch('youtube_handler.build')
    def test_get_playlist_videos_max_results(self, mock_build):
        """Test max_results parameter limits videos returned"""
        from youtube_handler import YouTubeHandler

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        # Create 10 videos
        items = []
        for i in range(10):
            items.append({
                'snippet': {
                    'title': f'Video {i}',
                    'position': i,
                    'resourceId': {'videoId': f'vid{i}'},
                    'videoOwnerChannelTitle': 'Channel'
                }
            })

        mock_response = {'items': items}
        mock_youtube.playlistItems().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        videos = handler.get_playlist_videos("PLtest", max_results=5)

        self.assertEqual(len(videos), 5)

    @patch('youtube_handler.build')
    def test_get_video_details(self, mock_build):
        """Test getting video details"""
        from youtube_handler import YouTubeHandler

        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        mock_response = {
            'items': [
                {'id': 'vid1', 'snippet': {'title': 'Video 1'}},
                {'id': 'vid2', 'snippet': {'title': 'Video 2'}}
            ]
        }

        mock_youtube.videos().list().execute.return_value = mock_response

        handler = YouTubeHandler("test_key")
        details = handler.get_video_details(['vid1', 'vid2'])

        self.assertEqual(len(details), 2)
        self.assertEqual(details[0]['id'], 'vid1')


class TestSpotifyHandler(unittest.TestCase):
    """Test SpotifyHandler class from spotify_handler.py"""

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_spotify_handler_initialization(self, mock_oauth, mock_spotify):
        """Test SpotifyHandler initialization"""
        from spotify_handler import SpotifyHandler

        handler = SpotifyHandler(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost:8080",
            scope="test_scope"
        )

        self.assertEqual(handler.client_id, "test_id")
        self.assertEqual(handler.client_secret, "test_secret")
        mock_oauth.assert_called_once()

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_get_current_user(self, mock_oauth, mock_spotify):
        """Test getting current user profile"""
        from spotify_handler import SpotifyHandler

        mock_user = {'id': 'user123', 'display_name': 'Test User'}
        mock_spotify_instance = MagicMock()
        mock_spotify_instance.current_user.return_value = mock_user
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        user = handler.get_current_user()

        self.assertEqual(user['id'], 'user123')
        self.assertEqual(user['display_name'], 'Test User')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_search_track_success(self, mock_oauth, mock_spotify):
        """Test successful track search"""
        from spotify_handler import SpotifyHandler

        mock_results = {
            'tracks': {
                'items': [
                    {'id': 'track1', 'name': 'Song 1'},
                    {'id': 'track2', 'name': 'Song 2'}
                ]
            }
        }

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.search.return_value = mock_results
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        tracks = handler.search_track("test query", limit=5)

        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0]['name'], 'Song 1')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_search_track_no_results(self, mock_oauth, mock_spotify):
        """Test track search with no results"""
        from spotify_handler import SpotifyHandler

        mock_results = {'tracks': {'items': []}}

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.search.return_value = mock_results
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        tracks = handler.search_track("nonexistent song")

        self.assertEqual(len(tracks), 0)

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    @patch('spotify_handler.time.sleep')
    def test_search_track_best_match(self, mock_sleep, mock_oauth, mock_spotify):
        """Test searching with multiple queries"""
        from spotify_handler import SpotifyHandler

        # First query fails, second succeeds
        mock_spotify_instance = MagicMock()
        mock_spotify_instance.search.side_effect = [
            {'tracks': {'items': []}},  # First query: no results
            {'tracks': {'items': [{'id': 'track1', 'name': 'Song'}]}}  # Second query: success
        ]
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        track = handler.search_track_best_match(['query1', 'query2'])

        self.assertIsNotNone(track)
        self.assertEqual(track['name'], 'Song')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_get_track_info(self, mock_oauth, mock_spotify):
        """Test getting track info by ID"""
        from spotify_handler import SpotifyHandler

        mock_track = {'id': 'track123', 'name': 'Test Song'}

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.track.return_value = mock_track
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        track = handler.get_track_info('track123')

        self.assertEqual(track['id'], 'track123')
        self.assertEqual(track['name'], 'Test Song')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_create_playlist(self, mock_oauth, mock_spotify):
        """Test creating a new playlist"""
        from spotify_handler import SpotifyHandler

        mock_user = {'id': 'user123'}
        mock_playlist = {'id': 'playlist123', 'name': 'Test Playlist'}

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.current_user.return_value = mock_user
        mock_spotify_instance.user_playlist_create.return_value = mock_playlist
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        playlist_id = handler.create_playlist("Test Playlist", "Description", public=True)

        self.assertEqual(playlist_id, 'playlist123')
        mock_spotify_instance.user_playlist_create.assert_called_once()

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    @patch('spotify_handler.time.sleep')
    def test_add_tracks_to_playlist(self, mock_sleep, mock_oauth, mock_spotify):
        """Test adding tracks to playlist"""
        from spotify_handler import SpotifyHandler

        mock_spotify_instance = MagicMock()
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        track_ids = ['track1', 'track2', 'track3']
        success = handler.add_tracks_to_playlist('playlist123', track_ids)

        self.assertTrue(success)
        mock_spotify_instance.playlist_add_items.assert_called_once_with('playlist123', track_ids)

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    @patch('spotify_handler.time.sleep')
    def test_add_tracks_to_playlist_batching(self, mock_sleep, mock_oauth, mock_spotify):
        """Test that large track lists are batched"""
        from spotify_handler import SpotifyHandler

        mock_spotify_instance = MagicMock()
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")

        # Create 150 tracks (should require 2 batches)
        track_ids = [f'track{i}' for i in range(150)]
        success = handler.add_tracks_to_playlist('playlist123', track_ids)

        self.assertTrue(success)
        # Should be called twice (100 + 50)
        self.assertEqual(mock_spotify_instance.playlist_add_items.call_count, 2)

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_get_playlist_url(self, mock_oauth, mock_spotify):
        """Test playlist URL generation"""
        from spotify_handler import SpotifyHandler

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        url = handler.get_playlist_url('playlist123')

        self.assertEqual(url, 'https://open.spotify.com/playlist/playlist123')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_playlist_exists_found(self, mock_oauth, mock_spotify):
        """Test checking if playlist exists (found)"""
        from spotify_handler import SpotifyHandler

        mock_user = {'id': 'user123'}
        mock_playlists = {
            'items': [
                {'id': 'pl1', 'name': 'Playlist 1'},
                {'id': 'pl2', 'name': 'Test Playlist'},
                {'id': 'pl3', 'name': 'Playlist 3'}
            ]
        }

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.current_user.return_value = mock_user
        mock_spotify_instance.user_playlists.return_value = mock_playlists
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        playlist_id = handler.playlist_exists('Test Playlist')

        self.assertEqual(playlist_id, 'pl2')

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    def test_playlist_exists_not_found(self, mock_oauth, mock_spotify):
        """Test checking if playlist exists (not found)"""
        from spotify_handler import SpotifyHandler

        mock_user = {'id': 'user123'}
        mock_playlists = {
            'items': [
                {'id': 'pl1', 'name': 'Playlist 1'},
                {'id': 'pl2', 'name': 'Playlist 2'}
            ]
        }

        mock_spotify_instance = MagicMock()
        mock_spotify_instance.current_user.return_value = mock_user
        mock_spotify_instance.user_playlists.return_value = mock_playlists
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        playlist_id = handler.playlist_exists('Nonexistent Playlist')

        self.assertIsNone(playlist_id)

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    @patch('builtins.open', create=True)
    def test_upload_playlist_cover_success(self, mock_open, mock_oauth, mock_spotify):
        """Test successful playlist cover upload"""
        from spotify_handler import SpotifyHandler
        import base64

        mock_spotify_instance = MagicMock()
        mock_spotify.return_value = mock_spotify_instance

        # Mock file reading
        mock_file = MagicMock()
        mock_file.read.return_value = b'fake_image_data'
        mock_open.return_value.__enter__.return_value = mock_file

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        success = handler.upload_playlist_cover('playlist123', '/path/to/image.jpg')

        self.assertTrue(success)
        mock_spotify_instance.playlist_upload_cover_image.assert_called_once()

    @patch('spotify_handler.spotipy.Spotify')
    @patch('spotify_handler.SpotifyOAuth')
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_upload_playlist_cover_file_not_found(self, mock_open, mock_oauth, mock_spotify):
        """Test playlist cover upload with non-existent file"""
        from spotify_handler import SpotifyHandler

        mock_spotify_instance = MagicMock()
        mock_spotify.return_value = mock_spotify_instance

        handler = SpotifyHandler("id", "secret", "uri", "scope")
        success = handler.upload_playlist_cover('playlist123', '/path/to/nonexistent.jpg')

        self.assertFalse(success)


class TestPlaylistTransfer(unittest.TestCase):
    """Test PlaylistTransfer class from transfer.py"""

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_playlist_transfer_initialization(self, mock_youtube, mock_spotify):
        """Test PlaylistTransfer initialization"""
        from transfer import PlaylistTransfer

        # Mock handlers
        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        transfer = PlaylistTransfer()

        self.assertIsNotNone(transfer.youtube)
        self.assertIsNotNone(transfer.spotify)

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_fetch_youtube_playlist(self, mock_youtube, mock_spotify):
        """Test fetching YouTube playlist"""
        from transfer import PlaylistTransfer

        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}

        mock_playlist_info = {
            'id': 'PLtest',
            'title': 'Test Playlist',
            'channel': 'Test Channel'
        }

        mock_videos = [
            {'title': 'Video 1', 'video_id': 'vid1'},
            {'title': 'Video 2', 'video_id': 'vid2'}
        ]

        mock_yt_instance.get_playlist_info.return_value = mock_playlist_info
        mock_yt_instance.get_playlist_videos.return_value = mock_videos

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        transfer = PlaylistTransfer()
        playlist_info, videos = transfer.fetch_youtube_playlist('PLtest')

        self.assertEqual(playlist_info['title'], 'Test Playlist')
        self.assertEqual(len(videos), 2)

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_match_tracks(self, mock_youtube, mock_spotify):
        """Test matching YouTube videos to Spotify tracks"""
        from transfer import PlaylistTransfer

        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}

        # Mock search results
        def search_side_effect(queries):
            if 'Video 1' in str(queries):
                return {'id': 'track1', 'name': 'Song 1', 'artists': [{'name': 'Artist 1'}]}
            return None

        mock_sp_instance.search_track_best_match.side_effect = search_side_effect

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        videos = [
            {'title': 'Video 1', 'video_id': 'vid1'},
            {'title': 'Video 2', 'video_id': 'vid2'}
        ]

        transfer = PlaylistTransfer()
        matches = transfer.match_tracks(videos)

        self.assertEqual(len(matches), 2)
        # First video should match
        self.assertIsNotNone(matches[0][1])
        # Second video should not match (None)
        self.assertIsNone(matches[1][1])

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_create_spotify_playlist(self, mock_youtube, mock_spotify):
        """Test creating Spotify playlist with matched tracks"""
        from transfer import PlaylistTransfer

        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}
        mock_sp_instance.create_playlist.return_value = 'playlist123'
        mock_sp_instance.add_tracks_to_playlist.return_value = True
        mock_sp_instance.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        matches = [
            ({'title': 'Video 1'}, {'id': 'track1', 'name': 'Song 1'}, 'matched'),
            ({'title': 'Video 2'}, {'id': 'track2', 'name': 'Song 2'}, 'low_confidence'),
            ({'title': 'Video 3'}, None, 'not_found')
        ]

        transfer = PlaylistTransfer()
        playlist_id = transfer.create_spotify_playlist(
            'Test Playlist',
            matches,
            include_low_confidence=True
        )

        self.assertEqual(playlist_id, 'playlist123')
        mock_sp_instance.create_playlist.assert_called_once()
        mock_sp_instance.add_tracks_to_playlist.assert_called_once()

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_create_spotify_playlist_high_confidence_only(self, mock_youtube, mock_spotify):
        """Test creating playlist with only high confidence matches"""
        from transfer import PlaylistTransfer

        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}
        mock_sp_instance.create_playlist.return_value = 'playlist123'
        mock_sp_instance.add_tracks_to_playlist.return_value = True

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        matches = [
            ({'title': 'Video 1'}, {'id': 'track1', 'name': 'Song 1'}, 'matched'),
            ({'title': 'Video 2'}, {'id': 'track2', 'name': 'Song 2'}, 'low_confidence'),
            ({'title': 'Video 3'}, None, 'not_found')
        ]

        transfer = PlaylistTransfer()
        playlist_id = transfer.create_spotify_playlist(
            'Test Playlist',
            matches,
            include_low_confidence=False
        )

        # Should only add 1 track (high confidence)
        call_args = mock_sp_instance.add_tracks_to_playlist.call_args
        added_tracks = call_args[0][1]
        self.assertEqual(len(added_tracks), 1)
        self.assertEqual(added_tracks[0], 'track1')

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    def test_transfer_complete_flow(self, mock_youtube, mock_spotify):
        """Test complete transfer flow"""
        from transfer import PlaylistTransfer

        # Setup mocks
        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()

        mock_sp_instance.get_current_user.return_value = {'display_name': 'Test User'}

        mock_playlist_info = {
            'id': 'PLtest',
            'title': 'YouTube Playlist',
            'channel': 'Test Channel'
        }

        mock_videos = [
            {'title': 'Artist - Song', 'video_id': 'vid1'}
        ]

        mock_yt_instance.get_playlist_info.return_value = mock_playlist_info
        mock_yt_instance.get_playlist_videos.return_value = mock_videos

        mock_sp_instance.search_track_best_match.return_value = {
            'id': 'track1',
            'name': 'Song',
            'artists': [{'name': 'Artist'}]
        }

        mock_sp_instance.create_playlist.return_value = 'playlist123'
        mock_sp_instance.add_tracks_to_playlist.return_value = True
        mock_sp_instance.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        # Run transfer
        transfer = PlaylistTransfer()
        result_url = transfer.transfer('PLtest')

        self.assertEqual(result_url, 'https://open.spotify.com/playlist/playlist123')

        # Verify all steps were called
        mock_yt_instance.get_playlist_info.assert_called_once()
        mock_yt_instance.get_playlist_videos.assert_called_once()
        mock_sp_instance.search_track_best_match.assert_called()
        mock_sp_instance.create_playlist.assert_called_once()
        mock_sp_instance.add_tracks_to_playlist.assert_called_once()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_clean_youtube_title_empty_string(self):
        """Test cleaning empty string"""
        result = clean_youtube_title("")
        self.assertEqual(result, "")

    def test_clean_youtube_title_only_brackets(self):
        """Test title with only brackets"""
        result = clean_youtube_title("[Official Video]")
        self.assertNotIn('[', result)

    def test_parse_artist_title_empty_string(self):
        """Test parsing empty string"""
        artist, title = parse_artist_title("")
        self.assertIsNone(artist)

    def test_similarity_score_empty_strings(self):
        """Test similarity of empty strings"""
        score = similarity_score("", "")
        self.assertEqual(score, 1.0)

    def test_extract_playlist_id_empty_string(self):
        """Test extracting from empty string"""
        result = extract_playlist_id("")
        self.assertEqual(result, "")

    def test_build_search_queries_empty_title(self):
        """Test building queries with empty title"""
        queries = build_search_queries("")
        self.assertIsInstance(queries, list)
        self.assertTrue(len(queries) > 0)

    def test_format_track_info_no_artists(self):
        """Test formatting track with empty artists list"""
        track = {'name': 'Song', 'artists': []}
        result = format_track_info(track)
        self.assertIn('Song', result)


class TestGradioApp(unittest.TestCase):
    """Test Gradio app (app.py) and CLI (transfer.py) functionality"""

    @patch('app.PlaylistTransfer')
    def test_fetch_tracks_empty_url(self, mock_transfer_class):
        """Test fetch_tracks with empty YouTube URL"""
        from app import fetch_tracks

        result = fetch_tracks("", True)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        self.assertIn('Error', result[0])
        self.assertIn('YouTube playlist URL', result[0])

    @patch('app.PlaylistTransfer')
    def test_fetch_tracks_initialization_error(self, mock_transfer_class):
        """Test fetch_tracks when initialization fails"""
        from app import fetch_tracks

        mock_transfer_class.side_effect = Exception("API credentials invalid")

        result = fetch_tracks("PLtest", True)

        self.assertIsInstance(result, tuple)
        self.assertIn('Error', result[0])
        self.assertIn('API credentials', result[0])

    @patch('app.PlaylistTransfer')
    def test_fetch_tracks_success(self, mock_transfer_class):
        """Test successful track fetching"""
        from app import fetch_tracks

        # Mock the transfer instance
        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_playlist_info = {
            'id': 'PLtest',
            'title': 'Test Playlist',
            'channel': 'Test Channel'
        }

        mock_videos = [
            {'title': 'Video 1', 'video_id': 'vid1'},
            {'title': 'Video 2', 'video_id': 'vid2'}
        ]

        mock_matches = [
            (
                {'title': 'Video 1'},
                {'id': 'track1', 'name': 'Song 1', 'artists': [{'name': 'Artist 1'}]},
                'matched'
            ),
            (
                {'title': 'Video 2'},
                {'id': 'track2', 'name': 'Song 2', 'artists': [{'name': 'Artist 2'}]},
                'low_confidence'
            )
        ]

        mock_transfer.fetch_youtube_playlist.return_value = (mock_playlist_info, mock_videos)
        mock_transfer.match_tracks.return_value = mock_matches

        status_msg, tracks_data, state_data, stats = fetch_tracks("PLtest", True)

        # Check return types
        self.assertIsInstance(status_msg, str)
        self.assertIsInstance(tracks_data, list)
        self.assertIsInstance(state_data, dict)
        self.assertIsInstance(stats, str)

        # Check status message
        self.assertIn('Fetched Successfully', status_msg)
        self.assertIn('Test Playlist', status_msg)

        # Check tracks data (should have 2 tracks)
        self.assertEqual(len(tracks_data), 2)
        self.assertTrue(tracks_data[0][0])  # First column is checkbox, should be True
        self.assertIn('Video 1', tracks_data[0][1])
        self.assertIn('Song 1', tracks_data[0][2])
        self.assertIn('High', tracks_data[0][3])

        # Check state data
        self.assertIn('playlist_info', state_data)
        self.assertIn('matches', state_data)
        self.assertEqual(len(state_data['matches']), 2)

        # Check statistics
        self.assertIn('Total Videos:', stats)
        self.assertIn('High Confidence Matches:', stats)

    @patch('app.PlaylistTransfer')
    def test_fetch_tracks_no_videos(self, mock_transfer_class):
        """Test fetch_tracks when no videos found"""
        from app import fetch_tracks

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_playlist_info = {
            'id': 'PLtest',
            'title': 'Empty Playlist',
            'channel': 'Test Channel'
        }

        mock_transfer.fetch_youtube_playlist.return_value = (mock_playlist_info, [])

        status_msg, tracks_data, state_data, stats = fetch_tracks("PLtest", True)

        self.assertIn('Error', status_msg)
        self.assertIn('No videos found', status_msg)

    @patch('app.PlaylistTransfer')
    def test_fetch_tracks_exclude_low_confidence(self, mock_transfer_class):
        """Test fetch_tracks with low confidence excluded"""
        from app import fetch_tracks

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_playlist_info = {
            'id': 'PLtest',
            'title': 'Test Playlist',
            'channel': 'Test Channel'
        }

        mock_videos = [
            {'title': 'Video 1', 'video_id': 'vid1'},
            {'title': 'Video 2', 'video_id': 'vid2'}
        ]

        mock_matches = [
            ({'title': 'Video 1'}, {'id': 'track1', 'name': 'Song 1', 'artists': [{'name': 'Artist 1'}]}, 'matched'),
            ({'title': 'Video 2'}, {'id': 'track2', 'name': 'Song 2', 'artists': [{'name': 'Artist 2'}]}, 'low_confidence')
        ]

        mock_transfer.fetch_youtube_playlist.return_value = (mock_playlist_info, mock_videos)
        mock_transfer.match_tracks.return_value = mock_matches

        status_msg, tracks_data, state_data, stats = fetch_tracks("PLtest", False)

        # Should only have 1 track (high confidence)
        self.assertEqual(len(tracks_data), 1)
        self.assertIn('Song 1', tracks_data[0][2])

    @patch('app.PlaylistTransfer')
    def test_create_playlist_no_state(self, mock_transfer_class):
        """Test create_playlist without fetching tracks first"""
        from app import create_playlist

        result = create_playlist("Test Playlist", "Description", None, [], {})

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIn('Error', result[0])
        self.assertIn('fetch tracks first', result[0])

    @patch('app.PlaylistTransfer')
    def test_create_playlist_no_tracks_selected(self, mock_transfer_class):
        """Test create_playlist with no tracks selected"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        state_dict = {
            'playlist_info': {'title': 'Test', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1'}, 'status': 'matched'}
            ]
        }

        # All tracks unchecked
        tracks_dataframe = [[False, 'Video 1', 'Song 1', 'High']]

        status_msg, playlist_url = create_playlist("Test", "Desc", None, tracks_dataframe, state_dict)

        self.assertIn('Error', status_msg)
        self.assertIn('No tracks selected', status_msg)

    @patch('app.PlaylistTransfer')
    def test_create_playlist_success(self, mock_transfer_class):
        """Test successful playlist creation"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_transfer.spotify.create_playlist.return_value = 'playlist123'
        mock_transfer.spotify.add_tracks_to_playlist.return_value = True
        mock_transfer.spotify.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        state_dict = {
            'playlist_info': {'title': 'YouTube Playlist', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1', 'name': 'Song 1'}, 'status': 'matched'},
                {'video': {'title': 'Video 2'}, 'track': {'id': 'track2', 'name': 'Song 2'}, 'status': 'matched'}
            ]
        }

        # Two tracks selected
        tracks_dataframe = [
            [True, 'Video 1', 'Song 1', 'High'],
            [True, 'Video 2', 'Song 2', 'High']
        ]

        status_msg, playlist_url = create_playlist("My Playlist", "My Description", None, tracks_dataframe, state_dict)

        self.assertIn('Created Successfully', status_msg)
        self.assertIn('My Playlist', status_msg)
        self.assertIn('2', status_msg)  # 2 tracks added
        self.assertEqual(playlist_url, 'https://open.spotify.com/playlist/playlist123')

        # Verify create_playlist was called with correct params
        mock_transfer.spotify.create_playlist.assert_called_once()
        call_args = mock_transfer.spotify.create_playlist.call_args
        self.assertEqual(call_args[1]['name'], 'My Playlist')
        self.assertEqual(call_args[1]['description'], 'My Description')

    @patch('app.PlaylistTransfer')
    def test_create_playlist_uses_youtube_name(self, mock_transfer_class):
        """Test that YouTube name is used when Spotify name is empty"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_transfer.spotify.create_playlist.return_value = 'playlist123'
        mock_transfer.spotify.add_tracks_to_playlist.return_value = True
        mock_transfer.spotify.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        state_dict = {
            'playlist_info': {'title': 'YouTube Playlist Name', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1'}, 'status': 'matched'}
            ]
        }

        tracks_dataframe = [[True, 'Video 1', 'Song 1', 'High']]

        status_msg, playlist_url = create_playlist("", "", None, tracks_dataframe, state_dict)

        # Check that YouTube name was used
        call_args = mock_transfer.spotify.create_playlist.call_args
        self.assertIn('YouTube Playlist Name', call_args[1]['name'])
        self.assertIn('from YouTube', call_args[1]['name'])

    @patch('app.PlaylistTransfer')
    def test_create_playlist_partial_selection(self, mock_transfer_class):
        """Test creating playlist with only some tracks selected"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_transfer.spotify.create_playlist.return_value = 'playlist123'
        mock_transfer.spotify.add_tracks_to_playlist.return_value = True
        mock_transfer.spotify.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        state_dict = {
            'playlist_info': {'title': 'Test', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1'}, 'status': 'matched'},
                {'video': {'title': 'Video 2'}, 'track': {'id': 'track2'}, 'status': 'matched'},
                {'video': {'title': 'Video 3'}, 'track': {'id': 'track3'}, 'status': 'matched'}
            ]
        }

        # Only first and third track selected
        tracks_dataframe = [
            [True, 'Video 1', 'Song 1', 'High'],
            [False, 'Video 2', 'Song 2', 'High'],
            [True, 'Video 3', 'Song 3', 'High']
        ]

        status_msg, playlist_url = create_playlist("Test", "Desc", None, tracks_dataframe, state_dict)

        # Should add 2 tracks
        self.assertIn('2', status_msg)

        # Verify only selected tracks were added
        call_args = mock_transfer.spotify.add_tracks_to_playlist.call_args
        added_tracks = call_args[0][1]
        self.assertEqual(len(added_tracks), 2)
        self.assertEqual(added_tracks[0], 'track1')
        self.assertEqual(added_tracks[1], 'track3')

    @patch('app.PlaylistTransfer')
    @patch('builtins.open', create=True)
    def test_create_playlist_with_cover_image(self, mock_open, mock_transfer_class):
        """Test creating playlist with cover image upload"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_transfer.spotify.create_playlist.return_value = 'playlist123'
        mock_transfer.spotify.add_tracks_to_playlist.return_value = True
        mock_transfer.spotify.upload_playlist_cover.return_value = True
        mock_transfer.spotify.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        state_dict = {
            'playlist_info': {'title': 'Test', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1'}, 'status': 'matched'}
            ]
        }

        tracks_dataframe = [[True, 'Video 1', 'Song 1', 'High']]

        # Mock file for cover image
        mock_file = MagicMock()
        mock_file.read.return_value = b'fake_image_data'
        mock_open.return_value.__enter__.return_value = mock_file

        status_msg, playlist_url = create_playlist("Test", "Desc", "/path/to/cover.jpg", tracks_dataframe, state_dict)

        # Verify cover was uploaded
        mock_transfer.spotify.upload_playlist_cover.assert_called_once_with('playlist123', '/path/to/cover.jpg')
        self.assertIn('Created Successfully', status_msg)

    @patch('app.PlaylistTransfer')
    def test_create_playlist_cover_upload_fails(self, mock_transfer_class):
        """Test that playlist creation continues even if cover upload fails"""
        from app import create_playlist

        mock_transfer = MagicMock()
        mock_transfer_class.return_value = mock_transfer

        mock_transfer.spotify.create_playlist.return_value = 'playlist123'
        mock_transfer.spotify.add_tracks_to_playlist.return_value = True
        mock_transfer.spotify.upload_playlist_cover.side_effect = Exception("Upload failed")
        mock_transfer.spotify.get_playlist_url.return_value = 'https://open.spotify.com/playlist/playlist123'

        state_dict = {
            'playlist_info': {'title': 'Test', 'channel': 'Test Channel'},
            'matches': [
                {'video': {'title': 'Video 1'}, 'track': {'id': 'track1'}, 'status': 'matched'}
            ]
        }

        tracks_dataframe = [[True, 'Video 1', 'Song 1', 'High']]

        # Should succeed even if cover upload fails
        status_msg, playlist_url = create_playlist("Test", "Desc", "/path/to/cover.jpg", tracks_dataframe, state_dict)

        self.assertIn('Created Successfully', status_msg)
        self.assertEqual(playlist_url, 'https://open.spotify.com/playlist/playlist123')

    @patch('os.makedirs')
    def test_create_ui_returns_blocks(self, mock_makedirs):
        """Test that create_ui returns a Gradio Blocks object"""
        from app import create_ui

        app = create_ui()

        # Check that it's a Gradio Blocks object
        self.assertIsNotNone(app)
        # The object should have a launch method
        self.assertTrue(hasattr(app, 'launch'))

    @patch('os.makedirs')
    def test_logs_directory_created_app(self, mock_makedirs):
        """Test that logs directory is created on app.py import"""
        # Re-import app module to trigger directory creation
        import importlib
        import app as app_module
        importlib.reload(app_module)

        # Verify makedirs was called with 'logs' and exist_ok=True
        mock_makedirs.assert_called_with('logs', exist_ok=True)

    @patch('transfer.SpotifyHandler')
    @patch('transfer.YouTubeHandler')
    @patch('os.makedirs')
    @patch('builtins.input', side_effect=['', '', ''])
    def test_logs_directory_created_transfer_main(self, mock_input, mock_makedirs, mock_youtube, mock_spotify):
        """Test that logs directory is created when transfer.py main() is called"""
        from transfer import main

        # Mock the handlers to prevent actual initialization
        mock_yt_instance = MagicMock()
        mock_sp_instance = MagicMock()
        mock_youtube.return_value = mock_yt_instance
        mock_spotify.return_value = mock_sp_instance

        try:
            main()
        except:
            pass  # main() will fail due to empty input, but we just want to check makedirs

        # Verify makedirs was called with 'logs' and exist_ok=True
        mock_makedirs.assert_called_with('logs', exist_ok=True)


def run_tests():
    """Run all tests and print detailed results"""

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestUtilsFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestYouTubeHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestSpotifyHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestPlaylistTransfer))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestGradioApp))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)

    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
    else:
        print("\n✗ SOME TESTS FAILED")

    return result


if __name__ == '__main__':
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST SUITE")
    print("YouTube to Spotify Playlist Transfer")
    print("="*70)
    print("Total Tests: 77")
    print("="*70 + "\n")

    result = run_tests()

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
