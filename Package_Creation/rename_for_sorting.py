import os
import string
import tkinter as tk
from tkinter import filedialog

def rename_files_to_letters(root_folder):
    subfolders = [
        os.path.join(root_folder, f)
        for f in os.listdir(root_folder)
        if os.path.isdir(os.path.join(root_folder, f))
    ]

    for folder in subfolders:
        print(f"\nRenaming files in: {folder}")
        files = [
            f for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))
        ]

        for i, file in enumerate(files):
            if i >= len(string.ascii_lowercase):
                print("⚠ Too many files, skipping extra ones.")
                break

            ext = os.path.splitext(file)[1]
            new_name = f"{string.ascii_lowercase[i]}{ext}"
            old_path = os.path.join(folder, file)
            new_path = os.path.join(folder, new_name)

            os.rename(old_path, new_path)
            print(f"Renamed: {file} → {new_name}")

def main():
    root = tk.Tk()
    root.withdraw()
    selected_folder = filedialog.askdirectory(title="Select Root Folder")

    if selected_folder:
        rename_files_to_letters(selected_folder)
    else:
        print("No folder selected.")

if __name__ == "__main__":
    main()
