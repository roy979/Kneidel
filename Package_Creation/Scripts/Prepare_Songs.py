import os
import sys
import shutil
import glob
from pydub import AudioSegment
import numpy as np
from scipy.signal import spectrogram
from tkinter.filedialog import askdirectory
CHORUS_DETECTION_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Kneidel_venv", "chorus-detection"))
if CHORUS_DETECTION_DIR not in sys.path:
    sys.path.insert(0, CHORUS_DETECTION_DIR)
from core.audio_processor import process_audio
from core.model import load_CRNN_model, make_predictions, MODEL_PATH


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

def create_run_file(package_folder):
    bat_content = f"""@echo off
echo Starting Demucs batch separation...
cd /d "%~dp0"

for %%i in ("{package_folder}\\*.mp3") do (
    echo Processing: %%i
    C:/Users/RoyWaisbord/anaconda3/python.exe -m demucs "%%i" -n htdemucs_6s --shifts 10 --overlap 0.25 --flac -d cpu -o "{package_folder}"
    if errorlevel 1 (
        echo Failed processing: %%i
        pause
        exit /b 1
    )
)

echo All songs processed successfully.
echo Deleting this script...
del "%~f0"
"""
    output_path = os.path.join(os.getcwd(), "Seperate_Songs.bat")
    with open(output_path, "w") as f:
        f.write(bat_content)

    print(f"Batch file created successfully at:\n{output_path}")


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
    Extracts the longest chorus section and overwrites the original audio file.

    Parameters:
        audio_path (str): Path to the original audio file.
        choruses (list of tuples): (start_time, end_time) pairs in seconds.

    Returns:
        str: Path to the overwritten audio file, or None if no choruses.
    """
    if not choruses:
        print(f"No choruses found in {os.path.basename(audio_path)}")
        return None

    # Load audio
    try:
        audio = AudioSegment.from_file(audio_path)
    except Exception as e:
        print(f"Failed to load audio: {e}")
        return None

    duration_ms = len(audio)

    # Compute middle and 30-second segment
    longest = max(choruses, key=lambda c: c[1] - c[0])
    middle = (longest[0] + longest[1]) / 2
    start_ms = max(0, int((middle - 15) * 1000))
    end_ms = min(duration_ms, int((middle + 15) * 1000))

    # Slice and export
    chorus_segment = audio[start_ms:end_ms]
    try:
        chorus_segment.export(audio_path, format="mp3")
        print(f"Overwritten with longest chorus: {audio_path}")
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
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    if audio.channels == 2:
        samples = samples.reshape((-1, 2)).mean(axis=1)
    return samples[:30 * audio.frame_rate], audio.frame_rate  # Trim to 30 seconds

def sort_instruments(song_path):
    print(f"\nProcessing: {song_path}")
    psd_list = []
    vocals_file = None

    for file in os.listdir(song_path):
        if file.lower().endswith(".flac"):
            full_path = os.path.join(song_path, file)

            if "vocals" in file.lower():
                vocals_file = file
                continue  # Skip for now; we'll handle vocals last

            try:
                samples, rate = process_song_file(full_path)
                psd = compute_band_psd(samples, rate, band=PSD_BAND)
                psd_list.append((file, psd))
            except Exception as e:
                print(f"Error processing {file}: {e}")

    if not psd_list and not vocals_file:
        print("No audio files found or processed.")
        return

    # Sort by PSD (low to high)
    psd_list.sort(key=lambda x: x[1])
    psd_values = [psd for _, psd in psd_list] or [1]  # Avoid division by zero
    max_psd = max(psd_values)

    for i, (filename, psd) in enumerate(psd_list):
        old_path = os.path.join(song_path, filename)

        if psd < QUIET_THRESHOLD_RATIO * max_psd:
            new_name = os.path.splitext(filename)[0] + "_Quiet.flac"
        else:
            new_name = f"{i + 1}.flac"

        new_path = os.path.join(song_path, new_name)
        os.rename(old_path, new_path)
        print(f"Renamed '{filename}' → '{new_name}'")

    # Handle vocals.flac → 6.flac
    if vocals_file:
        old_vocals_path = os.path.join(song_path, vocals_file)
        new_vocals_path = os.path.join(song_path, "6.flac")
        os.rename(old_vocals_path, new_vocals_path)
        print(f"Renamed 'vocals.flac' → '6.flac'")

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
            try:
                shutil.rmtree(full_path)
                print(f"Removed empty folder: {full_path}")
            except Exception as e:
                print(f"Failed to remove folder {full_path}: {e}")

# === Parameters ===
PSD_BAND = (20, 16000)  # Hz
QUIET_THRESHOLD_RATIO = 0.1  # Below 10% of max PSD → Quiet

if __name__ == "__main__":
    package_folder = askdirectory(title="Select Unprocessed Songs Folder")
    if not package_folder:
        print("No folder selected.")
    else:
        try:
            rename(package_folder)

            for song_path in glob.glob(os.path.join(package_folder, "*.mp3")):
                choruses = detect_choruses(song_path)

                extract_longest_chorus(song_path, choruses)

            for song_folder in os.listdir(package_folder):
                song_path = os.path.join(package_folder, song_folder)
                if os.path.isdir(song_path):
                    sort_instruments(song_path)

            create_run_file(package_folder)

            cleanup(package_folder)

        except Exception as e:
            print(f"Error: {e}")