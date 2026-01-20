#!/usr/bin/env python3
"""
Complete Spotify to TIDAL Playlist Transfer Script
Handles all playlists with proper throttling and error recovery.

Usage:
    python spotify_to_tidal_complete.py

Requirements:
    - tidalapi (pip install tidalapi)
    - spotipy (pip install spotipy)

You'll need:
    - Spotify API credentials (Client ID, Client Secret)
    - TIDAL credentials (username, password)
"""

import time
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

try:
    import tidalapi
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Please run:")
    print("  pip install tidalapi spotipy --break-system-packages")
    exit(1)


class SpotifyToTidalTransfer:
    def __init__(self):
        self.spotify = None
        self.tidal = None
        self.stats = {
            "playlists_processed": 0,
            "playlists_skipped": 0,
            "total_tracks_found": 0,
            "total_tracks_not_found": 0,
            "start_time": datetime.now()
        }
        self.log_file = f"transfer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    def log(self, message: str, also_print: bool = True):
        """Log message to file and optionally print."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

        if also_print:
            print(log_message)

    def setup_spotify(self):
        """Setup Spotify client with OAuth."""
        self.log("Setting up Spotify authentication...")

        # Get credentials from environment or prompt
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:8888/callback')

        if not client_id or not client_secret:
            self.log("ERROR: Spotify credentials not found in environment variables.")
            self.log("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
            self.log("Get them from: https://developer.spotify.com/dashboard")
            return False

        try:
            scope = "playlist-read-private playlist-read-collaborative user-library-read"
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                open_browser=True
            )
            self.spotify = spotipy.Spotify(auth_manager=auth_manager)

            # Test connection
            user = self.spotify.current_user()
            self.log(f"✅ Connected to Spotify as: {user['display_name']}")
            return True

        except Exception as e:
            self.log(f"ERROR setting up Spotify: {str(e)}")
            return False

    def setup_tidal(self):
        """Setup TIDAL client."""
        self.log("Setting up TIDAL authentication...")

        try:
            session = tidalapi.Session()

            # Try to load existing session
            session_file = 'tidal_session.json'
            if os.path.exists(session_file):
                try:
                    session.load_oauth_session_from_file(session_file)
                    if session.check_login():
                        self.tidal = session
                        user = session.user
                        self.log(f"✅ Connected to TIDAL as: {user.name if user else 'Unknown'}")
                        return True
                except:
                    pass

            # Need new login
            self.log("Opening browser for TIDAL OAuth login...")
            login, future = session.login_oauth()
            self.log(f"Visit this URL to authorize: {login.verification_uri_complete}")
            future.result()

            # Save session
            session.save_oauth_session_to_file(session_file)
            self.tidal = session

            user = session.user
            self.log(f"✅ Connected to TIDAL as: {user.name if user else 'Unknown'}")
            return True

        except Exception as e:
            self.log(f"ERROR setting up TIDAL: {str(e)}")
            return False

    def get_all_spotify_playlists(self) -> List[Dict]:
        """Get all user's Spotify playlists."""
        self.log("Fetching all Spotify playlists...")

        try:
            playlists = []
            offset = 0
            limit = 50

            while True:
                results = self.spotify.current_user_playlists(limit=limit, offset=offset)
                if not results['items']:
                    break

                playlists.extend(results['items'])
                offset += limit

                if len(results['items']) < limit:
                    break

            # Filter to only owned playlists
            user_id = self.spotify.current_user()['id']
            owned = [p for p in playlists if p['owner']['id'] == user_id]

            self.log(f"Found {len(playlists)} total playlists, {len(owned)} owned by you")
            return owned

        except Exception as e:
            self.log(f"ERROR fetching Spotify playlists: {str(e)}")
            return []

    def get_all_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Get ALL tracks from a Spotify playlist (handles pagination)."""
        tracks = []
        offset = 0
        limit = 100

        while True:
            try:
                results = self.spotify.playlist_tracks(
                    playlist_id,
                    offset=offset,
                    limit=limit,
                    fields='items(track(name,artists(name),id)),total'
                )

                if not results['items']:
                    break

                for item in results['items']:
                    if item['track']:  # Skip None tracks
                        track = item['track']
                        tracks.append({
                            'name': track['name'],
                            'artists': [a['name'] for a in track['artists']],
                            'id': track['id']
                        })

                offset += limit

                if len(results['items']) < limit:
                    break

            except Exception as e:
                self.log(f"ERROR fetching tracks at offset {offset}: {str(e)}")
                break

        return tracks

    def search_tidal_track(self, track_name: str, artist_name: str, throttle: float = 1.5) -> Optional[str]:
        """Search for a track on TIDAL."""
        try:
            query = f"{artist_name} {track_name}"
            results = self.tidal.search(query, models=[tidalapi.media.Track], limit=1)

            # Throttle to avoid API issues
            time.sleep(throttle)

            if results and 'tracks' in results and len(results['tracks']) > 0:
                return results['tracks'][0].id

            return None

        except Exception as e:
            self.log(f"ERROR searching TIDAL for '{artist_name} - {track_name}': {str(e)}", False)
            time.sleep(throttle)
            return None

    def create_tidal_playlist(self, name: str, description: str = "") -> Optional[str]:
        """Create a TIDAL playlist."""
        try:
            playlist = self.tidal.user.create_playlist(name, description)
            return playlist.id
        except Exception as e:
            self.log(f"ERROR creating TIDAL playlist '{name}': {str(e)}")
            return None

    def add_tracks_to_tidal_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Add tracks to TIDAL playlist."""
        try:
            playlist = self.tidal.playlist(playlist_id)
            playlist.add(track_ids)
            time.sleep(3)  # Extra delay after batch add
            return True
        except Exception as e:
            self.log(f"ERROR adding tracks to TIDAL playlist: {str(e)}")
            return False

    def transfer_playlist(self, spotify_playlist: Dict, throttle: float = 1.5) -> Dict:
        """Transfer a single playlist from Spotify to TIDAL."""
        name = spotify_playlist['name']
        playlist_id = spotify_playlist['id']
        total_tracks = spotify_playlist['tracks']['total']

        self.log(f"\n{'='*80}")
        self.log(f"Processing: {name} ({total_tracks} tracks)")
        self.log(f"{'='*80}")

        # Skip empty playlists
        if total_tracks == 0:
            self.log(f"⏭️  Skipping empty playlist")
            return {"status": "skipped", "reason": "empty"}

        # Get all tracks
        self.log(f"Fetching all {total_tracks} tracks from Spotify...")
        spotify_tracks = self.get_all_playlist_tracks(playlist_id)

        if not spotify_tracks:
            self.log(f"⚠️  No tracks retrieved")
            return {"status": "error", "reason": "no_tracks"}

        self.log(f"Retrieved {len(spotify_tracks)} tracks")

        # Create TIDAL playlist
        self.log(f"Creating TIDAL playlist...")
        tidal_playlist_id = self.create_tidal_playlist(
            name,
            f"Transferred from Spotify - {len(spotify_tracks)} tracks - {datetime.now().strftime('%Y-%m-%d')}"
        )

        if not tidal_playlist_id:
            return {"status": "error", "reason": "playlist_creation_failed"}

        self.log(f"✅ Created TIDAL playlist (ID: {tidal_playlist_id})")

        # Search and add tracks
        tidal_track_ids = []
        found_count = 0
        not_found_count = 0

        for idx, track in enumerate(spotify_tracks, 1):
            track_name = track['name']
            artist_name = track['artists'][0] if track['artists'] else "Unknown"

            self.log(f"  [{idx}/{len(spotify_tracks)}] {artist_name} - {track_name}", False)

            # Print progress every 10 tracks
            if idx % 10 == 0:
                self.log(f"Progress: {idx}/{len(spotify_tracks)} ({found_count} found, {not_found_count} not found)")

            tidal_track_id = self.search_tidal_track(track_name, artist_name, throttle)

            if tidal_track_id:
                tidal_track_ids.append(str(tidal_track_id))
                found_count += 1
            else:
                not_found_count += 1
                self.log(f"    ❌ Not found: {artist_name} - {track_name}", False)

            # Add in batches of 50
            if len(tidal_track_ids) >= 50:
                self.log(f"  Adding batch of {len(tidal_track_ids)} tracks...")
                success = self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)
                if success:
                    self.log(f"  ✅ Batch added")
                else:
                    self.log(f"  ⚠️  Batch add failed, retrying...")
                    time.sleep(5)
                    self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)
                tidal_track_ids = []

        # Add remaining tracks
        if tidal_track_ids:
            self.log(f"  Adding final batch of {len(tidal_track_ids)} tracks...")
            self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)

        self.log(f"\n✅ Completed: {name}")
        self.log(f"   Found: {found_count}/{len(spotify_tracks)} ({found_count/len(spotify_tracks)*100:.1f}%)")
        self.log(f"   Not found: {not_found_count}")

        self.stats["total_tracks_found"] += found_count
        self.stats["total_tracks_not_found"] += not_found_count

        return {
            "status": "completed",
            "name": name,
            "total": len(spotify_tracks),
            "found": found_count,
            "not_found": not_found_count
        }

    def run(self):
        """Main transfer process."""
        self.log("="*80)
        self.log("SPOTIFY TO TIDAL PLAYLIST TRANSFER")
        self.log("="*80)

        # Setup
        if not self.setup_spotify():
            return

        if not self.setup_tidal():
            return

        # Get playlists
        playlists = self.get_all_spotify_playlists()
        if not playlists:
            self.log("No playlists to transfer")
            return

        # Sort by name to get "Trip Inside This House" first (or keep original order)
        # For now, keeping original order

        self.log(f"\nStarting transfer of {len(playlists)} playlists...")
        self.log(f"Using 1.5s throttle between track searches")
        self.log(f"This will take significant time - grab a coffee! ☕")

        results = []

        for idx, playlist in enumerate(playlists, 1):
            self.log(f"\n[Playlist {idx}/{len(playlists)}]")
            result = self.transfer_playlist(playlist, throttle=1.5)
            results.append(result)
            self.stats["playlists_processed"] += 1

            # Brief pause between playlists
            if idx < len(playlists):
                self.log(f"Pausing 5s before next playlist...")
                time.sleep(5)

        # Final summary
        elapsed = datetime.now() - self.stats["start_time"]

        self.log("\n" + "="*80)
        self.log("TRANSFER COMPLETE")
        self.log("="*80)
        self.log(f"Time elapsed: {elapsed}")
        self.log(f"Playlists processed: {self.stats['playlists_processed']}")
        self.log(f"Total tracks found: {self.stats['total_tracks_found']}")
        self.log(f"Total tracks not found: {self.stats['total_tracks_not_found']}")

        completed = [r for r in results if r["status"] == "completed"]
        if completed:
            self.log("\n✅ Successfully transferred:")
            for r in completed:
                self.log(f"   - {r['name']}: {r['found']}/{r['total']} tracks")

        self.log(f"\nFull log saved to: {self.log_file}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Spotify to TIDAL Playlist Transfer")
    print("="*80)
    print("\nStarting transfer with configured credentials...")

    transfer = SpotifyToTidalTransfer()
    transfer.run()
