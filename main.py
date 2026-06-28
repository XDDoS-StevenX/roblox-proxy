"""
Roblox Catalog Proxy — main.py
Hosted on Render.com (Free tier)

NOTA: catalog.roblox.com bloquea requests desde servidores cloud.
Solución: lista de IDs hardcodeada aquí. Roblox fetchea precios
con GetProductInfo() internamente. Para agregar items usa /add-id.

Endpoints:
  GET /ping                → health check
  GET /recent-ids          → lista de IDs de accesorios
  POST /add-id             → agrega un ID a la lista (body: {"id": 123})
"""

from flask import Flask, jsonify, request
import time

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Lista de IDs de accesorios conocidos
# Agregar más con POST /add-id o editando esta lista directamente
# ---------------------------------------------------------------------------
ACCESSORY_IDS = [
    # Hats clásicos
    1029025,    # The Classic ROBLOX Fedora
    48545806,   # Dominus Frigidus
    1235488,    # Clockwork's Headphones
    11884330,   # Nerd Glasses
    102611803,  # Verified, Bonafide, Plaidafied
    4819740796, # Robox
    48474313,   # Red Roblox Cap
    19027209,   # Perfectly Legitimate Business Hat
    # Accesorios populares adicionales
    1365767,    # Bluesteel Domino Crown
    13488024,   # Aloha Fedora
    1029029,    # Sparkle Time Fedora
    119916029,  # Baseball Cap (Red)
    1365768,    # Violet Bluesteel Viking
    102611803,  # Verified Bonafide
    16630147,   # Whispering Flames
    175409451,  # Pirate Hat
    12578285,   # Balloon Sword
    422177519,  # Winged Fedora
    1081557,    # Pal Hair
    10406101,   # Messy Hair
]

# IDs agregados en runtime via /add-id
_extra_ids = []

# ---------------------------------------------------------------------------
CACHE_TTL = 300
_cache = {}

def _cache_get(key):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires_at"]:
        return entry["data"]
    return None

def _cache_set(key, data):
    _cache[key] = {"data": data, "expires_at": time.time() + CACHE_TTL}

# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "time": time.time()})


@app.route("/recent-ids")
def recent_ids():
    """
    Devuelve lista de IDs de accesorios.
    Roblox fetchea precios con GetProductInfo() internamente.
    """
    all_ids = list(dict.fromkeys(ACCESSORY_IDS + _extra_ids))  # dedup
    return jsonify(all_ids)


@app.route("/add-id", methods=["POST"])
def add_id():
    """
    POST /add-id  body: {"id": 123456}
    Agrega un ID a la lista en runtime (se pierde al reiniciar Render).
    Para persistir, editar ACCESSORY_IDS arriba y hacer deploy.
    """
    data = request.get_json(silent=True)
    if not data or "id" not in data:
        return jsonify({"error": "body must be {\"id\": NUMBER}"}), 400

    try:
        asset_id = int(data["id"])
    except (ValueError, TypeError):
        return jsonify({"error": "id must be an integer"}), 400

    if asset_id not in ACCESSORY_IDS and asset_id not in _extra_ids:
        _extra_ids.append(asset_id)

    return jsonify({"ok": True, "id": asset_id, "total": len(ACCESSORY_IDS) + len(_extra_ids)})


@app.route("/count")
def count():
    return jsonify({"total": len(ACCESSORY_IDS) + len(_extra_ids)})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
