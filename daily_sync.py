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
        "success": result.returncode == 0
    }

    for line in output.split('\n'):
        if "Already synced:" in line:
            stats["playlists_skipped"] += 1
        elif "Successfully transferred:" in line:
            # Next lines contain playlist names
            pass
        elif "- " in line and ":" in line and "tracks" in line:
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

    if stats["new_playlists"]:
        playlist_lines = "\n".join(f"  - {p}" for p in stats["new_playlists"])
        return f"""
### 🎵 Spotify-TIDAL Sync ({now})
**Synced {stats['playlists_synced']} playlist(s):**
{playlist_lines}

Tracks: {stats['tracks_found']} found, {stats['tracks_not_found']} unavailable on TIDAL
"""

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
            "new_playlists": ["New Playlist: 45/50 tracks", "Updated Mix: 44/50 tracks"]
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
