"""
Roblox Catalog Proxy — main.py
Hosted on Render.com (Free tier)

Endpoints:
  GET /ping                         → health check (anti-sleep)
  GET /item?id=ASSET_ID             → info de un solo item
  GET /items?ids=ID1,ID2,...        → info de varios items (máx 120)
  GET /recent-accessories           → lista de accesorios recientes (Hats + Accessories)
  GET /search?keyword=TEXTO         → búsqueda por nombre
"""

from flask import Flask, jsonify, request
import requests
import time

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Cache simple en memoria  (key → {data, expires_at})
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
# Headers comunes — imita un navegador para evitar bloqueos
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
    "Origin": "https://www.roblox.com",
}


# ---------------------------------------------------------------------------
# Función principal: obtener detalles de items por ID
# Usa economy.roblox.com — funciona sin cookies ni XSRF
# ---------------------------------------------------------------------------
def fetch_item_details(asset_ids: list[int]) -> list[dict]:
    """
    Llama a economy.roblox.com/v2/assets/details (POST) para obtener
    nombre, precio, tipo y creador de cada asset.
    Máximo 120 IDs por request.
    """
    results = []
    # Procesar en lotes de 120
    for i in range(0, len(asset_ids), 120):
        batch = asset_ids[i:i + 120]
        try:
            resp = requests.post(
                "https://economy.roblox.com/v2/assets/details",
                json={"assetIds": batch},
                headers=HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    results.append({
                        "id": item.get("AssetId"),
                        "name": item.get("Name", "Unknown"),
                        "price": item.get("PriceInRobux") or 0,
                        "type": item.get("AssetTypeId"),
                        "creator": item.get("Creator", {}).get("Name", "Roblox"),
                        "thumbnail": f"https://www.roblox.com/asset-thumbnail/image?assetId={item.get('AssetId')}&width=420&height=420&format=png",
                    })
        except Exception as e:
            print(f"[fetch_item_details] batch error: {e}")
    return results


# ---------------------------------------------------------------------------
# Búsqueda en el catálogo
# Usa catalog.roblox.com/v1/search/items con subcategory de sombreros/accesorios
# ---------------------------------------------------------------------------
def search_catalog(keyword: str = "", category: str = "Accessories", limit: int = 30) -> list[int]:
    """
    Devuelve una lista de asset IDs del catálogo.
    category: 'Accessories', 'Hats', 'All'
    """
    cache_key = f"search:{keyword}:{category}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    params = {
        "limit": limit,
        "sortType": 2,           # Relevance
        "includeNotForSale": "false",
    }
    if keyword:
        params["keyword"] = keyword
    if category == "Hats":
        params["subcategory"] = "ClassicHats"
    elif category == "Accessories":
        params["subcategory"] = "Accessories"
    # 'All' → sin subcategory

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
            _cache_set(cache_key, ids)
            return ids
    except Exception as e:
        print(f"[search_catalog] error: {e}")
    return []


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.route("/ping")
def ping():
    """Health check — llamar cada 10 min desde cron-job.org para no dormir."""
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/item")
def get_item():
    """
    GET /item?id=ASSET_ID
    Devuelve info de un solo item.
    """
    asset_id = request.args.get("id", type=int)
    if not asset_id:
        return jsonify({"error": "Missing ?id=ASSET_ID"}), 400

    cache_key = f"item:{asset_id}"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    results = fetch_item_details([asset_id])
    if not results:
        return jsonify({"error": "Item not found"}), 404

    _cache_set(cache_key, results[0])
    return jsonify(results[0])


@app.route("/items")
def get_items():
    """
    GET /items?ids=ID1,ID2,ID3,...
    Devuelve info de varios items. Máx 120.
    """
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify({"error": "Missing ?ids=ID1,ID2,..."}), 400

    try:
        asset_ids = [int(x.strip()) for x in ids_param.split(",") if x.strip()]
    except ValueError:
        return jsonify({"error": "IDs must be integers"}), 400

    if len(asset_ids) > 120:
        return jsonify({"error": "Max 120 IDs per request"}), 400

    cache_key = f"items:{ids_param}"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    results = fetch_item_details(asset_ids)
    _cache_set(cache_key, results)
    return jsonify(results)


@app.route("/recent-accessories")
def recent_accessories():
    """
    GET /recent-accessories
    Devuelve los 30 accesorios más recientes del catálogo (Hats + Accessories).
    Ideal para poblar el AccessoryShopGui automáticamente.
    """
    cache_key = "recent-accessories"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    # Buscar hats y accesorios por separado y mezclar
    hat_ids = search_catalog(category="Hats", limit=15)
    acc_ids = search_catalog(category="Accessories", limit=15)

    all_ids = list(dict.fromkeys(hat_ids + acc_ids))  # deduplicar preservando orden

    if not all_ids:
        return jsonify([])

    results = fetch_item_details(all_ids)
    _cache_set(cache_key, results)
    return jsonify(results)


@app.route("/search")
def search():
    """
    GET /search?keyword=TEXTO&limit=20
    Busca accesorios por nombre y devuelve detalles completos.
    """
    keyword = request.args.get("keyword", "").strip()
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 60)  # cap

    if not keyword:
        return jsonify({"error": "Missing ?keyword=TEXTO"}), 400

    cache_key = f"search-full:{keyword}:{limit}"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    ids = search_catalog(keyword=keyword, category="All", limit=limit)
    if not ids:
        return jsonify([])

    results = fetch_item_details(ids)
    _cache_set(cache_key, results)
    return jsonify(results)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
