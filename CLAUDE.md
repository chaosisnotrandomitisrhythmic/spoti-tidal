# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python utility for transferring Spotify playlists to TIDAL with:
- Automatic resume support
- Cross-platform music library tracking (CSV-based)
- Exact sync detection (track-by-track, not percentage-based)
- Duplicate prevention
- Progress tracking

## Commands

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install tidalapi spotipy tqdm python-dotenv

# Run transfer (auto-resumes from checkpoint)
python spotify_to_tidal_transfer.py

# CLI options
python spotify_to_tidal_transfer.py --sync     # Only sync playlists with new tracks (exact matching)
python spotify_to_tidal_transfer.py --fresh    # Ignore checkpoint
python spotify_to_tidal_transfer.py --status   # Show checkpoint progress
python spotify_to_tidal_transfer.py --library  # Show music library stats
python spotify_to_tidal_transfer.py --export   # Export unavailable tracks to CSV
python spotify_to_tidal_transfer.py --reset    # Delete checkpoint
```

## Configuration

Spotify credentials are loaded from `.env` file (see `.env.example`):
```
SPOTIFY_CLIENT_ID=your_id
SPOTIFY_CLIENT_SECRET=your_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:47281/callback
```

## Architecture

### Files

| File | Purpose |
|------|---------|
| `spotify_to_tidal_transfer.py` | Main transfer script |
| `library_manager.py` | Cross-platform track library management |
| `daily_sync.py` | Cron job for daily sync with Obsidian logging |

### Directory Structure

```
data/           # Runtime data (gitignored)
├── tidal_session.json
├── checkpoint.json
└── library.csv

logs/           # Logs (gitignored)
├── transfer_log_*.txt
└── cron.log

docs/           # Documentation
└── SETUP_INSTRUCTIONS.md
```

### SpotifyToTidalTransfer Class

**Authentication**
- `setup_spotify()` - OAuth via browser redirect
- `setup_tidal()` - Device code flow, caches session

**Checkpoint/Resume** (saves after every 50 tracks)
- `load_checkpoint()` / `save_checkpoint()` / `clear_checkpoint()`
- `init_checkpoint()` - Creates new checkpoint for transfer

**Duplicate Prevention**
- `build_tidal_playlist_cache()` - Caches existing TIDAL playlists
- `find_tidal_playlist_by_name()` - Finds existing playlist to reuse
- `get_tidal_playlist_track_ids()` - Gets tracks already in playlist

**Transfer**
- `transfer_playlist()` - Main per-playlist logic with resume support
- `run()` - Orchestrates full transfer

### LibraryManager Class

Cross-platform track tracking via CSV:

**Core Methods**
- `add_track()` - Register a track from Spotify
- `set_tidal_id()` - Record TIDAL match result
- `set_soundcloud_id()` - Record SoundCloud match (future)
- `save_library()` - Atomic CSV write

**Query Methods**
- `get_track()` - Get track by Spotify ID
- `get_tracks_for_playlist()` - All tracks in a playlist
- `get_unsynced_tracks_for_playlist()` - Tracks needing sync
- `is_playlist_synced()` - Exact sync check (track-by-track)
- `get_unavailable_tracks()` - Tracks not on a platform
- `get_sync_stats()` - Statistics for library or playlist

**Library CSV Schema**
```csv
spotify_id,tidal_id,soundcloud_id,track_name,artist_name,album_name,playlist_ids,spotify_available,tidal_available,soundcloud_available,last_synced,notes
```

## State Files

| File | Purpose | Git |
|------|---------|-----|
| `.env` | Spotify credentials | ignored |
| `data/tidal_session.json` | TIDAL auth cache | ignored |
| `data/checkpoint.json` | Transfer progress | ignored |
| `data/library.csv` | Cross-platform track database | ignored |
| `logs/*.txt` | Execution logs | ignored |

## API Rate Limiting

- 1.5s between track searches
- 3s after batch uploads
- 5s between playlists

## Future Expansion

The library architecture supports adding more platforms:
- SoundCloud (`soundcloud_id`, `soundcloud_available`)
- Other platforms can be added by extending the CSV schema
