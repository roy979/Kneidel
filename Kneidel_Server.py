from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)

# Enable CORS only for localhost:5500 (or your frontend origin)
CORS(app, resources={r"/api/*": {"origins": "http://127.0.0.1:5500"}})

GITHUB_TOKEN    = os.environ.get('GITHUB_TOKEN')
SPOTIFY_ID      = os.environ.get('SPOTIFY_ID')
SPOTIFY_SECRET  = os.environ.get('SPOTIFY_SECRET')

@app.route("/api/tokens", methods=["GET"])
def get_all_tokens():
    return jsonify({
        "github": GITHUB_TOKEN,
        "spotid": SPOTIFY_ID,
        "spotsec": SPOTIFY_SECRET
    })

@app.route("/")
def index():
    return "Package Server is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=port)