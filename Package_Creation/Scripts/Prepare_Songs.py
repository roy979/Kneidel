import os
import sys
import json
import time
import shutil
import glob
import subprocess
import requests
import logging
from pydub import AudioSegment, effects
import numpy as np
from scipy.signal import spectrogram
from tkinter.filedialog import askdirectory
CHORUS_DETECTION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Kneidel_venv", "chorus-detection"))
if CHORUS_DETECTION_DIR not in sys.path:
    sys.path.insert(0, CHORUS_DETECTION_DIR)
from core.audio_processor import process_audio
from core.model import load_CRNN_model, make_predictions, MODEL_PATH
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import contextlib

@contextlib.contextmanager
def suppress_output():
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

# Initialize credentials
print("Fetching Spotify Credentials From The Server...")
try:
    # Try to get tokens from external API first with timeout
    r = requests.get("https://kneidel.onrender.com/api/tokens", timeout=120)
    r.raise_for_status()
    data = r.json()

    SPOTIFY_ID = data["spotid"]
    SPOTIFY_SECRET = data["spotsec"]
    print(" ✔")
except Exception as e:
    print(f"Failed to get credentials from external API: {e}")


# Initialize Spotify client
if SPOTIFY_ID and SPOTIFY_SECRET:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_ID, client_secret=SPOTIFY_SECRET))
else:
    sp = None
    print("Spotify credentials not available")

