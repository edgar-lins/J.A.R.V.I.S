import httpx
from config import get_settings

settings = get_settings()

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def search(query: str, count: int = 5) -> str:
    """Busca na web via Brave Search e retorna resultados formatados."""
    if not settings.brave_api_key:
        return "Brave Search não configurado. Adicione BRAVE_API_KEY no .env."

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count}

    try:
        resp = httpx.get(_BRAVE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"Erro na busca: {e}"

    results = data.get("web", {}).get("results", [])
    if not results:
        return "Nenhum resultado encontrado."

    lines = [f"Resultados para: {query}\n"]
    for r in results:
        title = r.get("title", "")
        url   = r.get("url", "")
        desc  = r.get("description", "")
        lines.append(f"**{title}**\n{desc}\nFonte: {url}\n")

    return "\n".join(lines)
