import os
import random
import tempfile
import requests
import logging
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
CORS(app)

# Configuration
GITHUB_USER = "roy979"
GITHUB_REPO = "Kneidel"
BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/Packages"
API_BASE = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages"

# Initialize credentials
try:
    # Try to get tokens from external API first with timeout
    r = requests.get("https://kneidel.onrender.com/api/tokens", timeout=5)
    r.raise_for_status()
    data = r.json()

    GITHUB_TOKEN = data["github"]
    SPOTIFY_ID = data["spotid"]
    SPOTIFY_SECRET = data["spotsec"]
    logging.info("Successfully retrieved credentials from external API")
except Exception as e:
    logging.warning(f"Failed to get credentials from external API: {e}")
    # Fallback to environment variables
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    SPOTIFY_ID = os.environ.get('SPOTIFY_ID')
    SPOTIFY_SECRET = os.environ.get('SPOTIFY_SECRET')
    logging.info("Using environment variables for credentials")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# Initialize Spotify client
if SPOTIFY_ID and SPOTIFY_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET))
else:
    sp = None
    logging.warning("Spotify credentials not available")

# Game state storage (in production, use a proper session store)
game_sessions = {}


@app.route('/')
def index():
    """Main game page"""
    return render_template('index.html')


@app.route("/api/tokens", methods=["GET"])
def get_all_tokens():
    return jsonify({
        "github": GITHUB_TOKEN,
        "spotid": SPOTIFY_ID,
        "spotsec": SPOTIFY_SECRET
    })

