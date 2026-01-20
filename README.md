# Spotify to TIDAL Playlist Transfer

Transfer all your Spotify playlists to TIDAL with automatic resume support.

## Features

- Transfers all owned playlists and tracks
- **Auto-resume**: Safe to interrupt with Ctrl+C, progress is saved
- **Duplicate prevention**: Detects existing TIDAL playlists by name
- **Progress bars**: Visual feedback during transfer
- Detailed logging to file

## Quick Start

1. **Install dependencies**
   ```bash
   pip install tidalapi spotipy tqdm python-dotenv
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
   python spotify_to_tidal_transfer.py
   ```

## Usage

```bash
# Standard run (auto-resumes if interrupted)
python spotify_to_tidal_transfer.py

# Start fresh, ignore existing checkpoint
python spotify_to_tidal_transfer.py --fresh

# Check transfer progress
python spotify_to_tidal_transfer.py --status

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
| `transfer_checkpoint.json` | Progress state (auto-deleted on completion) |
| `tidal_session.json` | TIDAL auth session cache |
| `transfer_log_*.txt` | Detailed transfer log |

## Notes

- Only transfers playlists you own (not followed playlists)
- Not all Spotify tracks may be available on TIDAL (~85-95% match rate)
- Uses throttling to avoid API rate limits (1.5s between searches)
- Full transfer of ~30 playlists takes 2-4 hours
