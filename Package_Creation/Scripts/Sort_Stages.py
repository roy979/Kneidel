import os
import numpy as np
from pydub import AudioSegment
from scipy.signal import spectrogram
from tkinter import filedialog, Tk

# === Parameters ===
PSD_BAND = (20, 16000)  # Hz
QUIET_THRESHOLD_RATIO = 0.1  # Below 10% of max PSD → Quiet

def choose_folder():
    root = Tk()
    root.withdraw()
    return filedialog.askdirectory(title="Select Package Folder (containing song folders)")

def compute_band_psd(samples, sample_rate, band=(20, 16000)):
    f, t, Sxx = spectrogram(samples, fs=sample_rate, nperseg=1024)
    band_mask = (f >= band[0]) & (f <= band[1])
    band_power = Sxx[band_mask]
    mean_psd_band = np.mean(band_power)
    return mean_psd_band

def process_audio(file_path):
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
                samples, rate = process_audio(full_path)
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

# === Main script ===
if __name__ == "__main__":
    package_folder = choose_folder()
    if not package_folder:
        print("No folder selected.")
    else:
        for song_folder in os.listdir(package_folder):
            song_path = os.path.join(package_folder, song_folder)
            if os.path.isdir(song_path):
                sort_instruments(song_path)