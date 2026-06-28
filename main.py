from flask import Flask, jsonify
import requests

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

@app.route("/recent-accessories")
def recent_accessories():
    try:
        r1 = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params={
                "category": "Accessories",
                "sortType": 3,
                "sortAggregation": 5,
                "limit": 30,
                "minPrice": 0,
            },
            headers=HEADERS,
            timeout=10
        )
        data1 = r1.json()
        entries = data1.get("data", [])
        if not entries:
            return jsonify({"success": True, "items": [], "count": 0})

        item_list = [{"itemType": e["itemType"], "id": e["id"]} for e in entries]
        r2 = requests.post(
            "https://catalog.roblox.com/v1/catalog/items/details",
            json={"items": item_list},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=10
        )
        data2 = r2.json()

        items = []
        for item in data2.get("data", []):
            price = item.get("lowestPrice") or item.get("price") or 0
            items.append({
                "id":    item.get("id"),
                "name":  item.get("name", "Unknown"),
                "price": price,
            })

        return jsonify({"success": True, "items": items, "count": len(items)})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/debug2")
def debug2():
    try:
        # Paso 1
        r1 = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params={"category": "Accessories", "sortType": 3, "limit": 5},
            headers=HEADERS,
            timeout=10
        )
        entries = r1.json().get("data", [])

        # Paso 2 - ver respuesta raw
        item_list = [{"itemType": e["itemType"], "id": e["id"]} for e in entries]
        r2 = requests.post(
            "https://catalog.roblox.com/v1/catalog/items/details",
            json={"items": item_list},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=10
        )
        return jsonify({
            "step1_entries": entries,
            "step2_status": r2.status_code,
            "step2_raw": r2.json()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ping")
def ping():
    return "pong"

@app.route("/")
def index():
    return "Roblox Catalog Proxy — OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
