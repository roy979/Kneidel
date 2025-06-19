import os
import random
import tempfile
import requests
import tkinter as tk
from tkinter import ttk
from threading import Thread
from time import sleep
import pygame
from pydub import AudioSegment
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ─── CONFIG & AUTH ────────────────────────────────────────────────────────────
GITHUB_USER    = "roy979"
GITHUB_REPO    = "Kneidel"
BASE_URL       = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/Packages"
API_BASE       = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages"
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN") or "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"
HEADERS        = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id="6856f3744c7f44a788d1973b8a61b244",
    client_secret="e67de1cb6dae45bcb2382d540d3b3de8"
))

pygame.mixer.init()

# ─── MAIN GUI CLASS ────────────────────────────────────────────────────────────
class Kneidel:
    def __init__(self, root):
        # State
        self.packages = []          # selected package names
        self.remote_songs = []      # e.g. ["Songle/Alive", …]
        self.local_queue = []       # paths to two preloaded songs
        self.current_index = 0

        # Tk setup
        self.root = root
        root.title("Kneidel")
        root.geometry("600x400")
        root.configure(bg="white")

        # Playback state
        self.stage       = 0
        self.is_playing  = False
        self.is_paused   = False
        self.progress    = 0
        self.max_dur     = 30

        self._build_widgets()

    # ─── WIDGET CREATION ────────────────────────────────────────────────────────
    def _build_widgets(self):
        # Top buttons
        btns = tk.Frame(self.root, bg="white"); btns.pack(pady=20)
        ttk.Button(btns, text="▶ Play/Pause", command=self._play_pause).grid(row=0, column=0, padx=5)
        ttk.Button(btns, text="⏭ Skip",       command=self._skip_stage).grid(row=0, column=1, padx=5)
        ttk.Button(btns, text="⏪ Rewind",     command=self._rewind).grid(row=0, column=2, padx=5)
        tk.Button(self.root, text="Select Package", command=self._select_packages).pack()

        # Guess entry
        gf = tk.Frame(self.root, bg="white"); gf.pack(pady=10)
        ttk.Button(gf, text="Guess", command=self._check_guess).grid(row=0, column=1, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(gf, textvariable=self.search_var, width=30)
        self.search_entry.grid(row=0, column=0, padx=5)
        self.search_entry.bind("<KeyRelease>", self.update_search_suggestions)

        # Autocomplete listbox
        self.listbox_frame = tk.Frame(self.root, bg="white")
        self.listbox = tk.Listbox(self.listbox_frame, height=5, width=50)
        self.listbox.pack()
        self.listbox.bind("<<ListboxSelect>>", self.select_song_from_listbox)

        # Feedback & next‑song
        self.feedback = tk.Label(self.root, text="", bg="white", font=("Arial", 14))
        self.feedback.pack(pady=5)
        self.next_btn = ttk.Button(self.root, text="Next Song", command=self._next_song)
        self.next_btn.pack(pady=5); self.next_btn.pack_forget()

        # Stage bars
        self.bars   = []
        self.labels = []
        for i in range(6):
            lbl = tk.Label(self.root, text=f"Stage {i+1}", bg="white")
            lbl.pack(anchor="w", padx=20)
            self.labels.append(lbl)

            bar = ttk.Progressbar(self.root, length=500, maximum=self.max_dur)
            bar.pack(pady=3)
            bar.bind("<Button-1>", self._seek)
            self.bars.append(bar)

    # ─── PACKAGE / SONG QUEUE LOGIC ──────────────────────────────────────────────
    def _select_packages(self):
        win = tk.Toplevel(self.root)
        win.title("Select Packages")
        win.geometry("300x400")
        tk.Label(win, text="Select packages:").pack(pady=10)

        # 1) fetch the list
        try:
            r = requests.get(API_BASE, headers=HEADERS); r.raise_for_status()
            pkgs = [i["name"] for i in r.json() if i["type"] == "dir"]
        except Exception as e:
            self.feedback.config(text=f"Error fetching packages: {e}", fg="red")
            return

        vars_ = {}
        for pkg in pkgs:
            b = tk.BooleanVar(value=False)
            tk.Checkbutton(win, text=pkg, variable=b).pack(anchor="w")
            vars_[pkg] = b

        start_btn = ttk.Button(win, text="Start Game")
        start_btn.pack(pady=10)

        def confirm():
            # 1) Immediately close the selector dialog
            win.destroy()

            # 2) Validate selection and give user feedback
            self.packages = [p for p, v in vars_.items() if v.get()]
            if not self.packages:
                return self.feedback.config(text="Pick at least one package!", fg="red")

            # 3) Show “Loading first song…” banner
            self.feedback.config(text="Loading first song…", fg="blue")

            # 4) Kick off Phase 1 in background
            def worker_phase1():
                try:
                    # build list of remote_songs
                    self.remote_songs.clear()
                    for pkg in self.packages:
                        url = f"{API_BASE}/{pkg}"
                        rr = requests.get(url, headers=HEADERS); rr.raise_for_status()
                        for item in rr.json():
                            if item["type"] == "dir":
                                self.remote_songs.append(f"{pkg}/{item['name']}")

                    if not self.remote_songs:
                        raise RuntimeError("No songs found in these packages")

                    random.shuffle(self.remote_songs)
                    self.current_index = 0
                    self.temp_root = tempfile.mkdtemp(prefix="kneidel_")
                    self.local_queue = []

                    # Phase 1: preload only the first song
                    self._preload(0)

                    # Once first is ready, on main thread call finish()
                    self.root.after(0, finish)

                except Exception as e:
                    # On error, show it on main thread
                    self.root.after(0, lambda: self.feedback.config(
                        text=f"Load error: {e}", fg="red"
                    ))

            Thread(target=worker_phase1, daemon=True).start()

        def finish():
            # Phase 1 complete: clear banner and show the first song
            self.feedback.config(text="")
            self._load_current()

            # Phase 2: download the second song quietly
            if len(self.remote_songs) > 1:
                def worker_phase2():
                    try:
                        self._preload(1)
                    except Exception:
                        pass
                Thread(target=worker_phase2, daemon=True).start()

        start_btn.config(command=confirm)
        
    def _preload(self, idx):
        """Download just one song folder (FLAC stems) into temp_root."""
        remote = self.remote_songs[idx]
        local_dir = os.path.join(self.temp_root, os.path.basename(remote))
        if not os.path.isdir(local_dir):
            os.makedirs(local_dir, exist_ok=True)
            api = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/Packages/{remote}"
            r = requests.get(api, headers=HEADERS); r.raise_for_status()
            for f in r.json():
                if f['type']=='file' and f['name'].endswith('.flac'):
                    data = requests.get(f['download_url'], headers=HEADERS).content
                    open(os.path.join(local_dir, f['name']), 'wb').write(data)
        self.local_queue.append(local_dir)

    def _load_current(self):
        """Load current from local_queue and preload the next+1 entry if any."""
        self.song_folder = self.local_queue[self.current_index]
        # preload next+1
        ni = self.current_index+2
        # reset UI
        self.stage = 0
        self._update_highlight()
        self._reset_bars()
        self._load_stems()

    # ─── STEM LOADING & PLAYBACK ──────────────────────────────────────────────────
    @staticmethod
    def _sorted_stems(folder):
        return sorted([n[:-5] for n in os.listdir(folder)
                       if n.endswith(".flac") and "_Quiet" not in n],
                      key=int)

    def _load_stems(self):
        stems = self._sorted_stems(self.song_folder)
        self._create_stage_widgets(len(stems))
        self.loaded = [AudioSegment.from_file(os.path.join(self.song_folder, f"{s}.flac"))
                       for s in stems]

    def mix_tracks(self):
        mix = self.loaded[0]
        for i in range(1, self.stage+1):
            mix = mix.overlay(self.loaded[i])
        return mix[:int(self.max_dur*1000)]

    def _play_pause(self):
        if not self.packages:
            return self.feedback.config(text="Choose Packages", fg="red")

        if self.is_playing:
            # toggle pause/unpause
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
            return

        # start new playback
        self.is_playing = True
        self.is_paused  = False
        self.progress   = 0

        # mix stems
        mix = self.mix_tracks()

        # create a temp WAV file
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)                   # close the low‐level FD so pygame can open it
        mix.export(path, format="wav") # actually write the file

        # load & play
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception as e:
            print("Playback load error:", e)
            return

        # update progress bar in background
        def updater():
            while self.progress < self.max_dur and self.is_playing:
                try:
                    if not self.is_paused:
                        self.bars[self.stage]["value"] = self.progress
                        sleep(0.1)
                        self.progress += 0.1
                    else:
                        sleep(0.1)
                except tk.TclError:
                    # widget was destroyed, stop updating
                    break

            # Final cleanup
            self.is_playing = False
            try:
                self.bars[self.stage]["value"] = 0
            except:
                pass
            # delete temp file if needed…
        Thread(target=updater, daemon=True).start()


    def _rewind(self):
        if self.is_playing:
            self.progress = max(0, self.progress-5)
            pygame.mixer.music.play(start=self.progress)

    def _skip_stage(self):
        self.search_var.set("")
        if self.stage < len(self.loaded)-1:
            pygame.mixer.music.stop(); self.is_playing=False
            self.stage += 1; self._reset_bars(); self._update_highlight()
            self.feedback.config(text="")
        else:
            correct = os.path.basename(self.song_folder)
            self.feedback.config(text=correct, fg="green")
            self.next_btn.pack()

    def _check_guess(self):
        if not self.packages:
            return self.feedback.config(text="Choose Packages", fg="red")
        pygame.mixer.music.stop(); self.is_playing=False
        guess = self.search_var.get().split('-')[0].strip().lower()
        answer = os.path.basename(self.song_folder).lower()
        if answer in guess or guess == 'vizen gay':
            self.feedback.config(text="Correct! 🎉", fg="green"); self.next_btn.pack()
        else:
            self._skip_stage(); self.feedback.config(text="Incorrect", fg="red")

    def _next_song(self):
        # Stop any current playback and clear the “Next Song” button and feedback
        pygame.mixer.music.stop()
        self.next_btn.pack_forget()
        self.feedback.config(text="")
        self.search_var.set("selected")

        # Advance our index
        self.current_index += 1

        # If we’ve run out of songs, let the user know
        if self.current_index >= len(self.remote_songs):
            return self.feedback.config(text="All done!", fg="blue")

        # -- Phase A: load the newly current (it should already be in self.local_queue)
        self._load_current()

        # -- Phase B (background): preload the *next* song (index+1) if it exists
        next_idx = self.current_index + 1
        if next_idx < len(self.remote_songs):
            def bg_preload():
                try:
                    self._preload(next_idx)
                except Exception as e:
                    # you could log this if you like
                    print("Preload error:", e)
            Thread(target=bg_preload, daemon=True).start()


    def _finish_next(self):
        self.feedback.config(text="")
        if self.current_index >= len(self.remote_songs):
            return self.feedback.config(text="All done!", fg="blue")
        self._load_current()

    # ─── STAGE WIDGET HELPERS ────────────────────────────────────────────────────
    def _create_stage_widgets(self, n):
        for w in self.bars+self.labels:
            w.destroy()
        self.bars, self.labels = [], []
        for i in range(n):
            lbl = tk.Label(self.root, text=f"Stage {i+1}", bg="white")
            lbl.pack(anchor='w', padx=20); self.labels.append(lbl)
            bar = ttk.Progressbar(self.root, length=500, maximum=self.max_dur)
            bar.pack(pady=3); bar.bind("<Button-1>", self._seek); self.bars.append(bar)
        self._update_highlight()

    def _update_highlight(self):
        for i,l in enumerate(self.labels):
            l.config(fg="blue" if i==self.stage else "black")

    def _reset_bars(self):
        for b in self.bars: b['value']=0

    def _seek(self, e):
        if not self.is_playing: return
        frac = max(0, min(1, e.x / e.widget.winfo_width()))
        self.progress = frac*self.max_dur
        pygame.mixer.music.play(start=self.progress)

    # ─── SPOTIFY AUTOCOMPLETE ────────────────────────────────────────────────────
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

# ─── RUN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    Kneidel(root)
    root.mainloop()
