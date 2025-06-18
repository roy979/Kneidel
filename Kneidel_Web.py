import os
import pygame
import random
import requests
import tkinter as tk
from tkinter import ttk
from threading import Thread
from time import sleep
from urllib.parse import quote
from pydub import AudioSegment
import tempfile
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="6856f3744c7f44a788d1973b8a61b244",
    client_secret="e67de1cb6dae45bcb2382d540d3b3de8"
))

# === Setup Pygame Mixer ===
pygame.mixer.init()

BASE_URL = "http://0f5e663b-cb9d-4eb5-bf97-95caddbdade4-00-i82hhenc0n59.pike.replit.dev"

# === GUI Setup ===
class SongGameGUI:
    def __init__(self, root):
        self.package_folder = None
        self.song_folders = []
        self.current_song_index = 0

        self.root = root
        self.song_folder = None
        self.root.title("Kneidel")
        self.root.geometry("600x400")
        self.root.configure(bg="white")

        self.stage = 0
        self.is_playing = False
        self.is_paused = False
        self.progress = 0
        self.max_duration = 30  # seconds

        self.create_widgets()

    def create_widgets(self):
        btn_frame = tk.Frame(self.root, bg="white")
        btn_frame.pack(pady=20)

        self.play_button = ttk.Button(btn_frame, text="\u23EF Play/Pause", command=self.play_pause_audio)
        self.play_button.grid(row=0, column=0, padx=10)

        self.skip_button = ttk.Button(btn_frame, text="\u23ED Skip", command=self.skip_stage)
        self.skip_button.grid(row=0, column=1, padx=10)

        self.rewind_button = ttk.Button(btn_frame, text="\u23EA Rewind", command=self.rewind_audio)
        self.rewind_button.grid(row=0, column=2, padx=10)

        self.choose_folder_button = tk.Button(root, text="Select Package", command=self.open_package_selector)
        self.choose_folder_button.pack()

        guess_frame = tk.Frame(self.root, bg="white")
        guess_frame.pack(pady=10)

        self.guess_button = ttk.Button(guess_frame, text="Guess", command=self.check_guess)
        self.guess_button.grid(row=0, column=1, padx=5)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(guess_frame, textvariable=self.search_var, width=30)
        self.search_entry.grid(row=0, column=0, padx=5)
        self.search_entry.bind("<KeyRelease>", self.update_search_suggestions)

        self.listbox_frame = tk.Frame(self.root, bg="white")
        self.listbox = tk.Listbox(self.listbox_frame, height=5, width=50)
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", self.select_song_from_listbox)

        self.feedback_label = tk.Label(self.root, text="", bg="white", fg="green", font=("Arial", 14))
        self.feedback_label.pack(pady=5)

        self.next_song_button = ttk.Button(self.root, text="Next Song", command=self.next_song)
        self.next_song_button.pack(pady=5)
        self.next_song_button.pack_forget()

        self.bars = []
        self.stage_labels = []  # Add this line to store label references

        for i in range(6):
            label = tk.Label(self.root, text=f"Stage {i+1}", bg="white", fg="black")
            label.pack(anchor="w", padx=20)
            self.stage_labels.append(label)

            bar = ttk.Progressbar(self.root, length=500, maximum=self.max_duration)
            bar.pack(pady=3)
            bar.bind("<Button-1>", self.on_progress_click)
            self.bars.append(bar)
        
        self.update_stage_highlight()

    def create_stage_widgets(self, num_stages):
        # Clear previous widgets
        for bar in self.bars:
            bar.destroy()
        for label in self.stage_labels:
            label.destroy()
        self.bars = []
        self.stage_labels = []

        for i in range(num_stages):
            label = tk.Label(self.root, text=f"Stage {i+1}", bg="white", fg="black")
            label.pack(anchor="w", padx=20)
            self.stage_labels.append(label)

            bar = ttk.Progressbar(self.root, length=500, maximum=self.max_duration)
            bar.pack(pady=3)
            bar.bind("<Button-1>", self.on_progress_click)
            self.bars.append(bar)
        self.update_stage_highlight()

    def mix_tracks(self):
        mixed = self.loaded_tracks[0]
        for i in range(1, self.stage + 1):
            mixed = mixed.overlay(self.loaded_tracks[i])
        mixed = mixed[:self.max_duration * 1000]

        # Use a new temp file each time
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            mixed.export(tmp.name, format="wav")
            self.current_mix_path = tmp.name  # Save path for playback

    def play_pause_audio(self):
        if not self.package_folder:
            self.feedback_label.config(text="Choose Packages First", fg="red")
            return

        if self.is_playing:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
            return

        self.is_playing = True
        self.is_paused = False
        self.progress = 0
        self.mix_tracks()
        pygame.mixer.music.load(self.current_mix_path)
        pygame.mixer.music.play()

        def update_progress():
            while self.progress < self.max_duration and self.is_playing:
                if not self.is_paused:
                    self.bars[self.stage]["value"] = self.progress
                    sleep(0.1)
                    self.progress += 0.1
                else:
                    sleep(0.1)  # wait briefly while paused
            if not self.is_paused:
                self.progress = 0
                self.bars[self.stage]["value"] = 0
                self.is_playing = False

        Thread(target=update_progress, daemon=True).start()

    def rewind_audio(self):
        if not self.package_folder:
            self.feedback_label.config(text="Choose Packages First", fg="red")
            return
        
        if not self.is_playing:
            return
        self.progress = max(self.progress - 5, 0)
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=self.progress)

    def skip_stage(self):
        if not self.package_folder:
            self.feedback_label.config(text="Choose Packages First", fg="red")
            return
        pygame.mixer.music.stop()
        self.is_playing = False  # Add this
        self.reset_progress()

        if self.stage < len(self.instruments) - 1:
            self.stage += 1
            self.update_stage_highlight()
        else:
            correct = os.path.basename(os.path.normpath(self.song_folder))
            self.feedback_label.config(text=f"{correct}", fg="red")
            self.next_song_button.pack()
            return

        self.reset_progress()

    def check_guess(self):
        if not self.package_folder:
            self.feedback_label.config(text="Choose Packages First", fg="red")
            return
        
        pygame.mixer.music.stop()
        self.is_playing = False
        user_guess = self.search_var.get().lower().strip()
        # Remove Artist Name
        if '-' in user_guess:
            user_guess = user_guess.split('-')[0].strip()

        correct = os.path.basename(os.path.normpath(self.song_folder))
        if user_guess.lower() in correct.lower():
            self.feedback_label.config(text="Correct! 🎉", fg="green")
            self.next_song_button.pack()
        else:
            self.skip_stage()
            self.feedback_label.config(text="Incorrect. Try again!", fg="red")

    def reset_progress(self):
        if self.stage < len(self.bars):
            self.bars[self.stage]["value"] = 0
        self.progress = 0
        self.search_var.set("")

    def reset_all_progress(self):
        for bar in self.bars:
            bar["value"] = 0
        self.progress = 0
        self.search_var.set("")

    def load_current_song(self):
        if self.current_song_index >= len(self.song_folders):
            self.feedback_label.config(text="🎵 You've finished all songs!", fg="blue")
            self.next_song_button.pack_forget()
            return
        
        self.song_folder = self.song_folders[self.current_song_index]
        print(f"Loading song: {self.song_folder}")
        self.stage = 0
        self.update_stage_highlight()
        self.reset_all_progress()
        self.load_stage_tracks()

    def load_stage_tracks(self):
        if not self.song_folder:
            return

        # song_folder should be a relative path like: Packages/package_name/htdemucs_6s/song_name
        # Extract only the part after "Packages/"
        relative_path = self.song_folder.split("Packages/")[-1]  # e.g. 'Songle/htdemucs_6s/Buddy Holly'
        encoded_folder = quote(relative_path)  # URL-safe path

        self.instruments = self.rank_instruments_by_band_psd(self.song_folder)
        self.create_stage_widgets(len(self.instruments))
        self.loaded_tracks = []

        for stage in self.instruments:
            track_url = f"{BASE_URL}/{encoded_folder}/{stage}.flac"
            try:
                temp_path = self.download_file_from_url(track_url)
                track = AudioSegment.from_file(temp_path)
                self.loaded_tracks.append(track)
            except Exception as e:
                print(f"Failed to load {track_url}: {e}")
                self.loaded_tracks.append(None)  # Preserve indexing even if load fails

    def update_search_suggestions(self, event=None):
        query = self.search_var.get().strip()
        if len(query) < 2:
            self.hide_listbox()
            return

        try:
            results = sp.search(q=query, type="track", limit=5)
            suggestions = []
            for item in results["tracks"]["items"]:
                name = item["name"]
                artist = item["artists"][0]["name"]
                suggestions.append(f"{name} - {artist}")

            self.listbox.delete(0, tk.END)
            for s in suggestions:
                self.listbox.insert(tk.END, s)

            if suggestions:
                self.show_listbox()
            else:
                self.hide_listbox()

        except Exception as e:
            print(f"Spotify search failed: {e}")

    def select_song_from_listbox(self, event):
        selection = self.listbox.curselection()
        if selection:
            selected = self.listbox.get(selection[0])
            self.search_var.set(selected)
            self.hide_listbox()

    def show_listbox(self):
        self.listbox_frame.place(x=self.search_entry.winfo_rootx() - self.root.winfo_rootx(),
                                y=self.search_entry.winfo_rooty() - self.root.winfo_rooty() + 25)
        self.listbox_frame.lift()

    def hide_listbox(self):
        self.listbox_frame.place_forget()

    def update_stage_highlight(self):
        for i, label in enumerate(self.stage_labels):
            if i == self.stage:
                label.config(fg="blue")  # Highlight current stage
            else:
                label.config(fg="black")  # Reset others

    def on_progress_click(self, event):
        if not self.is_playing:
            return
        bar = self.bars[self.stage]
        # Get width of the progress bar widget
        width = bar.winfo_width()
        # Calculate click position as fraction of total width
        click_x = event.x
        fraction = min(max(click_x / width, 0), 1)  # clamp between 0 and 1

        # Calculate new playback time
        new_pos = fraction * self.max_duration
        self.progress = new_pos

        # Restart playback at new position
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=new_pos)
        if self.is_paused:
            pygame.mixer.music.pause()  # keep paused if it was paused

        # Update progress bar immediately
        bar["value"] = new_pos

    def next_song(self):
        self.next_song_button.pack_forget()
        self.feedback_label.config(text="")
        self.current_song_index += 1
        self.load_current_song()

    def open_package_selector(self):
        selector = tk.Toplevel(self.root)
        selector.title("Select Packages")
        selector.geometry("300x400")

        tk.Label(selector, text="Select packages to include:").pack(pady=10)

        # Fetch package manifest from server
        try:
            response = requests.get(f"{BASE_URL}/list_packages")
            print(f"{BASE_URL}/list_packages")
            print(f"response: {response}")
            print(f"response text: {response.text}")
            response.raise_for_status()
            packages_manifest = response.json()
            print(packages_manifest)
        except Exception as e:
            self.feedback_label.config(text=f"Failed to fetch packages list: {e}", fg="red")
            print(e)
            return

        self.package_vars = {}
        for package_name in packages_manifest:
            var = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(selector, text=package_name, variable=var)
            chk.pack(anchor='w')
            self.package_vars[package_name] = var

        def confirm_selection():
            selected = [pkg for pkg, var in self.package_vars.items() if var.get()]
            if not selected:
                self.feedback_label.config(text="Select at least one package!", fg="red")
                return

            song_folders = []
            for package_name in selected:
                # From the manifest, get list of songs under htdemucs_6s for this package
                htdemucs_songs = packages_manifest.get(package_name, {}).get("htdemucs_6s", [])
                for song in htdemucs_songs:
                    # Compose remote folder path, matching your previous scheme (relative to /packages/)
                    folder_path = f"{package_name}/htdemucs_6s/{song}"
                    song_folders.append(folder_path)

            if not song_folders:
                self.feedback_label.config(text="No valid songs found in selected packages.", fg="red")
                return

            self.package_folder = None  # Since no local folder, or you can store BASE_URL
            self.song_folders = song_folders
            random.shuffle(self.song_folders)
            self.current_song_index = 0
            self.load_current_song()
            selector.destroy()

        ttk.Button(selector, text="Start Game", command=confirm_selection).pack(pady=10)

    @staticmethod
    def rank_instruments_by_band_psd(song_folder):
        """
        After renaming is done, return a list of instrument file numbers as strings,
        excluding any *_Quiet.flac files.
        For example: ['1', '2', '3', '5'] if those files exist.
        """
        numbered = []
        for fname in os.listdir(song_folder):
            if fname.lower().endswith(".flac") and "_quiet" not in fname.lower():
                name_no_ext = os.path.splitext(fname)[0]
                if name_no_ext.isdigit():
                    numbered.append(name_no_ext)

        # Sort numerically as strings
        return sorted(numbered, key=lambda x: int(x))

# === Run the GUI ===
if __name__ == "__main__":
    root = tk.Tk()
    gui = SongGameGUI(root)
    root.mainloop()
