"""
Roblox Catalog Proxy — main.py
Hosted on Render.com (Free tier)

Endpoints:
  GET /ping                         → health check (anti-sleep)
  GET /recent-ids                   → lista de IDs de accesorios recientes (usado por CatalogProxy)
  GET /search?keyword=TEXTO         → búsqueda por nombre, devuelve solo IDs
"""

from flask import Flask, jsonify, request
import requests
import time

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Cache simple en memoria
# ---------------------------------------------------------------------------
_cache: dict = {}
CACHE_TTL = 300  # 5 minutos

def _cache_get(key):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    return None

def _cache_set(key, data):
    _cache[key] = {"data": data, "expires_at": time.time() + CACHE_TTL}

# ---------------------------------------------------------------------------
# Headers — imita navegador para evitar bloqueos
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.roblox.com/",
}

# ---------------------------------------------------------------------------
# Buscar IDs en el catálogo de Roblox
# ---------------------------------------------------------------------------
def search_catalog_ids(keyword: str = "", subcategory: str = "", limit: int = 30) -> list:
    """
    Devuelve lista de asset IDs del catálogo.
    No fetchea precios — eso lo hace Roblox con GetProductInfo.
    """
    params = {
        "limit": min(limit, 30),
        "sortType": 3,  # Recently updated
        "includeNotForSale": "false",
    }
    if keyword:
        params["keyword"] = keyword
    if subcategory:
        params["subcategory"] = subcategory

    try:
        resp = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            return [item["id"] for item in data if "id" in item]
        else:
            print(f"[search_catalog_ids] HTTP {resp.status_code} subcategory={subcategory}")
    except Exception as e:
        print(f"[search_catalog_ids] error: {e}")

    return []

# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.route("/ping")
def ping():
    """Health check — llamar cada 10 min desde cron-job.org."""
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/recent-ids")
def recent_ids():
    """
    GET /recent-ids
    Devuelve lista de IDs de accesorios recientes (Hats + Accessories).
    Roblox dentro del juego fetchea los precios via GetProductInfo().
    """
    cached = _cache_get("recent-ids")
    if cached is not None:
        return jsonify(cached)

    hat_ids  = search_catalog_ids(subcategory="ClassicHats",   limit=15)
    acc_ids  = search_catalog_ids(subcategory="Accessories",   limit=15)

    # Deduplicar preservando orden
    seen = set()
    combined = []
    for id_ in hat_ids + acc_ids:
        if id_ not in seen:
            seen.add(id_)
            combined.append(id_)

    print(f"[recent-ids] {len(combined)} IDs encontrados")
    _cache_set("recent-ids", combined)
    return jsonify(combined)


@app.route("/search-ids")
def search_ids():
    """
    GET /search-ids?keyword=TEXTO&limit=20
    Busca por nombre y devuelve solo IDs.
    """
    keyword = request.args.get("keyword", "").strip()
    limit   = min(request.args.get("limit", 20, type=int), 60)

    if not keyword:
        return jsonify({"error": "Missing ?keyword=TEXTO"}), 400

    cached = _cache_get(f"search:{keyword}:{limit}")
    if cached is not None:
        return jsonify(cached)

    ids = search_catalog_ids(keyword=keyword, limit=limit)
    _cache_set(f"search:{keyword}:{limit}", ids)
    return jsonify(ids)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
