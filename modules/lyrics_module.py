import json
import os

LYRICS_FILE = "lyrics_settings.json"

# This is the "Source of Truth". Other files will import this variable.
lyrics_enabled = {}   # {guild_id: True/False}

def load_lyrics_settings():
    """Loads JSON data into the global lyrics_enabled dictionary."""
    global lyrics_enabled
    if os.path.exists(LYRICS_FILE):
        try:
            with open(LYRICS_FILE, "r") as f:
                data = json.load(f)
                lyrics_enabled.update(data)
                print(f"Loaded lyrics settings for {len(lyrics_enabled)} guilds.")
        except Exception as e:
            print(f"Error loading lyrics settings: {e}")
    else:
        print("No lyrics settings file found, starting fresh.")

def save_lyrics_settings():
    """Saves the current state of lyrics_enabled to JSON."""
    try:
        with open(LYRICS_FILE, "w") as f:
            json.dump(lyrics_enabled, f, indent=4)
    except Exception as e:
        print(f"Error saving lyrics settings: {e}")
