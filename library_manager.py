#!/usr/bin/env python3
"""
Cross-Platform Music Library Manager

Tracks all music across platforms (Spotify, TIDAL, SoundCloud) with exact matching.
Uses a CSV file as the source of truth for sync operations.

CSV Schema:
- spotify_id: Spotify track ID (primary key for Spotify)
- tidal_id: TIDAL track ID (null if not available/not searched)
- soundcloud_id: SoundCloud track ID (future)
- track_name: Track title
- artist_name: Primary artist name
- album_name: Album name
- playlist_ids: Comma-separated list of Spotify playlist IDs containing this track
- spotify_available: True/False - track exists on Spotify
- tidal_available: True/False/null - True if found, False if searched but not found, null if not searched
- soundcloud_available: True/False/null (future)
- last_synced: ISO timestamp of last sync operation
- notes: Optional notes (e.g., "remix not on TIDAL")
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path


class LibraryManager:
    """
    Manages cross-platform music library tracking via CSV.

    This class provides:
    - Track registration from Spotify
    - Cross-platform ID mapping (Spotify <-> TIDAL <-> SoundCloud)
    - Availability tracking per platform
    - Playlist membership tracking
    - Sync status queries
    """

    FIELDNAMES = [
        'spotify_id',
        'tidal_id',
        'soundcloud_id',
        'track_name',
        'artist_name',
        'album_name',
        'playlist_ids',
        'spotify_available',
        'tidal_available',
        'soundcloud_available',
        'last_synced',
        'notes'
    ]

    def __init__(self, library_file: str = "data/library.csv"):
        """
        Initialize the library manager.

        Args:
            library_file: Path to the CSV library file
        """
        self.library_file = library_file
        self.tracks: Dict[str, Dict] = {}  # spotify_id -> track data
        self._load_library()

    def _load_library(self):
        """Load existing library from CSV file."""
        if not os.path.exists(self.library_file):
            return

        try:
            with open(self.library_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    spotify_id = row.get('spotify_id')
                    if spotify_id:
                        # Convert string booleans back to proper types
                        row['spotify_available'] = self._parse_bool(row.get('spotify_available'))
                        row['tidal_available'] = self._parse_bool(row.get('tidal_available'))
                        row['soundcloud_available'] = self._parse_bool(row.get('soundcloud_available'))
                        # Parse playlist_ids as set
                        playlist_str = row.get('playlist_ids', '')
                        row['playlist_ids'] = set(playlist_str.split(',')) if playlist_str else set()
                        self.tracks[spotify_id] = row
        except Exception as e:
            print(f"WARNING: Error loading library: {e}")

    def _parse_bool(self, value: str) -> Optional[bool]:
        """Parse string boolean value (True/False/null)."""
        if value is None or value == '' or value.lower() == 'null':
            return None
        return value.lower() == 'true'

    def _bool_to_str(self, value: Optional[bool]) -> str:
        """Convert boolean to string for CSV."""
        if value is None:
            return 'null'
        return 'True' if value else 'False'

    def save_library(self):
        """
        Save library to CSV file atomically.

        Uses temp file + rename pattern to prevent corruption.
        """
        dir_path = os.path.dirname(self.library_file) or '.'
        temp_path = os.path.join(dir_path, f".library_temp_{os.getpid()}.csv")

        try:
            with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()

                for spotify_id, track in self.tracks.items():
                    row = track.copy()
                    # Convert set back to comma-separated string
                    playlist_ids = row.get('playlist_ids', set())
                    row['playlist_ids'] = ','.join(sorted(playlist_ids)) if playlist_ids else ''
                    # Convert booleans to strings
                    row['spotify_available'] = self._bool_to_str(row.get('spotify_available'))
                    row['tidal_available'] = self._bool_to_str(row.get('tidal_available'))
                    row['soundcloud_available'] = self._bool_to_str(row.get('soundcloud_available'))
                    writer.writerow(row)

            # Atomic rename
            os.replace(temp_path, self.library_file)

        except Exception as e:
            print(f"ERROR saving library: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def add_track(self, spotify_id: str, track_name: str, artist_name: str,
                  album_name: str = "", playlist_id: Optional[str] = None) -> Dict:
        """
        Add or update a track in the library.

        Args:
            spotify_id: Spotify track ID
            track_name: Track title
            artist_name: Primary artist name
            album_name: Album name
            playlist_id: Optional playlist ID to associate with this track

        Returns:
            The track record (new or updated)
        """
        if spotify_id in self.tracks:
            # Update existing track
            track = self.tracks[spotify_id]
            if playlist_id:
                track['playlist_ids'].add(playlist_id)
            # Update metadata if changed
            track['track_name'] = track_name
            track['artist_name'] = artist_name
            if album_name:
                track['album_name'] = album_name
        else:
            # Create new track
            track = {
                'spotify_id': spotify_id,
                'tidal_id': '',
                'soundcloud_id': '',
                'track_name': track_name,
                'artist_name': artist_name,
                'album_name': album_name,
                'playlist_ids': {playlist_id} if playlist_id else set(),
                'spotify_available': True,
                'tidal_available': None,  # Not searched yet
                'soundcloud_available': None,
                'last_synced': '',
                'notes': ''
            }
            self.tracks[spotify_id] = track

        return track

    def set_tidal_id(self, spotify_id: str, tidal_id: Optional[str], available: bool = True):
        """
        Set TIDAL ID for a track.

        Args:
            spotify_id: Spotify track ID
            tidal_id: TIDAL track ID (None if not found)
            available: Whether track is available on TIDAL
        """
        if spotify_id not in self.tracks:
            return

        track = self.tracks[spotify_id]
        track['tidal_id'] = tidal_id or ''
        track['tidal_available'] = available
        track['last_synced'] = datetime.now().isoformat()

    def set_soundcloud_id(self, spotify_id: str, soundcloud_id: Optional[str], available: bool = True):
        """
        Set SoundCloud ID for a track (future use).

        Args:
            spotify_id: Spotify track ID
            soundcloud_id: SoundCloud track ID (None if not found)
            available: Whether track is available on SoundCloud
        """
        if spotify_id not in self.tracks:
            return

        track = self.tracks[spotify_id]
        track['soundcloud_id'] = soundcloud_id or ''
        track['soundcloud_available'] = available
        track['last_synced'] = datetime.now().isoformat()

    def get_track(self, spotify_id: str) -> Optional[Dict]:
        """Get track by Spotify ID."""
        return self.tracks.get(spotify_id)

    def get_tracks_for_playlist(self, playlist_id: str) -> List[Dict]:
        """Get all tracks belonging to a specific playlist."""
        return [
            track for track in self.tracks.values()
            if playlist_id in track.get('playlist_ids', set())
        ]

    def get_unsynced_tracks_for_playlist(self, playlist_id: str, platform: str = 'tidal') -> List[Dict]:
        """
        Get tracks in a playlist that haven't been synced to a platform.

        Args:
            playlist_id: Spotify playlist ID
            platform: Target platform ('tidal' or 'soundcloud')

        Returns:
            List of track records that need syncing
        """
        available_key = f'{platform}_available'

        unsynced = []
        for track in self.tracks.values():
            if playlist_id not in track.get('playlist_ids', set()):
                continue

            availability = track.get(available_key)
            # Track needs syncing if:
            # - availability is None (never searched)
            # - OR availability is True but we don't have the platform ID yet
            if availability is None:
                unsynced.append(track)
            elif availability is True and not track.get(f'{platform}_id'):
                unsynced.append(track)

        return unsynced

    def get_unavailable_tracks(self, platform: str = 'tidal') -> List[Dict]:
        """Get all tracks that are not available on a platform."""
        available_key = f'{platform}_available'
        return [
            track for track in self.tracks.values()
            if track.get(available_key) is False
        ]

    def is_playlist_synced(self, playlist_id: str, spotify_track_ids: Set[str], platform: str = 'tidal') -> bool:
        """
        Check if a playlist is fully synced to a platform.

        A playlist is synced when:
        1. All Spotify tracks are registered in the library
        2. All tracks have been searched on the target platform

        Args:
            playlist_id: Spotify playlist ID
            spotify_track_ids: Set of Spotify track IDs currently in the playlist
            platform: Target platform to check

        Returns:
            True if fully synced, False otherwise
        """
        available_key = f'{platform}_available'

        for track_id in spotify_track_ids:
            track = self.tracks.get(track_id)
            if not track:
                # Track not in library at all
                return False

            if playlist_id not in track.get('playlist_ids', set()):
                # Track not associated with this playlist
                return False

            if track.get(available_key) is None:
                # Track hasn't been searched on this platform
                return False

        return True

    def get_sync_stats(self, playlist_id: Optional[str] = None) -> Dict:
        """
        Get sync statistics for the library or a specific playlist.

        Args:
            playlist_id: Optional playlist ID to filter by

        Returns:
            Dict with sync statistics
        """
        if playlist_id:
            tracks = self.get_tracks_for_playlist(playlist_id)
        else:
            tracks = list(self.tracks.values())

        total = len(tracks)
        tidal_available = sum(1 for t in tracks if t.get('tidal_available') is True)
        tidal_unavailable = sum(1 for t in tracks if t.get('tidal_available') is False)
        tidal_unsearched = sum(1 for t in tracks if t.get('tidal_available') is None)

        soundcloud_available = sum(1 for t in tracks if t.get('soundcloud_available') is True)
        soundcloud_unavailable = sum(1 for t in tracks if t.get('soundcloud_available') is False)
        soundcloud_unsearched = sum(1 for t in tracks if t.get('soundcloud_available') is None)

        return {
            'total_tracks': total,
            'tidal': {
                'available': tidal_available,
                'unavailable': tidal_unavailable,
                'unsearched': tidal_unsearched,
                'match_rate': (tidal_available / (tidal_available + tidal_unavailable) * 100)
                              if (tidal_available + tidal_unavailable) > 0 else 0
            },
            'soundcloud': {
                'available': soundcloud_available,
                'unavailable': soundcloud_unavailable,
                'unsearched': soundcloud_unsearched,
                'match_rate': (soundcloud_available / (soundcloud_available + soundcloud_unavailable) * 100)
                              if (soundcloud_available + soundcloud_unavailable) > 0 else 0
            }
        }

    def export_unavailable_tracks(self, platform: str = 'tidal', output_file: Optional[str] = None) -> str:
        """
        Export tracks not available on a platform to a separate CSV.

        Args:
            platform: Platform to check ('tidal' or 'soundcloud')
            output_file: Optional output file path

        Returns:
            Path to the exported file
        """
        if output_file is None:
            output_file = f"unavailable_on_{platform}.csv"

        unavailable = self.get_unavailable_tracks(platform)

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['artist_name', 'track_name', 'album_name', 'spotify_id', 'notes'])
            writer.writeheader()
            for track in unavailable:
                writer.writerow({
                    'artist_name': track.get('artist_name', ''),
                    'track_name': track.get('track_name', ''),
                    'album_name': track.get('album_name', ''),
                    'spotify_id': track.get('spotify_id', ''),
                    'notes': track.get('notes', '')
                })

        return output_file

    def get_library_summary(self) -> str:
        """Get a human-readable summary of the library."""
        stats = self.get_sync_stats()

        lines = [
            f"Music Library: {self.library_file}",
            f"Total tracks: {stats['total_tracks']}",
            "",
            "TIDAL:",
            f"  Available: {stats['tidal']['available']}",
            f"  Unavailable: {stats['tidal']['unavailable']}",
            f"  Not searched: {stats['tidal']['unsearched']}",
            f"  Match rate: {stats['tidal']['match_rate']:.1f}%",
            "",
            "SoundCloud:",
            f"  Available: {stats['soundcloud']['available']}",
            f"  Unavailable: {stats['soundcloud']['unavailable']}",
            f"  Not searched: {stats['soundcloud']['unsearched']}",
        ]

        return '\n'.join(lines)


def main():
    """CLI for library management."""
    import argparse

    parser = argparse.ArgumentParser(description='Music Library Manager')
    parser.add_argument('--library', default='data/library.csv', help='Path to library CSV')
    parser.add_argument('--stats', action='store_true', help='Show library statistics')
    parser.add_argument('--export-unavailable', metavar='PLATFORM',
                        help='Export tracks unavailable on PLATFORM (tidal/soundcloud)')
    args = parser.parse_args()

    manager = LibraryManager(args.library)

    if args.stats:
        print(manager.get_library_summary())
    elif args.export_unavailable:
        output = manager.export_unavailable_tracks(args.export_unavailable)
        print(f"Exported to: {output}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
