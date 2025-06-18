import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "Kneidel_venv"))
REPO_URL = "https://github.com/dennisvdang/chorus-detection.git"
REPO_DIR = os.path.join(VENV_DIR, "chorus-detection")  # Clone into venv folder

def run(cmd, check=True, **kwargs):
    print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, check=check, **kwargs)

def find_python_310():
    candidates = ["python3.10", "python3", "python"]
    for cmd in candidates:
        try:
            output = subprocess.check_output([cmd, "--version"], stderr=subprocess.STDOUT, text=True).strip()
            if output.startswith("Python 3.10"):
                print(f"Found Python 3.10 interpreter: {cmd} -> {output}")
                return cmd
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    raise RuntimeError("Python 3.10 interpreter not found on PATH. Please install it or specify its path manually.")

PYTHON_3_10_EXECUTABLE = find_python_310()

def create_venv():
    if os.path.exists(VENV_DIR):
        print(f"Virtual environment '{VENV_DIR}' already exists. Skipping creation.")
        return
    print(f"Creating virtual environment with Python 3.10: {VENV_DIR}")
    run([PYTHON_3_10_EXECUTABLE, "-m", "venv", VENV_DIR])

def get_python_path():
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")

def install_packages():
    python_path = get_python_path()
    print("Upgrading pip...")
    run([python_path, "-m", "pip", "install", "--upgrade", "pip"])
    print("Installing required packages: demucs, SoundFile")
    run([python_path, "-m", "pip", "install", "-U", "demucs", "SoundFile"])

def clone_repo():
    if os.path.exists(REPO_DIR):
        print(f"Repo folder '{REPO_DIR}' already exists. Skipping clone.")
        return
    print(f"Cloning repository {REPO_URL} into {REPO_DIR} ...")
    run(["git", "clone", REPO_URL, REPO_DIR])

def install_requirements():
    python_path = get_python_path()
    requirements_path = os.path.join(SCRIPT_DIR, "requirements.txt")
    if not os.path.isfile(requirements_path):
        print(f"Requirements file not found: {requirements_path}")
        return
    print(f"Installing requirements from {requirements_path} ...")
    run([python_path, "-m", "pip", "install", "-r", requirements_path])

def main():
    create_venv()
    install_packages()
    clone_repo()
    install_requirements()
    print("\nSetup complete! To activate your virtual environment:")
    if os.name == "nt":
        print(f"    {VENV_DIR}\\Scripts\\activate.bat")
    else:
        print(f"    source {VENV_DIR}/bin/activate")

if __name__ == "__main__":
    main()
