import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
spotify_client_id= os.getenv("SPOTIFY_CLIENT_ID")
spotify_client_secret= os.getenv("SPOTIFY_CLIENT_SECRET")
sp_dc = os.getenv("SPOTIFY_SP_DC")
