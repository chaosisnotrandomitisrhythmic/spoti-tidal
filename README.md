# Spotify to TIDAL Playlist Transfer

Transfer all your Spotify playlists to TIDAL with automatic resume support and cross-platform library tracking.

## Features

- Transfers all owned playlists and tracks
- **Auto-resume**: Safe to interrupt with Ctrl+C, progress is saved
- **Duplicate prevention**: Detects existing TIDAL playlists by name
- **Music Library**: CSV-based tracking of all tracks across platforms
- **Exact sync detection**: Knows exactly which tracks need syncing (not just percentage-based)
- **Unavailable track reports**: Exports tracks not found on TIDAL
- **Progress bars**: Visual feedback during transfer
- **Future-ready**: Architecture supports SoundCloud and other platforms
- Detailed logging to file

## Quick Start

1. **Create virtual environment and install dependencies**
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install tidalapi spotipy tqdm python-dotenv
   ```

2. **Configure Spotify credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your Spotify API credentials
   ```

   Get credentials from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard):
   - Create an app
   - Copy Client ID and Client Secret to `.env`
   - Add redirect URI: `http://127.0.0.1:47281/callback`

3. **Run the transfer**
   ```bash
   source .venv/bin/activate
   python spotify_to_tidal_transfer.py
   ```

## Usage

```bash
# Standard run (auto-resumes if interrupted)
python spotify_to_tidal_transfer.py

# Sync mode - only process playlists with new tracks (exact track matching)
python spotify_to_tidal_transfer.py --sync

# Start fresh, ignore existing checkpoint
python spotify_to_tidal_transfer.py --fresh

# Check transfer progress
python spotify_to_tidal_transfer.py --status

# View music library statistics
python spotify_to_tidal_transfer.py --library

# Export tracks not available on TIDAL to CSV
python spotify_to_tidal_transfer.py --export

# Delete checkpoint and start over
python spotify_to_tidal_transfer.py --reset
```

## How It Works

1. Authenticates with Spotify (browser OAuth) and TIDAL (device code)
2. Fetches all your owned Spotify playlists
3. For each playlist:
   - Checks if it already exists on TIDAL
   - Searches for each track on TIDAL
   - Adds found tracks in batches of 50
   - Saves progress after each batch

## Files Created

| File | Purpose |
|------|---------|
| `music_library.csv` | Cross-platform track database (persistent) |
| `transfer_checkpoint.json` | Progress state (auto-deleted on completion) |
| `tidal_session.json` | TIDAL auth session cache |
| `unavailable_on_tidal.csv` | Tracks not found on TIDAL |
| `transfer_log_*.txt` | Detailed transfer log |

## Music Library

The `music_library.csv` tracks every song across all platforms:

```csv
spotify_id,tidal_id,track_name,artist_name,spotify_available,tidal_available,last_synced
4iV5W9uYEdYUVa79Axb7Rh,12345678,Circles,Post Malone,True,True,2024-01-15T10:30:00
3n3Ppam7vgaVa1iaRUc9Lp,,Mr. Brightside,The Killers,True,False,2024-01-15T10:31:00
```

### Benefits
- **Exact sync detection**: Knows precisely which tracks are synced vs. missing
- **No duplicate searches**: Remembers tracks that aren't on TIDAL
- **Cross-platform ready**: Architecture supports Spotify, TIDAL, SoundCloud
- **Exportable reports**: Generate lists of unavailable tracks

## Notes

- Only transfers playlists you own (not followed playlists)
- Not all Spotify tracks may be available on TIDAL (~85-95% match rate)
- Uses throttling to avoid API rate limits (1.5s between searches)
- Full transfer of ~30 playlists takes 2-4 hours
