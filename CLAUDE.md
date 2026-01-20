# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python utility for transferring Spotify playlists to TIDAL with automatic resume support, duplicate prevention, and progress tracking.

## Commands

```bash
# Install dependencies
pip install tidalapi spotipy tqdm python-dotenv

# Run transfer (auto-resumes from checkpoint)
python spotify_to_tidal_transfer.py

# CLI options
python spotify_to_tidal_transfer.py --fresh   # Ignore checkpoint
python spotify_to_tidal_transfer.py --status  # Show progress
python spotify_to_tidal_transfer.py --reset   # Delete checkpoint
```

## Configuration

Spotify credentials are loaded from `.env` file (see `.env.example`):
```
SPOTIFY_CLIENT_ID=your_id
SPOTIFY_CLIENT_SECRET=your_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:47281/callback
```

## Architecture

Single file `spotify_to_tidal_transfer.py` with `SpotifyToTidalTransfer` class:

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

## State Files

| File | Purpose | Git |
|------|---------|-----|
| `.env` | Spotify credentials | ignored |
| `tidal_session.json` | TIDAL auth cache | ignored |
| `transfer_checkpoint.json` | Transfer progress | ignored |
| `transfer_log_*.txt` | Execution logs | ignored |

## API Rate Limiting

- 1.5s between track searches
- 3s after batch uploads
- 5s between playlists
