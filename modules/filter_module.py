import json
import os

FILTER_FILE = "filtered_words.json"

# This is the "Source of Truth". Other files will import this variable.
filtered_words = {}

def load_filtered_words():
    """Loads JSON data into the global filtered_words dictionary."""
    global filtered_words
    if os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, "r") as f:
                # Update the existing dictionary instead of replacing the reference
                data = json.load(f)
                filtered_words.update(data)
                print(f"Loaded filter list for {len(filtered_words)} guilds.")
        except Exception as e:
            print(f"Error loading filters: {e}")
    else:
        print("No filter file found, starting fresh.")

def save_filtered_words():
    """Saves the current state of filtered_words to JSON."""
    try:
        with open(FILTER_FILE, "w") as f:
            json.dump(filtered_words, f, indent=4)
    except Exception as e:
        print(f"Error saving filters: {e}")