#!/bin/bash
# ===========================================
# Setup script for Writingway (macOS/Linux)
# ===========================================

# -------------------------------------------------
# Detect a suitable Python version (prefer 3.11)
# -------------------------------------------------
PYTHON_CMD=""

# Try python3.11 first (best compatibility)
if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_CMD="python3.11"
# Try python3.12
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_CMD="python3.12"
# Try python3.13
elif command -v python3.13 >/dev/null 2>&1; then
  PYTHON_CMD="python3.13"
# Fallback to generic python3 and check version
elif command -v python3 >/dev/null 2>&1; then
  PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
  case "$PY_VER" in
    3.11|3.12|3.13) PYTHON_CMD="python3" ;;
  esac
fi

if [ -z "$PYTHON_CMD" ]; then
  echo "ERROR: Python 3.11, 3.12, or 3.13 is required but was not found."
  echo "Please install Python 3.11 (recommended) from https://www.python.org/downloads/"
  exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1)
echo "Using $PY_VERSION ($PYTHON_CMD)"

# Check if the virtual environment folder exists.
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  $PYTHON_CMD -m venv venv
else
  echo "Virtual environment already exists."
  # Verify the venv Python version is acceptable
  VENV_VER=$(venv/bin/python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
  case "$VENV_VER" in
    3.11|3.12|3.13) ;;
    *)
      echo "WARNING: Existing venv uses Python $VENV_VER which may not be compatible."
      echo "Consider deleting the venv folder and rerunning this script."
      ;;
  esac
fi

# Activate the virtual environment.
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip.
echo "Upgrading pip..."
python -m pip install --upgrade pip

# Upgrade setuptools.
echo "Upgrading setuptools..."
python -m pip install --upgrade setuptools

# Install required packages from requirements.txt.
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Install spaCy English model if not already installed.
echo "Installing spaCy English model..."
python -m spacy download en_core_web_sm

# Add BeautifulSoup4 so that statistics.py can extract text from HTML files
python -m pip install beautifulsoup4

echo ""
echo "Setup complete!"

read -p "Press Enter to continue..."
