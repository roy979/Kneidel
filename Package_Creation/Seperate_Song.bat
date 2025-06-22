@echo off
echo Starting Demucs separation for: "Bodies.mp3"
cd /d "%~dp0"

"C:\Users\RoyWaisbord\anaconda3\python.exe" -m demucs "C:/Users/RoyWaisbord/OneDrive - Technion/Kneidel/Packages\Metal\Bodies.mp3" -n htdemucs_6s --shifts 10 --overlap 0.4 --flac -d cpu -o "C:/Users/RoyWaisbord/OneDrive - Technion/Kneidel/Packages\Metal"
if errorlevel 1 (
    echo Failed processing: "C:/Users/RoyWaisbord/OneDrive - Technion/Kneidel/Packages\Metal\Bodies.mp3"
    pause
    exit /b 1
)

echo Song processed successfully.
