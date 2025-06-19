from flask import Flask, jsonify
import os

app = Flask(__name__)
GITHUB_TOKEN = os.environ['Git_Token']

@app.route("/api/token", methods=["GET"])
def get_token():
    return jsonify({"token": GITHUB_TOKEN})

@app.route("/")
def index():
    return "Package Server is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=port)