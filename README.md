# Spotify to TIDAL Playlist Transfer

Transfer all your Spotify playlists to TIDAL with automatic resume support and cross-platform library tracking.

## Features

- Transfers all owned playlists and tracks
- **Auto-resume**: Safe to interrupt with Ctrl+C, progress is saved
- **Duplicate prevention**: Detects existing TIDAL playlists by name
- **Music Library**: CSV-based tracking of all tracks across platforms
- **Exact sync detection**: Knows exactly which tracks need syncing
- **Daily sync**: Cron job with Obsidian notifications
- **Unavailable track reports**: Exports tracks not found on TIDAL
- **Future-ready**: Architecture supports SoundCloud and other platforms

## Quick Start

```bash
# 1. Create virtual environment
uv venv && source .venv/bin/activate
uv pip install tidalapi spotipy tqdm python-dotenv

# 2. Configure Spotify credentials
cp .env.example .env
# Edit .env with your Spotify API credentials

# 3. Run the transfer
python spotify_to_tidal_transfer.py
```

Get Spotify credentials from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

## Usage

```bash
python spotify_to_tidal_transfer.py              # Full transfer (auto-resumes)
python spotify_to_tidal_transfer.py --sync       # Only sync new tracks
python spotify_to_tidal_transfer.py --status     # Show checkpoint progress
python spotify_to_tidal_transfer.py --library    # Show library stats
python spotify_to_tidal_transfer.py --export     # Export unavailable tracks
python spotify_to_tidal_transfer.py --fresh      # Ignore checkpoint
python spotify_to_tidal_transfer.py --reset      # Delete checkpoint
```

## Directory Structure

```
spoti_tidal/
├── spotify_to_tidal_transfer.py   # Main transfer script
├── library_manager.py             # Cross-platform track library
├── daily_sync.py                  # Daily cron job with Obsidian logging
├── .env                           # Spotify credentials (not in git)
├── data/                          # Runtime data (not in git)
│   ├── tidal_session.json         # TIDAL auth cache
│   ├── checkpoint.json            # Transfer progress
│   └── library.csv                # Cross-platform track database
├── logs/                          # Logs (not in git)
│   ├── transfer_log_*.txt         # Transfer logs
│   └── cron.log                   # Daily sync log
└── docs/                          # Documentation
    └── SETUP_INSTRUCTIONS.md      # Detailed setup guide
```

## Daily Sync

Runs automatically at 6 PM via cron, appends results to your Obsidian daily log:

```markdown
### 🎵 Spotify-TIDAL Sync (18:00)
**Synced 2 playlist(s):**
  - New Playlist: 45/50 tracks
**New tracks added (3):**
  - Daft Punk - Around The World
  - Kraftwerk - Trans-Europe Express
```

Manual run: `python daily_sync.py` or `python daily_sync.py --dry`

## Notes

- Only transfers playlists you own (not followed playlists)
- ~85-95% track match rate (some tracks aren't on TIDAL)
- Uses throttling to avoid API rate limits (1.5s between searches)
- Full transfer of ~30 playlists takes 2-4 hours
