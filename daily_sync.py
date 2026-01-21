#!/usr/bin/env python3
"""
Daily Spotify-TIDAL Sync

Runs sync and appends results to today's Obsidian daily log.
Designed to run via cron once a day.

Usage:
    python daily_sync.py          # Run sync and log to Obsidian
    python daily_sync.py --dry    # Show what would be logged without syncing
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
OBSIDIAN_LOGS = Path.home() / "Documents/obsedian/chaos_isrhythmic/Scanner Daybook/Daily Logs"

def get_todays_log_path() -> Path:
    """Get path to today's daily log file."""
    today = datetime.now()
    return OBSIDIAN_LOGS / str(today.year) / f"{today.month:02d}" / f"{today.strftime('%Y-%m-%d')}.md"

def run_sync() -> dict:
    """Run the sync and capture results."""
    os.chdir(SCRIPT_DIR)

    # Activate venv and run sync
    result = subprocess.run(
        ["bash", "-c", "source .venv/bin/activate && python spotify_to_tidal_transfer.py --sync"],
        capture_output=True,
        text=True,
        cwd=SCRIPT_DIR
    )

    output = result.stdout + result.stderr

    # Parse results
    stats = {
        "playlists_synced": 0,
        "playlists_skipped": 0,
        "tracks_found": 0,
        "tracks_not_found": 0,
        "new_playlists": [],
        "new_tracks": [],  # Track names that were added
        "success": result.returncode == 0
    }

    current_playlist = None
    for line in output.split('\n'):
        if "Already synced:" in line:
            stats["playlists_skipped"] += 1
        elif "Processing:" in line:
            # Extract playlist name: "Processing: Playlist Name (50 tracks)"
            try:
                current_playlist = line.split("Processing:")[1].split("(")[0].strip()
            except:
                pass
        elif "Successfully transferred:" in line:
            # Next lines contain playlist names
            pass
        elif "- " in line and ":" in line and "tracks" in line and not line.strip().startswith("⏭"):
            # Format: "   - Playlist Name: 45/50 tracks"
            playlist_info = line.strip().lstrip("- ")
            stats["new_playlists"].append(playlist_info)
            stats["playlists_synced"] += 1
        elif "Total tracks found:" in line:
            try:
                stats["tracks_found"] = int(line.split(":")[-1].strip())
            except:
                pass
        elif "Total tracks not found:" in line:
            try:
                stats["tracks_not_found"] = int(line.split(":")[-1].strip())
            except:
                pass
        # Capture added tracks (not skipped, not "not found")
        elif "Already in playlist:" not in line and "Not found:" not in line and "Not on TIDAL" not in line:
            # Look for successful track additions in the log
            pass

    # Parse the log file for actual track names added
    log_files = sorted(SCRIPT_DIR.glob("transfer_log_*.txt"), reverse=True)
    if log_files:
        latest_log = log_files[0]
        try:
            with open(latest_log, 'r') as f:
                log_content = f.read()

            # Find tracks that were found (not skipped, not "not found")
            for line in log_content.split('\n'):
                # Skip lines about tracks not found or already in playlist
                if any(skip in line for skip in ["Not found:", "Already in playlist:", "Not on TIDAL", "❌", "⏭️"]):
                    continue
                # We need a different approach - check the library for recently synced tracks
        except:
            pass

    # Get recently synced tracks from library
    try:
        from library_manager import LibraryManager
        from datetime import datetime, timedelta

        lib = LibraryManager(SCRIPT_DIR / "music_library.csv")
        now = datetime.now()
        recent_cutoff = now - timedelta(hours=1)  # Tracks synced in the last hour

        for track in lib.tracks.values():
            last_synced = track.get('last_synced', '')
            if last_synced and track.get('tidal_available') is True:
                try:
                    sync_time = datetime.fromisoformat(last_synced)
                    if sync_time > recent_cutoff:
                        artist = track.get('artist_name', 'Unknown')
                        name = track.get('track_name', 'Unknown')
                        stats["new_tracks"].append(f"{artist} - {name}")
                except:
                    pass
    except Exception as e:
        print(f"Could not read library: {e}")

    return stats

def format_obsidian_entry(stats: dict) -> str:
    """Format sync results for Obsidian."""
    now = datetime.now().strftime("%H:%M")

    if not stats["new_playlists"] and stats["playlists_skipped"] > 0:
        # Nothing new to sync
        return f"""
### 🎵 Spotify-TIDAL Sync ({now})
All {stats['playlists_skipped']} playlists already synced. No changes.
"""

    if stats["new_playlists"] or stats["new_tracks"]:
        lines = [f"### 🎵 Spotify-TIDAL Sync ({now})"]

        if stats["new_playlists"]:
            lines.append(f"**Synced {stats['playlists_synced']} playlist(s):**")
            for p in stats["new_playlists"]:
                lines.append(f"  - {p}")

        if stats["new_tracks"]:
            lines.append("")
            lines.append(f"**New tracks added ({len(stats['new_tracks'])}):**")
            # Show up to 15 tracks, then summarize
            for track in stats["new_tracks"][:15]:
                lines.append(f"  - {track}")
            if len(stats["new_tracks"]) > 15:
                lines.append(f"  - *...and {len(stats['new_tracks']) - 15} more*")

        lines.append("")
        lines.append(f"Tracks: {stats['tracks_found']} found, {stats['tracks_not_found']} unavailable on TIDAL")

        return "\n" + "\n".join(lines) + "\n"

    # Fallback
    return f"""
### 🎵 Spotify-TIDAL Sync ({now})
Sync completed. Playlists checked: {stats['playlists_skipped'] + stats['playlists_synced']}
"""

def append_to_daily_log(entry: str):
    """Append entry to today's Obsidian daily log."""
    log_path = get_todays_log_path()

    # Create directory if needed
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if not log_path.exists():
        # Create minimal daily log if it doesn't exist
        with open(log_path, 'w') as f:
            f.write(f"# {datetime.now().strftime('%Y-%m-%d')} - Daily Scanner Log\n\n")
            f.write("#daily-log\n")

    # Read current content
    with open(log_path, 'r') as f:
        content = f.read()

    # Insert before #daily-log tag or append at end
    if "#daily-log" in content:
        content = content.replace("#daily-log", entry.strip() + "\n\n#daily-log")
    else:
        content += "\n" + entry

    with open(log_path, 'w') as f:
        f.write(content)

    print(f"Logged to: {log_path}")

def main():
    dry_run = "--dry" in sys.argv

    if dry_run:
        print("DRY RUN - would log to:", get_todays_log_path())
        print("\nSample entry:")
        sample = {
            "playlists_synced": 2,
            "playlists_skipped": 28,
            "tracks_found": 89,
            "tracks_not_found": 11,
            "new_playlists": ["New Playlist: 45/50 tracks", "Updated Mix: 44/50 tracks"],
            "new_tracks": [
                "Daft Punk - Around The World",
                "Kraftwerk - Trans-Europe Express",
                "New Order - Blue Monday"
            ]
        }
        print(format_obsidian_entry(sample))
        return

    print("Running Spotify-TIDAL sync...")
    stats = run_sync()

    entry = format_obsidian_entry(stats)
    print(entry)

    append_to_daily_log(entry)
    print("Done!")

if __name__ == "__main__":
    main()
