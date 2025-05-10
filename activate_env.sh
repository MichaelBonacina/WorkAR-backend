#!/bin/bash

# This script must be run with 'source' or '.' command
# e.g., 'source activate_env.sh' or '. activate_env.sh'

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "ERROR: This script must be sourced, not executed directly."
    echo "Please run: source $(basename ${0})"
    exit 1
fi

# WorkAR Backend Activation Script
echo "Activating WorkAR backend environment..."

# Activate virtual environment
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/workar_env/bin/activate"

# Verify activation
if [[ "$(which python)" != *"workar_env"* ]]; then
    echo "WARNING: Virtual environment may not be activated correctly."
    echo "Expected python from workar_env, but got: $(which python)"
else
    echo "Environment activated successfully!"
fi

# Set any environment variables if needed
# export FLASK_APP=main.py
# export FLASK_ENV=development

echo "You can now run:"
echo "python main.py" 