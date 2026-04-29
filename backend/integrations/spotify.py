import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import get_settings

settings = get_settings()

_SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "streaming",
])
_CACHE_PATH = ".spotify_token"
_REDIRECT_URI = "https://open.spotify.com"


def _client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=_REDIRECT_URI,
        scope=_SCOPES,
        cache_path=_CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth)


def is_authenticated() -> bool:
    try:
        token = SpotifyOAuth(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=_REDIRECT_URI,
            scope=_SCOPES,
            cache_path=_CACHE_PATH,
            open_browser=False,
        ).get_cached_token()
        return token is not None and not SpotifyOAuth.is_token_expired(token)
    except Exception:
        return False


def get_auth_url() -> str:
    auth = SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=_REDIRECT_URI,
        scope=_SCOPES,
        cache_path=_CACHE_PATH,
        open_browser=False,
    )
    return auth.get_authorize_url()


def exchange_code(code: str) -> None:
    auth = SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=_REDIRECT_URI,
        scope=_SCOPES,
        cache_path=_CACHE_PATH,
        open_browser=False,
    )
    auth.get_access_token(code)


def _active_device_id() -> str | None:
    devices = _client().devices()
    items = devices.get("devices", [])
    if not items:
        return None
    active = next((d for d in items if d["is_active"]), None)
    return (active or items[0])["id"]


def play(query: str) -> str:
    sp = _client()
    device_id = _active_device_id()
    if not device_id:
        return "Nenhum dispositivo Spotify ativo. Abre o Spotify em algum device primeiro."

    results = sp.search(q=query, limit=1, type="track,artist,playlist,album")

    # tenta nessa ordem: track > playlist > album > artist
    for kind in ("tracks", "playlists", "albums", "artists"):
        items = results.get(kind, {}).get("items", [])
        if not items:
            continue
        item = items[0]
        uri  = item["uri"]
        name = item.get("name", "")

        if kind == "tracks":
            sp.start_playback(device_id=device_id, uris=[uri])
        elif kind == "artists":
            sp.start_playback(device_id=device_id, context_uri=uri)
        else:
            sp.start_playback(device_id=device_id, context_uri=uri)

        return f"Tocando: {name}"

    return f"Nada encontrado para '{query}'."


def pause() -> str:
    try:
        _client().pause_playback()
        return "Pausado."
    except spotipy.SpotifyException as e:
        return f"Erro ao pausar: {e}"


def resume() -> str:
    try:
        _client().start_playback()
        return "Retomado."
    except spotipy.SpotifyException as e:
        return f"Erro ao retomar: {e}"


def next_track() -> str:
    try:
        _client().next_track()
        return "Próxima faixa."
    except spotipy.SpotifyException as e:
        return f"Erro: {e}"


def previous_track() -> str:
    try:
        _client().previous_track()
        return "Faixa anterior."
    except spotipy.SpotifyException as e:
        return f"Erro: {e}"


def set_volume(level: int) -> str:
    try:
        _client().volume(max(0, min(100, level)))
        return f"Volume em {level}%."
    except spotipy.SpotifyException as e:
        return f"Erro: {e}"


def now_playing() -> str:
    current = _client().current_playback()
    if not current or not current.get("item"):
        return "Nada tocando no momento."
    item    = current["item"]
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    title   = item.get("name", "")
    paused  = not current.get("is_playing", True)
    status  = " (pausado)" if paused else ""
    return f"{title} — {artists}{status}"