@app.route('/api/packages')
def get_packages():
    """Get available music packages from GitHub"""
    try:
        r = requests.get(API_BASE, headers=HEADERS)
        r.raise_for_status()
        packages = [item["name"] for item in r.json() if item["type"] == "dir"]
        return jsonify({"success": True, "packages": packages})
    except Exception as e:
        logging.error(f"Error fetching packages: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/start-game', methods=['POST'])
def start_game():
    """Initialize a new game session with selected packages"""
    try:
        data = request.json
        selected_packages = data.get('packages', [])
        session_id = data.get('session_id', 'default')

        if not selected_packages:
            return jsonify({
                "success": False,
                "error": "No packages selected"
            }), 400

        # Fetch songs from selected packages
        remote_songs = []
        for pkg in selected_packages:
            url = f"{API_BASE}/{pkg}"
            r = requests.get(url, headers=HEADERS)
            r.raise_for_status()
            for item in r.json():
                if item["type"] == "dir":
                    remote_songs.append(f"{pkg}/{item['name']}")

        if not remote_songs:
            return jsonify({
                "success": False,
                "error": "No songs found in selected packages"
            }), 400

        # Shuffle songs and initialize game state
        random.shuffle(remote_songs)
        game_sessions[session_id] = {
            'packages': selected_packages,
            'songs': remote_songs,
            'current_index': 0,
            'stage': 0,
            'score': 0,
            'guessed_songs': []
        }

        return jsonify({"success": True, "total_songs": len(remote_songs)})

    except Exception as e:
        logging.error(f"Error starting game: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/current-song/<session_id>')
def get_current_song(session_id):
    """Get current song information and stems"""
    try:
        if session_id not in game_sessions:
            return jsonify({
                "success": False,
                "error": "Session not found"
            }), 404

        session = game_sessions[session_id]
        if session['current_index'] >= len(session['songs']):
            return jsonify({"success": False, "error": "No more songs"}), 400

        current_song = session['songs'][session['current_index']]

        # Get stems for current song
        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages/{current_song}"
        r = requests.get(api_url, headers=HEADERS)
        r.raise_for_status()

        stems = []
        for file_info in r.json():
            if file_info['type'] == 'file' and file_info['name'].endswith(
                    '.flac') and '_Quiet' not in file_info['name']:
                stem_name = file_info['name'][:-5]  # Remove .flac extension
                stems.append({
                    'name':
                    stem_name,
                    'url':
                    file_info['download_url'],
                    'stage':
                    int(stem_name) if stem_name.isdigit() else 0
                })

        # Sort stems by stage number
        stems.sort(key=lambda x: x['stage'])

        return jsonify({
            "success": True,
            "song_name": current_song.split('/')[-1],
            "stems": stems,
            "current_stage": session['stage'],
            "total_stages": len(stems)
        })

    except Exception as e:
        logging.error(f"Error getting current song: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/search-songs', methods=['POST'])
def search_songs():
    """Search for songs using Spotify API for autocomplete"""
    try:
        data = request.json
        query = data.get('query', '').strip()

        if not query or len(query) < 2:
            return jsonify({"success": True, "suggestions": []})

        if not sp:
            return jsonify({
                "success": False,
                "error": "Spotify not available"
            }), 503

        # Search Spotify for tracks
        results = sp.search(q=query, type='track', limit=10)
        suggestions = []

        for track in results['tracks']['items']:
            artist_name = track['artists'][0]['name'] if track[
                'artists'] else 'Unknown'
            suggestions.append({
                'name': track['name'],
                'artist': artist_name,
                'display': f"{artist_name} - {track['name']}"
            })

        return jsonify({"success": True, "suggestions": suggestions})

    except Exception as e:
        logging.error(f"Error searching songs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/guess', methods=['POST'])
def check_guess():
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        guess = data.get('guess', '').strip().lower()

        if session_id not in game_sessions:
            return jsonify({
                "success": False,
                "error": "Session not found"
            }), 404

        session = game_sessions[session_id]
        current_song = session['songs'][session['current_index']]
        correct_answer = current_song.split('/')[-1].lower()

        # Check if guess matches (partial matching)
        is_correct = correct_answer in guess or guess in correct_answer or guess == 'vizen gay'

        # Fetch total stages dynamically
        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages/{current_song}"
        r = requests.get(api_url, headers=HEADERS)
        r.raise_for_status()
        total_stages = len([
            f for f in r.json()
            if f['type'] == 'file' and f['name'].endswith('.flac') and '_Quiet' not in f['name']
        ])

        if is_correct:
            # Calculate score based on current stage (earlier guess = higher score)
            stage_bonus = max(0, total_stages - session['stage'])
            points = 100 + (stage_bonus * 20)
            session['score'] += points
            session['guessed_songs'].append({
                'song': current_song.split('/')[-1],
                'stage': session['stage'],
                'points': points
            })

            return jsonify({
                "success": True,
                "correct": True,
                "answer": current_song.split('/')[-1],
                "points": points,
                "total_score": session['score']
            })
        else:
            session['stage'] += 1
            
            if session['stage'] >= total_stages:
                return jsonify({
                    "success": True,
                    "correct": False,
                    "final_stage": True,
                    "answer": current_song.split('/')[-1],
                    "message": f"Wrong! The answer was: {current_song.split('/')[-1]}"
                })
            else:
                return jsonify({
                    "success": True,
                    "correct": False,
                    "new_stage": session['stage'],
                    "message": "Not quite right! Moving to next stage..."
                })

    except Exception as e:
        logging.error(f"Error checking guess: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/skip-stage', methods=['POST'])
def skip_stage():
    """Skip to next stage or reveal answer"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')

        if session_id not in game_sessions:
            return jsonify({
                "success": False,
                "error": "Session not found"
            }), 404

        session = game_sessions[session_id]
        current_song = session['songs'][session['current_index']]

        # Fetch actual number of stems for the current song
        api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages/{current_song}"
        r = requests.get(api_url, headers=HEADERS)
        r.raise_for_status()

        total_stages = len([
            f for f in r.json()
            if f['type'] == 'file' and f['name'].endswith('.flac') and '_Quiet' not in f['name']
        ])

        # Advance to the next stage
        session['stage'] += 1

        # Check if we've reached or exceeded the final stage
        if session['stage'] >= total_stages:
            return jsonify({
                "success": True,
                "final_stage": True,
                "answer": current_song.split('/')[-1]
            })

        return jsonify({
            "success": True,
            "new_stage": session['stage'],
            "final_stage": False
        })

    except Exception as e:
        logging.error(f"Error skipping stage: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/next-song', methods=['POST'])
def next_song():
    """Move to the next song"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')

        if session_id not in game_sessions:
            return jsonify({
                "success": False,
                "error": "Session not found"
            }), 404

        session = game_sessions[session_id]
        session['current_index'] += 1
        session['stage'] = 0

        if session['current_index'] >= len(session['songs']):
            # Game finished
            return jsonify({
                "success": True,
                "game_finished": True,
                "final_score": session['score'],
                "songs_guessed": len(session['guessed_songs']),
                "total_songs": len(session['songs'])
            })

        return jsonify({
            "success": True,
            "game_finished": False,
            "song_number": session['current_index'] + 1,
            "total_songs": len(session['songs'])
        })

    except Exception as e:
        logging.error(f"Error moving to next song: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/game-status/<session_id>')
def get_game_status(session_id):
    """Get current game status"""
    try:
        if session_id not in game_sessions:
            return jsonify({
                "success": False,
                "error": "Session not found"
            }), 404

        session = game_sessions[session_id]
        return jsonify({
            "success": True,
            "current_song": session['current_index'] + 1,
            "total_songs": len(session['songs']),
            "current_stage": session['stage'],
            "score": session['score'],
            "guessed_songs": len(session['guessed_songs'])
        })

    except Exception as e:
        logging.error(f"Error getting game status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)


# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 10000)) 
#     print(f"Running on port {port}")
#     app.run(host='0.0.0.0', port=port)