def fetch_song_metadata(song_folder_path):
    """
    Extracts release year and popularity from Spotify API based on folder name.
    Assumes folder name is the song name and it contains the original song file.
    Saves metadata as a JSON file in the same folder.
    """
    if not os.path.isdir(song_folder_path):
        print(f"Not a valid folder: {song_folder_path}")
        return

    # Use the folder name as the search query
    song_name = os.path.basename(song_folder_path).replace("_", " ").replace("-", " ")

    try:
        results = sp.search(q=song_name, type="track", limit=1)
        if not results["tracks"]["items"]:
            print(f"No results for: {song_name}")
            return

        track = results["tracks"]["items"][0]
        release_date = track["album"]["release_date"]
        popularity = track["popularity"]
        artist = track["artists"][0]["name"]
        title = track["name"]

        data = {
            "title": title,
            "artist": artist,
            "release_year": release_date.split("-")[0],
            "popularity": popularity
        }

        # Save metadata JSON in the same folder
        json_path = os.path.join(song_folder_path, f"{title} - {artist}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print(f"Metadata saved to: {json_path}")

    except Exception as e:
        print(f"Error processing {song_folder_path}: {e}")

def rename(package_folder):
    if package_folder:
        parent_dir = os.path.dirname(package_folder)
        folder_name = os.path.basename(package_folder)

        # --- Rename the folder itself if needed ---
        if folder_name.startswith("[SPOTDOWNLOADER.COM] "):
            new_folder_name = folder_name.replace("[SPOTDOWNLOADER.COM] ", "", 1)
            new_package_folder = os.path.join(parent_dir, new_folder_name)
            os.rename(package_folder, new_package_folder)
            print(f"Renamed folder: {folder_name} → {new_folder_name}")
            package_folder = new_package_folder  # Update to new name

        # --- Rename all files inside ---
        for filename in os.listdir(package_folder):
            if filename.startswith("[SPOTDOWNLOADER.COM] "):
                new_name = filename.replace("[SPOTDOWNLOADER.COM] ", "", 1)
                old_path = os.path.join(package_folder, filename)
                new_path = os.path.join(package_folder, new_name)
                os.rename(old_path, new_path)
                print(f"Renamed file: {filename} → {new_name}")

        return package_folder

def create_run_file(song_path):
    """
    Creates a batch file that runs Demucs on a single song.
    """
    song_dir = os.path.dirname(song_path)
    bat_content = f"""@echo off
echo Starting Demucs separation for: {os.path.basename(song_path)}
cd /d "%~dp0"

C:/Users/RoyWaisbord/anaconda3/python.exe -m demucs "{song_path}" -n htdemucs_6s  --shifts 5 --overlap 0.25 --flac -d cpu -o "{song_dir}"
if errorlevel 1 (
    echo Failed processing: {song_path}
    pause
    exit /b 1
)

echo Song processed successfully.
"""
    output_path = os.path.join(os.getcwd(), "Seperate_Song.bat")
    with open(output_path, "w") as f:
        f.write(bat_content)

def detect_choruses(audio_path: str, model_path: str = MODEL_PATH):
    """
    Detects choruses in a given audio file.
    
    Parameters:
        audio_path (str): Path to a local audio file.
        model_path (str): Path to the pre-trained CRNN model.
        
    Returns:
        list of tuples: Each tuple contains (start_time, end_time) in seconds.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found at {audio_path}")

    # Process the audio
    processed_audio, audio_features = process_audio(audio_path)
    if processed_audio is None:
        raise ValueError("Failed to process audio.")

    # Load model
    model = load_CRNN_model(model_path=model_path)
    if model is None:
        raise RuntimeError("Failed to load CRNN model.")

    # Predict
    _, chorus_start_times, chorus_end_times = make_predictions(model, processed_audio, audio_features)

    return list(zip(chorus_start_times, chorus_end_times))

def extract_longest_chorus(audio_path, choruses):
    """
    Extracts the first chorus longer than 20s, or the longest if none qualify.
    Overwrites the original audio file with a 30-second centered segment.
    """
    if not choruses:
        print(f"No choruses found in {os.path.basename(audio_path)}")
        return None

    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as e:
        print(f"Failed to load audio: {e}")
        return None

    duration_ms = len(audio)

    # Try to find the first chorus longer than 20s
    selected = None
    for start, end in choruses:
        if end - start >= 20:
            selected = (start, end)
            break

    # If none found, fall back to longest chorus
    if not selected:
        selected = max(choruses, key=lambda c: c[1] - c[0])

    # Center a 30s segment around the middle of the chorus
    middle = (selected[0] + selected[1]) / 2
    start_ms = max(0, int((middle - 15) * 1000))
    end_ms = min(duration_ms, int((middle + 15) * 1000))

    chorus_segment = audio[start_ms:end_ms]
    try:
        chorus_segment.export(audio_path, format="mp3")
        return audio_path
    except Exception as e:
        print(f"Failed to save audio: {e}")
        return None

def compute_band_psd(samples, sample_rate, band=(20, 16000)):
    f, t, Sxx = spectrogram(samples, fs=sample_rate, nperseg=1024)
    band_mask = (f >= band[0]) & (f <= band[1])
    band_power = Sxx[band_mask]
    mean_psd_band = np.mean(band_power)
    return mean_psd_band

def process_song_file(file_path):
    audio = AudioSegment.from_file(file_path)
    audio = effects.normalize(audio)
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)
    return samples[:30 * audio.frame_rate], audio.frame_rate  # Trim to 30 seconds

def sort_instruments(song_path):
    print(f"\nProcessing: {song_path}")
    stem_scores = []
    vocals_file = None

    for file in os.listdir(song_path):
        if file.lower().endswith(".flac"):
            full_path = os.path.join(song_path, file)

            if "vocals" in file.lower():
                vocals_file = file
                continue

            try:
                samples, rate = process_song_file(full_path)
                psd = compute_band_psd(samples, rate, band=PSD_BAND)
                rms = effects.normalize(AudioSegment.from_file(full_path)).rms
                combined_score = 0.7 * psd + 0.3 * rms
                stem_scores.append((file, combined_score))
            except Exception as e:
                print(f"Error processing {file}: {e}")

    if not stem_scores and not vocals_file:
        print("No stems found.")
        return

    stem_scores.sort(key=lambda x: x[1])
    max_score = max([score for _, score in stem_scores] or [1])

    for i, (filename, score) in enumerate(stem_scores):
        old_path = os.path.join(song_path, filename)
        if score < QUIET_THRESHOLD_RATIO * max_score:
            new_name = os.path.splitext(filename)[0] + "_Quiet.flac"
        else:
            new_name = f"{i + 1}.flac"
        new_path = os.path.join(song_path, new_name)
        os.rename(old_path, new_path)
        print(f"Renamed '{filename}' → '{new_name}'")
        last_stem = i+1

    if vocals_file:
        old_vocals_path = os.path.join(song_path, vocals_file)
        new_vocals_path = os.path.join(song_path, f"{last_stem}.flac")
        os.rename(old_vocals_path, new_vocals_path)
        print(f"Renamed 'vocals.flac' → '{last_stem}.flac'")

def cleanup(package_folder):
    """
    Removes all files directly inside `package_folder` and moves all song folders from
    subfolders like 'htdemucs_6s' to the main `package_folder`.

    Example:
        Packages/Songle/htdemucs_6s/Back To Black  -->  Packages/Songle/Back To Black
    """
    if not os.path.exists(package_folder):
        print(f"Package folder does not exist: {package_folder}")
        return

    # Step 1: Delete all files directly inside the package folder
    for item in os.listdir(package_folder):
        full_path = os.path.join(package_folder, item)
        if os.path.isfile(full_path):
            try:
                os.remove(full_path)
                print(f"Deleted file: {full_path}")
            except Exception as e:
                print(f"Failed to delete {full_path}: {e}")

    # Step 2: Move song folders from subfolders (e.g. htdemucs_6s) to the main folder
    for root, dirs, files in os.walk(package_folder):
        if root == package_folder:
            continue  # Skip the main folder
        for folder in dirs:
            src = os.path.join(root, folder)
            dest = os.path.join(package_folder, folder)
            if os.path.exists(dest):
                print(f"Warning: Destination already exists, skipping: {dest}")
                continue
            try:
                os.rename(src, dest)
                print(f"Moved: {src} --> {dest}")
            except Exception as e:
                print(f"Failed to move {src} to {dest}: {e}")
        break  # Only process immediate subfolder level

    # Optional: Remove now-empty folders (like htdemucs_6s)
    for item in os.listdir(package_folder):
        full_path = os.path.join(package_folder, item)
        if os.path.isdir(full_path) and not os.listdir(full_path):
            for attempt in range(3):  # Retry up to 3 times
                try:
                    shutil.rmtree(full_path)
                    print(f"Removed empty folder: {full_path}")
                    break
                except PermissionError as e:
                    print(f"Retrying to remove {full_path} (attempt {attempt + 1})...")
                    time.sleep(1)
                except Exception as e:
                    print(f"Failed to remove folder {full_path}: {e}")
                    break

# === Parameters ===
PSD_BAND = (20, 16000)  # Hz
QUIET_THRESHOLD_RATIO = 0.12  # Below 12% of max PSD → Quiet

if __name__ == "__main__":
    package_folder = askdirectory(title="Select Unprocessed Songs Folder")
    if not package_folder:
        print("No folder selected.")
    else:
        try:
            print(f"\n🔁 Removing [SPOTDOWNLOADER] Tag From Folder And Songs Name...")
            package_folder = rename(package_folder)
            print(" ✔")

            song_paths = glob.glob(os.path.join(package_folder, "*.mp3"))
            total_songs = len(song_paths)

            print(f"\n🎼 Found {total_songs} song(s) to process.")

            for idx, song_path in enumerate(song_paths, start=1):
                if "htdemucs" in song_path or "mdx" in song_path:
                    continue

                song_name = os.path.basename(song_path)

                print(f"\n🔁 Processing {song_name} [{idx}/{total_songs}]")

                # Step 1: Detect chorus
                print("   🎵 Detecting choruses...", end="", flush=True)
                with suppress_output():
                    choruses = detect_choruses(song_path)
                print(" ✔")

                # Step 2: Extract chorus
                print("   🎯 Extracting chorus segment...", end="", flush=True)
                extract_longest_chorus(song_path, choruses)
                print(" ✔")

                # Step 3: Create and run batch file
                print("   🛠️  Creating Demucs batch file...", end="", flush=True)
                create_run_file(song_path)
                print(" ✔")

                print("   ⚙ Running separation...")
                bat_path = os.path.join(os.getcwd(), "Seperate_Song.bat")
                subprocess.run(["cmd.exe", "/c", bat_path], check=True)

                # Step 4: Delete .bat
                try:
                    os.remove(bat_path)
                    print("   🧹 Batch file deleted.")
                except Exception as e:
                    print(f"   ⚠️ Failed to delete batch file: {e}")

            # Step 5: Cleanup output
            print("\n📂 Cleaning up folder structure...")
            cleanup(package_folder)
            print("✔ Folder cleaned.\n")

            # Step 6: Sort instruments + fetch metadata
            song_folders = [f for f in os.listdir(package_folder) if os.path.isdir(os.path.join(package_folder, f))]
            total_folders = len(song_folders)

            for idx, song_folder in enumerate(song_folders, start=1):
                song_folder_path = os.path.join(package_folder, song_folder)
                print(f"\n🎚️ Sorting stems for: {song_folder} [{idx}/{total_folders}]")
                sort_instruments(song_folder_path)

                print(f"🔍 Fetching metadata for: {song_folder} [{idx}/{total_folders}]")
                fetch_song_metadata(song_folder_path)

            print("\n✅ All songs processed successfully.")

        except subprocess.CalledProcessError as bat_error:
            print(f"\n❌ Batch file failed: {bat_error}")
        except Exception as e:
            print(f"\n❌ Error: {e}")