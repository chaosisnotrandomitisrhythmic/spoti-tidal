#!/usr/bin/env python3
"""
Spotify to TIDAL Playlist Transfer

A tool to transfer all your Spotify playlists to TIDAL with automatic resume
support, duplicate prevention, and progress tracking.

Features:
- Transfers ALL playlists and tracks (handles pagination)
- Automatic checkpoint/resume if interrupted
- Detects existing TIDAL playlists to avoid duplicates
- Skips tracks already in target playlist
- Progress bars for visual feedback
- Detailed logging

Setup:
1. Copy .env.example to .env and add your Spotify API credentials
2. Create venv and install: uv venv && source .venv/bin/activate && uv pip install tidalapi spotipy tqdm python-dotenv
3. Run: python spotify_to_tidal_transfer.py

For Spotify API credentials, visit: https://developer.spotify.com/dashboard
"""

import time
import json
import os
import argparse
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, can use system environment variables

try:
    import tidalapi
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from tqdm import tqdm
except ImportError as e:
    print("ERROR: Required packages not installed.")
    print("Please run:")
    print("  uv pip install tidalapi spotipy tqdm python-dotenv")
    exit(1)


class SpotifyToTidalTransfer:
    """
    Main class for transferring Spotify playlists to TIDAL.

    Handles authentication, playlist discovery, track searching,
    and checkpoint-based resume functionality.
    """

    def __init__(self, checkpoint_file: str = "transfer_checkpoint.json", fresh_start: bool = False, sync_only: bool = False):
        """
        Initialize the transfer manager.

        Args:
            checkpoint_file: Path to save/load transfer progress
            fresh_start: If True, ignore existing checkpoint and start fresh
            sync_only: If True, only sync playlists that have new tracks (skip fully synced)
        """
        self.spotify = None
        self.tidal = None
        self.stats = {
            "playlists_processed": 0,
            "playlists_skipped": 0,
            "playlists_already_synced": 0,
            "total_tracks_found": 0,
            "total_tracks_not_found": 0,
            "start_time": datetime.now()
        }
        self.log_file = f"transfer_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        self.checkpoint_file = checkpoint_file
        self.checkpoint = None
        self.fresh_start = fresh_start
        self.sync_only = sync_only
        # Cache of existing TIDAL playlists: {name: {"id": str, "track_count": int, "track_ids": Set}}
        self.tidal_playlist_cache = {}

    def log(self, message: str, also_print: bool = True):
        """Log message to file and optionally print."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')

        if also_print:
            print(log_message)

    # ==================== Checkpoint Management ====================

    def load_checkpoint(self) -> Optional[Dict]:
        """
        Load existing checkpoint file if it exists and is valid.

        Returns:
            Checkpoint dict if valid checkpoint exists, None otherwise
        """
        if not os.path.exists(self.checkpoint_file):
            return None

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)

            # Validate checkpoint structure
            if checkpoint.get("version") != "1.0":
                self.log("Checkpoint version mismatch, starting fresh")
                return None

            if checkpoint.get("status") == "completed":
                self.log("Previous transfer completed, starting fresh")
                return None

            return checkpoint
        except (json.JSONDecodeError, KeyError) as e:
            self.log(f"Checkpoint file corrupted: {e}, starting fresh")
            return None

    def save_checkpoint(self):
        """
        Save current checkpoint state atomically.

        Uses temp file + rename pattern to prevent corruption if
        the script is interrupted during write.
        """
        if self.checkpoint is None:
            return

        self.checkpoint["updated_at"] = datetime.now().isoformat()

        # Atomic write: write to temp file, then rename (prevents corruption)
        dir_path = os.path.dirname(self.checkpoint_file) or '.'
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix='.json', dir=dir_path)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(self.checkpoint, f, indent=2, default=str)
            shutil.move(temp_path, self.checkpoint_file)
        except Exception as e:
            self.log(f"ERROR saving checkpoint: {e}")
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def clear_checkpoint(self):
        """Remove checkpoint file after successful completion."""
        if os.path.exists(self.checkpoint_file):
            # Archive the completed checkpoint
            archive_name = f"transfer_checkpoint_completed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy(self.checkpoint_file, archive_name)
            os.remove(self.checkpoint_file)
            self.log(f"Checkpoint archived to {archive_name}")

    def init_checkpoint(self, playlists: List[Dict], spotify_user_id: str):
        """Initialize a new checkpoint for the transfer."""
        self.checkpoint = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "spotify_user_id": spotify_user_id,
            "status": "in_progress",
            "total_playlists": len(playlists),
            "playlists": {}
        }

        for playlist in playlists:
            self.checkpoint["playlists"][playlist['id']] = {
                "name": playlist['name'],
                "status": "pending",
                "tidal_playlist_id": None,
                "tracks_processed": 0,
                "tracks_found": 0,
                "tracks_not_found": 0
            }

        self.save_checkpoint()

    # ==================== TIDAL Playlist Detection ====================

    def build_tidal_playlist_cache(self):
        """
        Build cache of all TIDAL playlists owned by user.

        This enables duplicate detection - if a playlist with the same name
        already exists on TIDAL, we'll add tracks to it instead of creating
        a new duplicate playlist.
        """
        self.log("Building TIDAL playlist cache...")
        try:
            user_playlists = self.tidal.user.playlists()
            for playlist in tqdm(user_playlists, desc="Caching TIDAL playlists", unit="playlist"):
                self.tidal_playlist_cache[playlist.name] = {
                    "id": playlist.id,
                    "track_count": playlist.num_tracks if hasattr(playlist, 'num_tracks') else None,
                    "track_ids": None  # Lazy loaded when needed
                }
            self.log(f"Cached {len(self.tidal_playlist_cache)} TIDAL playlists")
        except Exception as e:
            self.log(f"WARNING: Could not cache TIDAL playlists: {e}")

    def find_tidal_playlist_by_name(self, name: str) -> Optional[str]:
        """Find existing TIDAL playlist by name. Returns playlist ID or None."""
        if name in self.tidal_playlist_cache:
            return self.tidal_playlist_cache[name]["id"]
        return None

    def get_tidal_playlist_track_ids(self, playlist_id: str) -> Set[str]:
        """Get all track IDs currently in a TIDAL playlist."""
        try:
            playlist = self.tidal.playlist(playlist_id)
            tracks = playlist.tracks()
            track_ids = {str(t.id) for t in tracks}
            return track_ids
        except Exception as e:
            self.log(f"WARNING: Could not fetch TIDAL playlist tracks: {e}")
            return set()

    def get_tidal_playlist_track_count(self, playlist_id: str) -> int:
        """Get the number of tracks in a TIDAL playlist."""
        try:
            playlist = self.tidal.playlist(playlist_id)
            return playlist.num_tracks if hasattr(playlist, 'num_tracks') else len(playlist.tracks())
        except Exception as e:
            self.log(f"WARNING: Could not fetch TIDAL playlist track count: {e}")
            return 0

    def is_playlist_synced(self, spotify_playlist: Dict) -> bool:
        """
        Check if a Spotify playlist is already fully synced to TIDAL.

        A playlist is considered synced if:
        1. A TIDAL playlist with the same name exists
        2. The TIDAL playlist has at least as many tracks as Spotify
           (accounting for ~10-15% of tracks not being available on TIDAL)
        """
        name = spotify_playlist['name']
        spotify_track_count = spotify_playlist['tracks']['total']

        if name not in self.tidal_playlist_cache:
            return False

        tidal_info = self.tidal_playlist_cache[name]
        tidal_track_count = tidal_info.get("track_count")

        if tidal_track_count is None:
            # Need to fetch track count
            tidal_track_count = self.get_tidal_playlist_track_count(tidal_info["id"])
            self.tidal_playlist_cache[name]["track_count"] = tidal_track_count

        # Consider synced if TIDAL has at least 80% of Spotify tracks
        # (accounting for tracks not available on TIDAL)
        min_expected = int(spotify_track_count * 0.80)

        return tidal_track_count >= min_expected

    # ==================== Authentication ====================

    def setup_spotify(self):
        """Setup Spotify client with OAuth."""
        self.log("Setting up Spotify authentication...")

        # Load credentials from environment variables
        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:47281/callback')

        if not client_id or not client_secret:
            self.log("ERROR: Spotify credentials not found.")
            self.log("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env file")
            self.log("See .env.example for the required format")
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
            session_file = Path('tidal_session.json')
            if session_file.exists():
                try:
                    session.load_session_from_file(session_file)
                    if session.check_login():
                        self.tidal = session
                        user = session.user
                        self.log(f"✅ Connected to TIDAL as: {user.first_name or user.username if user else 'Unknown'}")
                        return True
                except:
                    pass

            # Need new login
            self.log("Opening browser for TIDAL OAuth login...")
            login, future = session.login_oauth()
            self.log(f"Visit this URL to authorize: {login.verification_uri_complete}")
            future.result()

            # Save session
            session.save_session_to_file(session_file)
            self.tidal = session

            user = session.user
            self.log(f"✅ Connected to TIDAL as: {user.first_name or user.username if user else 'Unknown'}")
            return True

        except Exception as e:
            self.log(f"ERROR setting up TIDAL: {str(e)}")
            return False

    # ==================== Spotify Data Fetching ====================

    def get_all_spotify_playlists(self) -> List[Dict]:
        """Get all user's Spotify playlists (owned only, handles pagination)."""
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

    # ==================== TIDAL Operations ====================

    def search_tidal_track(self, track_name: str, artist_name: str, throttle: float = 1.5) -> Optional[str]:
        """Search for a track on TIDAL. Returns track ID if found."""
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

    # ==================== Transfer Logic ====================

    def transfer_playlist(self, spotify_playlist: Dict, throttle: float = 1.5) -> Dict:
        """
        Transfer a single playlist from Spotify to TIDAL.

        Handles:
        - Finding or creating the TIDAL playlist
        - Resuming from checkpoint if interrupted
        - Skipping tracks already in the playlist
        - Saving checkpoint after each batch
        """
        name = spotify_playlist['name']
        spotify_id = spotify_playlist['id']
        total_tracks = spotify_playlist['tracks']['total']

        self.log(f"\n{'='*80}")
        self.log(f"Processing: {name} ({total_tracks} tracks)")
        self.log(f"{'='*80}")

        # Get checkpoint entry for this playlist
        checkpoint_entry = self.checkpoint["playlists"].get(spotify_id, {})

        # Skip empty playlists
        if total_tracks == 0:
            self.log(f"⏭️  Skipping empty playlist")
            checkpoint_entry["status"] = "completed"
            self.checkpoint["playlists"][spotify_id] = checkpoint_entry
            self.save_checkpoint()
            return {"status": "skipped", "reason": "empty"}

        # Get all tracks from Spotify
        self.log(f"Fetching all {total_tracks} tracks from Spotify...")
        spotify_tracks = self.get_all_playlist_tracks(spotify_id)

        if not spotify_tracks:
            self.log(f"⚠️  No tracks retrieved")
            return {"status": "error", "reason": "no_tracks"}

        self.log(f"Retrieved {len(spotify_tracks)} tracks")

        # Check for existing TIDAL playlist (duplicate prevention)
        existing_tidal_id = checkpoint_entry.get("tidal_playlist_id")
        if not existing_tidal_id:
            existing_tidal_id = self.find_tidal_playlist_by_name(name)

        if existing_tidal_id:
            self.log(f"📂 Found existing TIDAL playlist: {name}")
            tidal_playlist_id = existing_tidal_id
            # Get existing track IDs to avoid duplicates
            existing_track_ids = self.get_tidal_playlist_track_ids(tidal_playlist_id)
            self.log(f"   Existing playlist has {len(existing_track_ids)} tracks")
        else:
            # Create new TIDAL playlist
            self.log(f"Creating new TIDAL playlist...")
            tidal_playlist_id = self.create_tidal_playlist(
                name,
                f"Transferred from Spotify - {len(spotify_tracks)} tracks - {datetime.now().strftime('%Y-%m-%d')}"
            )
            existing_track_ids = set()

            if not tidal_playlist_id:
                return {"status": "error", "reason": "playlist_creation_failed"}

            self.log(f"✅ Created TIDAL playlist (ID: {tidal_playlist_id})")

            # Add to cache
            self.tidal_playlist_cache[name] = {"id": tidal_playlist_id, "track_ids": set()}

        # Update checkpoint with TIDAL playlist ID
        checkpoint_entry["tidal_playlist_id"] = tidal_playlist_id
        checkpoint_entry["status"] = "in_progress"
        self.checkpoint["playlists"][spotify_id] = checkpoint_entry
        self.save_checkpoint()

        # Determine resume point
        start_index = checkpoint_entry.get("tracks_processed", 0)
        if start_index > 0:
            self.log(f"📍 Resuming from track {start_index + 1}/{len(spotify_tracks)}")

        # Search and add tracks with progress bar
        tidal_track_ids = []
        found_count = checkpoint_entry.get("tracks_found", 0)
        not_found_count = checkpoint_entry.get("tracks_not_found", 0)
        skipped_count = 0

        # Create progress bar for tracks
        track_pbar = tqdm(
            enumerate(spotify_tracks[start_index:], start_index + 1),
            total=len(spotify_tracks) - start_index,
            desc=f"  Tracks",
            unit="track",
            position=1,
            leave=False
        )

        for idx, track in track_pbar:
            track_name = track['name']
            artist_name = track['artists'][0] if track['artists'] else "Unknown"

            track_pbar.set_postfix({
                "found": found_count,
                "missing": not_found_count,
                "skipped": skipped_count
            })

            tidal_track_id = self.search_tidal_track(track_name, artist_name, throttle)

            if tidal_track_id:
                tidal_id_str = str(tidal_track_id)
                # Skip if already in playlist
                if tidal_id_str in existing_track_ids:
                    skipped_count += 1
                    self.log(f"    ⏭️  Already in playlist: {artist_name} - {track_name}", False)
                else:
                    tidal_track_ids.append(tidal_id_str)
                    found_count += 1
            else:
                not_found_count += 1
                self.log(f"    ❌ Not found: {artist_name} - {track_name}", False)

            # Add in batches of 50
            if len(tidal_track_ids) >= 50:
                self.log(f"  Adding batch of {len(tidal_track_ids)} tracks...", False)
                success = self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)
                if success:
                    # Update checkpoint after successful batch
                    existing_track_ids.update(tidal_track_ids)
                    checkpoint_entry["tracks_processed"] = idx
                    checkpoint_entry["tracks_found"] = found_count
                    checkpoint_entry["tracks_not_found"] = not_found_count
                    self.checkpoint["playlists"][spotify_id] = checkpoint_entry
                    self.save_checkpoint()
                else:
                    self.log(f"  ⚠️  Batch add failed, retrying...", False)
                    time.sleep(5)
                    self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)
                tidal_track_ids = []

        track_pbar.close()

        # Add remaining tracks
        if tidal_track_ids:
            self.log(f"  Adding final batch of {len(tidal_track_ids)} tracks...")
            self.add_tracks_to_tidal_playlist(tidal_playlist_id, tidal_track_ids)

        # Mark playlist as completed
        checkpoint_entry["status"] = "completed"
        checkpoint_entry["tracks_processed"] = len(spotify_tracks)
        checkpoint_entry["tracks_found"] = found_count
        checkpoint_entry["tracks_not_found"] = not_found_count
        self.checkpoint["playlists"][spotify_id] = checkpoint_entry
        self.save_checkpoint()

        match_rate = found_count / len(spotify_tracks) * 100 if spotify_tracks else 0
        self.log(f"\n✅ Completed: {name}")
        self.log(f"   Found: {found_count}/{len(spotify_tracks)} ({match_rate:.1f}%)")
        self.log(f"   Not found: {not_found_count}")
        if skipped_count:
            self.log(f"   Skipped (already in playlist): {skipped_count}")

        self.stats["total_tracks_found"] += found_count
        self.stats["total_tracks_not_found"] += not_found_count

        return {
            "status": "completed",
            "name": name,
            "total": len(spotify_tracks),
            "found": found_count,
            "not_found": not_found_count,
            "skipped": skipped_count
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

        # Build TIDAL playlist cache for duplicate detection
        self.build_tidal_playlist_cache()

        # Get Spotify user ID for checkpoint validation
        spotify_user_id = self.spotify.current_user()['id']

        # Check for existing checkpoint
        if not self.fresh_start:
            self.checkpoint = self.load_checkpoint()

        if self.checkpoint:
            # Validate checkpoint matches current user
            if self.checkpoint.get("spotify_user_id") != spotify_user_id:
                self.log(f"WARNING: Checkpoint is for different Spotify user!")
                self.log(f"  Checkpoint user: {self.checkpoint.get('spotify_user_id')}")
                self.log(f"  Current user: {spotify_user_id}")
                self.log("Starting fresh transfer...")
                self.checkpoint = None
            else:
                completed_count = sum(1 for p in self.checkpoint["playlists"].values() if p["status"] == "completed")
                total_count = self.checkpoint["total_playlists"]
                self.log(f"\n📂 Resuming from checkpoint: {completed_count}/{total_count} playlists completed")
                self.log(f"   Checkpoint created: {self.checkpoint.get('created_at', 'unknown')}")

        # Get playlists
        playlists = self.get_all_spotify_playlists()
        if not playlists:
            self.log("No playlists to transfer")
            return

        # Initialize checkpoint if needed
        if not self.checkpoint:
            self.log("\n📝 Creating new checkpoint...")
            self.init_checkpoint(playlists, spotify_user_id)

        self.log(f"\nStarting transfer of {len(playlists)} playlists...")
        if self.sync_only:
            self.log("🔄 SYNC MODE: Only processing playlists with new tracks")
        self.log(f"Using 1.5s throttle between track searches")
        self.log(f"Progress is saved after each batch - safe to interrupt with Ctrl+C")

        results = []

        # Use tqdm for overall playlist progress
        playlist_pbar = tqdm(playlists, desc="Overall progress", unit="playlist", position=0)
        for idx, playlist in enumerate(playlist_pbar, 1):
            spotify_id = playlist['id']

            # Check if already completed in checkpoint
            checkpoint_entry = self.checkpoint["playlists"].get(spotify_id, {})
            if checkpoint_entry.get("status") == "completed":
                self.log(f"\n⏭️  Skipping already completed: {playlist['name']}")
                self.stats["playlists_processed"] += 1
                continue

            # In sync mode, skip playlists that are already fully synced
            if self.sync_only and self.is_playlist_synced(playlist):
                tidal_info = self.tidal_playlist_cache.get(playlist['name'], {})
                tidal_count = tidal_info.get("track_count", "?")
                self.log(f"\n✅ Already synced: {playlist['name']} (Spotify: {playlist['tracks']['total']}, TIDAL: {tidal_count})")
                self.stats["playlists_already_synced"] += 1
                # Mark as completed in checkpoint so we don't check again
                checkpoint_entry["status"] = "completed"
                checkpoint_entry["name"] = playlist['name']
                self.checkpoint["playlists"][spotify_id] = checkpoint_entry
                self.save_checkpoint()
                continue

            playlist_pbar.set_description(f"Playlist {idx}/{len(playlists)}: {playlist['name'][:30]}")
            result = self.transfer_playlist(playlist, throttle=1.5)
            results.append(result)
            self.stats["playlists_processed"] += 1

            # Brief pause between playlists
            if idx < len(playlists):
                time.sleep(5)

        playlist_pbar.close()

        # Mark transfer as complete
        self.checkpoint["status"] = "completed"
        self.save_checkpoint()

        # Clear checkpoint (archives it)
        self.clear_checkpoint()

        # Final summary
        elapsed = datetime.now() - self.stats["start_time"]

        self.log("\n" + "="*80)
        self.log("TRANSFER COMPLETE")
        self.log("="*80)
        self.log(f"Time elapsed: {elapsed}")
        self.log(f"Playlists processed: {self.stats['playlists_processed']}")
        if self.stats['playlists_already_synced'] > 0:
            self.log(f"Playlists already synced (skipped): {self.stats['playlists_already_synced']}")
        self.log(f"Total tracks found: {self.stats['total_tracks_found']}")
        self.log(f"Total tracks not found: {self.stats['total_tracks_not_found']}")

        completed = [r for r in results if r["status"] == "completed"]
        if completed:
            self.log("\n✅ Successfully transferred:")
            for r in completed:
                self.log(f"   - {r['name']}: {r['found']}/{r['total']} tracks")

        self.log(f"\nFull log saved to: {self.log_file}")


def show_checkpoint_status(checkpoint_file: str):
    """Display the current checkpoint status and exit."""
    if not os.path.exists(checkpoint_file):
        print("No checkpoint file found. No transfer in progress.")
        return

    try:
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            checkpoint = json.load(f)

        print("\n" + "="*60)
        print("CHECKPOINT STATUS")
        print("="*60)
        print(f"Created: {checkpoint.get('created_at', 'unknown')}")
        print(f"Updated: {checkpoint.get('updated_at', 'unknown')}")
        print(f"Spotify User: {checkpoint.get('spotify_user_id', 'unknown')}")
        print(f"Status: {checkpoint.get('status', 'unknown')}")

        playlists = checkpoint.get("playlists", {})
        completed = sum(1 for p in playlists.values() if p.get("status") == "completed")
        in_progress = sum(1 for p in playlists.values() if p.get("status") == "in_progress")
        pending = sum(1 for p in playlists.values() if p.get("status") == "pending")

        print(f"\nPlaylists: {len(playlists)} total")
        print(f"  ✅ Completed: {completed}")
        print(f"  🔄 In Progress: {in_progress}")
        print(f"  ⏳ Pending: {pending}")

        total_found = sum(p.get("tracks_found", 0) for p in playlists.values())
        total_not_found = sum(p.get("tracks_not_found", 0) for p in playlists.values())
        print(f"\nTracks processed: {total_found + total_not_found}")
        print(f"  Found: {total_found}")
        print(f"  Not found: {total_not_found}")

        # Show in-progress playlist details
        for name, entry in playlists.items():
            if entry.get("status") == "in_progress":
                print(f"\n📍 Currently in progress: {entry.get('name', 'unknown')}")
                print(f"   Tracks processed: {entry.get('tracks_processed', 0)}")
                break

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error reading checkpoint file: {e}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Transfer Spotify playlists to TIDAL with resume support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python spotify_to_tidal_transfer.py           # Auto-resume if checkpoint exists
  python spotify_to_tidal_transfer.py --sync    # Only sync playlists with new tracks
  python spotify_to_tidal_transfer.py --fresh   # Ignore checkpoint, start fresh
  python spotify_to_tidal_transfer.py --status  # Show checkpoint status
  python spotify_to_tidal_transfer.py --reset   # Delete checkpoint and exit
        """
    )
    parser.add_argument(
        '--sync', action='store_true',
        help='Sync mode: only process playlists that have new tracks (skip fully synced)'
    )
    parser.add_argument(
        '--fresh', action='store_true',
        help='Start fresh, ignore existing checkpoint'
    )
    parser.add_argument(
        '--checkpoint-file', default='transfer_checkpoint.json',
        help='Path to checkpoint file (default: transfer_checkpoint.json)'
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Show checkpoint status and exit'
    )
    parser.add_argument(
        '--reset', action='store_true',
        help='Delete checkpoint file and exit'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.status:
        show_checkpoint_status(args.checkpoint_file)
        exit(0)

    if args.reset:
        if os.path.exists(args.checkpoint_file):
            os.remove(args.checkpoint_file)
            print(f"Checkpoint file '{args.checkpoint_file}' deleted.")
        else:
            print("No checkpoint file found.")
        exit(0)

    print("\n" + "="*80)
    print("Spotify to TIDAL Playlist Transfer")
    print("="*80)

    if args.sync:
        print("\n🔄 SYNC MODE: Only processing playlists with new tracks")
    elif args.fresh:
        print("\n⚠️  Starting fresh (ignoring any existing checkpoint)")
    else:
        print("\n📂 Will resume from checkpoint if available")

    transfer = SpotifyToTidalTransfer(
        checkpoint_file=args.checkpoint_file,
        fresh_start=args.fresh,
        sync_only=args.sync
    )
    transfer.run()
