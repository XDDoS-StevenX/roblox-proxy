from flask import Flask, jsonify
import requests

app = Flask(__name__)

@app.route("/recent-accessories")
def recent_accessories():
    try:
        r = requests.get(
            "https://catalog.roblox.com/v1/search/items",
            params={
                "category": "Accessories",
                "sortType": 3,
                "limit": 20,
                "salesTypeFilter": 1
            },
            timeout=10
        )
        data = r.json()
        items = []
        for item in data.get("data", []):
            items.append({
                "id":    item.get("id"),
                "name":  item.get("name", "Unknown"),
                "price": item.get("lowestPrice") or item.get("price") or 0,
            })
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ping")
def ping():
    return "pong"

@app.route("/")
def index():
    return "Roblox Catalog Proxy — OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
