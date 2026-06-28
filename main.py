"""
Roblox Catalog Proxy — main.py
Hosted on Render.com (Free tier)

Endpoints:
  GET /ping                         → health check (anti-sleep)
  GET /item?id=ASSET_ID             → info de un solo item
  GET /items?ids=ID1,ID2,...        → info de varios items (máx 120)
  GET /recent-accessories           → lista de accesorios recientes
  GET /search?keyword=TEXTO         → búsqueda por nombre
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
# Headers — imita navegador
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
# Obtener info de un item usando la API pública de marketplace
# ---------------------------------------------------------------------------
def fetch_single_item(asset_id: int) -> dict | None:
    """
    Usa la API pública de Roblox que no requiere XSRF ni cookies.
    Endpoint: https://api.roblox.com/marketplace/productinfo
    """
    try:
        resp = requests.get(
            f"https://api.roblox.com/marketplace/productinfo?assetId={asset_id}",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            d = resp.json()
            return {
                "id": asset_id,
                "name": d.get("Name", "Unknown"),
                "price": d.get("PriceInRobux") or 0,
                "creator": d.get("Creator", {}).get("Name", "Roblox"),
                "thumbnail": f"https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png",
            }
    except Exception as e:
        print(f"[fetch_single_item] {asset_id}: {e}")
    return None


def fetch_item_details(asset_ids: list) -> list:
    """
    Llama a la API de thumbnails para verificar existencia,
    y productinfo para precio/nombre.
    """
    results = []
    for asset_id in asset_ids:
        cached = _cache_get(f"item:{asset_id}")
        if cached:
            results.append(cached)
            continue
        item = fetch_single_item(asset_id)
        if item:
            _cache_set(f"item:{asset_id}", item)
            results.append(item)
    return results


# ---------------------------------------------------------------------------
# Búsqueda en el catálogo
# ---------------------------------------------------------------------------
def search_catalog(keyword: str = "", subcategory: str = "", limit: int = 30) -> list:
    """
    Busca en el catálogo y devuelve lista de items con detalles.
    Usa catalog.roblox.com/v1/search/items — devuelve IDs,
    luego fetchea detalles con productinfo.
    """
    cache_key = f"search:{keyword}:{subcategory}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "limit": min(limit, 30),
        "sortType": 3,  # Recently updated
        "includeNotForSale": "false",
    }
    if keyword:
        params["keyword"] = keyword
    if subcategory:
        params["subcategory"] = subcategory

    ids = []
    try:
        resp = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params=params,
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            ids = [item["id"] for item in data if "id" in item]
    except Exception as e:
        print(f"[search_catalog] error: {e}")

    if not ids:
        _cache_set(cache_key, [])
        return []

    # Fetchear detalles de cada ID
    results = fetch_item_details(ids)
    _cache_set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/item")
def get_item():
    asset_id = request.args.get("id", type=int)
    if not asset_id:
        return jsonify({"error": "Missing ?id=ASSET_ID"}), 400

    cached = _cache_get(f"item:{asset_id}")
    if cached:
        return jsonify(cached)

    item = fetch_single_item(asset_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    _cache_set(f"item:{asset_id}", item)
    return jsonify(item)


@app.route("/items")
def get_items():
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify({"error": "Missing ?ids=ID1,ID2,..."}), 400

    try:
        asset_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "IDs must be integers"}), 400

    if len(asset_ids) > 120:
        return jsonify({"error": "Max 120 IDs per request"}), 400

    results = fetch_item_details(asset_ids)
    return jsonify(results)


@app.route("/recent-accessories")
def recent_accessories():
    cached = _cache_get("recent-accessories")
    if cached is not None:
        return jsonify(cached)

    # Buscar hats y accesorios por separado y mezclar
    hats = search_catalog(subcategory="ClassicHats", limit=15)
    accs = search_catalog(subcategory="Accessories", limit=15)

    # Deduplicar por id
    seen = set()
    combined = []
    for item in hats + accs:
        if item["id"] not in seen:
            seen.add(item["id"])
            combined.append(item)

    _cache_set("recent-accessories", combined)
    return jsonify(combined)


@app.route("/search")
def search():
    keyword = request.args.get("keyword", "").strip()
    limit = min(request.args.get("limit", 20, type=int), 60)

    if not keyword:
        return jsonify({"error": "Missing ?keyword=TEXTO"}), 400

    results = search_catalog(keyword=keyword, limit=limit)
    return jsonify(results)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
