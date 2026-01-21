# Spotify to TIDAL Playlist Transfer - Setup Guide

This script will transfer all your Spotify playlists to TIDAL, handling the full track lists with proper throttling.

## Prerequisites

1. **Python 3.7+** installed on your system
2. **Spotify Developer Account** (free)
3. **TIDAL Subscription** (required for API access)

## Step 1: Install Required Packages

Open your terminal and run:

```bash
pip install tidalapi spotipy --break-system-packages
```

Or if you prefer using pip3:

```bash
pip3 install tidalapi spotipy --break-system-packages
```

## Step 2: Get Spotify API Credentials

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click "Create an App"
4. Fill in:
   - **App name**: "Playlist Transfer" (or any name)
   - **App description**: "Transfer playlists to TIDAL"
   - Check the terms of service box
5. Click "Create"
6. You'll see your **Client ID** and **Client Secret**
7. Click "Edit Settings"
8. Under "Redirect URIs", add: `http://localhost:8888/callback`
9. Click "Add" then "Save"

## Step 3: Set Environment Variables

### On macOS/Linux:

```bash
export SPOTIFY_CLIENT_ID='your_client_id_here'
export SPOTIFY_CLIENT_SECRET='your_client_secret_here'
```

### On Windows (Command Prompt):

```cmd
set SPOTIFY_CLIENT_ID=your_client_id_here
set SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

### On Windows (PowerShell):

```powershell
$env:SPOTIFY_CLIENT_ID='your_client_id_here'
$env:SPOTIFY_CLIENT_SECRET='your_client_secret_here'
```

**Important**: Replace `your_client_id_here` and `your_client_secret_here` with your actual credentials from Step 2.

## Step 4: Run the Script

Navigate to the directory where you saved `spotify_to_tidal_complete.py` and run:

```bash
python spotify_to_tidal_complete.py
```

Or:

```bash
python3 spotify_to_tidal_complete.py
```

## Step 5: Authenticate

### Spotify Authentication:
- Your browser will open automatically
- Log in to Spotify and authorize the app
- You'll be redirected to localhost (this is normal, just close the browser)

### TIDAL Authentication:
- The script will provide a URL
- Open that URL in your browser
- Log in to TIDAL and authorize
- Return to the terminal - authentication is complete

## What Happens Next

The script will:

1. ✅ Fetch all your Spotify playlists
2. ✅ Process each playlist in order (starting with "Trip Inside This House")
3. ✅ For each track:
   - Search on TIDAL
   - Wait 1.5 seconds (throttling)
   - Collect matching tracks
4. ✅ Create TIDAL playlists with the same names
5. ✅ Add tracks in batches of 50
6. ✅ Generate a detailed log file

## Time Estimates

- **Small playlist** (10-30 tracks): ~1-2 minutes
- **Medium playlist** (50-100 tracks): ~3-5 minutes
- **Large playlist** (700+ tracks): ~20-30 minutes
- **All 30 playlists**: 2-4 hours total

The script is designed to run safely without overwhelming the APIs.

## Progress Tracking

The script will:
- Print progress updates every 10 tracks
- Show which tracks were found/not found on TIDAL
- Create a timestamped log file (e.g., `transfer_log_20260119_143000.txt`)
- Display a final summary when complete

## If Something Goes Wrong

The script includes:
- ✅ Automatic retry logic for failed batch uploads
- ✅ Detailed error logging
- ✅ Session persistence (you won't need to re-authenticate TIDAL)
- ✅ Safe continuation (you can stop and restart)

If the script fails:
1. Check the log file for errors
2. Verify your credentials are correct
3. Make sure both Spotify and TIDAL accounts are active
4. Try running again - it will skip already-created playlists

## Common Issues

### "Module not found" error
- Make sure you installed the packages: `pip install tidalapi spotipy`

### "Spotify credentials not found"
- Verify you set the environment variables correctly
- Make sure there are no quotes issues in your client ID/secret

### "TIDAL authentication failed"
- Ensure you have an active TIDAL subscription
- Try deleting `tidal_session.json` and re-authenticating

### Tracks not found on TIDAL
- This is normal - not all Spotify tracks are on TIDAL
- The script logs which tracks couldn't be found
- Typical match rate: 85-95%

## Output Files

After running, you'll have:

1. **TIDAL Playlists**: All your playlists in your TIDAL account
2. **Log File**: `transfer_log_YYYYMMDD_HHMMSS.txt` with full details
3. **Session File**: `tidal_session.json` (for faster re-authentication)

## Notes

- The script transfers playlists you **own** only (not followed playlists)
- Empty playlists are skipped automatically
- Track order is preserved
- Playlist descriptions include transfer date and track count
- You can safely stop the script (Ctrl+C) and restart - it won't duplicate playlists

## Support

If you encounter issues:
1. Check the log file for specific errors
2. Verify all prerequisites are met
3. Make sure your API credentials are correct
4. Ensure both services are accessible from your network

---

**Ready to start? Follow the steps above and enjoy your music on TIDAL! 🎵**
