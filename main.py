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
        r = requests.get(
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
        data = r.json()
        items = []
        for item in data.get("data", []):
            price = item.get("lowestPrice") or item.get("price") or 0
            items.append({
                "id":    item.get("id"),
                "name":  item.get("name", "Unknown"),
                "price": price,
            })
        return jsonify({"success": True, "items": items, "count": len(items)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/debug")
def debug():
    try:
        r = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params={
                "category": "Accessories",
                "sortType": 3,
                "limit": 10,
            },
            headers=HEADERS,
            timeout=10
        )
        return jsonify({
            "status_code": r.status_code,
            "raw": r.json()
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
