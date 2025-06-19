from flask import Flask, jsonify
import os

app = Flask(__name__)
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