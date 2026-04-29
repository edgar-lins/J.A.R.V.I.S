"""
Autenticação Spotify manual — sem servidor local.
Uso: python scripts/spotify_auth.py
"""
import sys
import os
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import get_settings
import spotipy
from spotipy.oauth2 import SpotifyOAuth

settings = get_settings()

_SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "streaming",
])
_REDIRECT_URI = "https://open.spotify.com"

auth = SpotifyOAuth(
    client_id=settings.spotify_client_id,
    client_secret=settings.spotify_client_secret,
    redirect_uri=_REDIRECT_URI,
    scope=_SCOPES,
    cache_path=".spotify_token",
    open_browser=False,
)

url = auth.get_authorize_url()
print("\nAbrindo browser para autenticação Spotify...")
webbrowser.open(url)

print("\nDepois de autorizar, você será redirecionado para open.spotify.com.")
print("Copia a URL completa do browser (começa com https://open.spotify.com?code=...)")
print()
redirect_url = input("Cola a URL aqui: ").strip()

code = auth.parse_response_code(redirect_url)
auth.get_access_token(code, as_dict=False)

sp = spotipy.Spotify(auth_manager=auth)
user = sp.current_user()
print(f"\nAutenticado como: {user['display_name']}")
print("Token salvo. Pode fechar.\n")
