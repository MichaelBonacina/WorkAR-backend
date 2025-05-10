#!/bin/bash
set -e

# WorkAR Backend Setup Script
echo "Setting up WorkAR backend environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "workar_env" ]; then
    echo "Creating virtual environment..."
    python -m venv workar_env
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment (only for this script)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/workar_env/bin/activate"

# Update pip
echo "Updating pip..."
python -m pip install --upgrade pip

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Setting up directories..."
mkdir -p media/tmp_frames

# Make the activate script executable
chmod +x activate_env.sh 2>/dev/null || true

echo "Setup complete!"
echo ""
echo "IMPORTANT: To activate the environment, you must run:"
echo "    source ./activate_env.sh"
echo ""
echo "Do NOT run it as 'bash activate_env.sh' or './activate_env.sh' 