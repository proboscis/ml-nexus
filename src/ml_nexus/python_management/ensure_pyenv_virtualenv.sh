#!/bin/bash

# Default values for environment variables
: "${PYENV_ROOT:="$HOME/.pyenv"}"
: "${PYTHON_VERSION:="3.11.0"}"  # 元のバージョンを保持
: "${VENV_NAME:="myenv"}"
: "${VENV_PATH:="$PWD/$VENV_NAME"}"
: "${PYENV_GIT_URL:="https://github.com/pyenv/pyenv.git"}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to log messages
log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function to check if directory is a git repository
is_git_repo() {
    git -C "$1" rev-parse --is-inside-work-tree >/dev/null 2>&1
}

# Initialize pyenv environment
init_pyenv_env() {
    export PYENV_ROOT="$PYENV_ROOT"
    export PATH="$PYENV_ROOT/bin:$PATH"
    if command_exists pyenv; then
        eval "$(pyenv init --path)"
        eval "$(pyenv init -)"
    else
        log_message "pyenv command not found after setting PATH"
        return 1
    fi
}

# Install pyenv if not already installed
install_pyenv() {
    local pyenv_bin="$PYENV_ROOT/bin/pyenv"

    # Check if pyenv binary exists and is executable
    if [ -x "$pyenv_bin" ]; then
        log_message "pyenv binary found, initializing..."
        init_pyenv_env
        return 0
    fi

    # If PYENV_ROOT exists but no pyenv binary, handle the git repo setup
    if [ -d "$PYENV_ROOT" ]; then
        if ! is_git_repo "$PYENV_ROOT"; then
            log_message "PYENV_ROOT exists but is not a git repository."
            # Try to initialize it as a git repo and add pyenv remote
            if git init "$PYENV_ROOT" && \
               cd "$PYENV_ROOT" && \
               git remote add origin "$PYENV_GIT_URL" && \
               git fetch && \
               git reset --hard origin/master; then
                log_message "Successfully initialized pyenv repository"
                cd - > /dev/null
            else
                log_message "Failed to initialize pyenv repository"
                return 1
            fi
        fi
    else
        log_message "Installing pyenv..."
        git clone "$PYENV_GIT_URL" "$PYENV_ROOT"
    fi

    init_pyenv_env
}

# Install Python version if not already installed
install_python() {
    if ! command_exists pyenv; then
        log_message "pyenv command not available"
        return 1
    fi

    if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
        log_message "Installing Python $PYTHON_VERSION..."
        pyenv install "$PYTHON_VERSION"
    else
        log_message "Python $PYTHON_VERSION already installed"
    fi
    pyenv global "$PYTHON_VERSION"
}

# Function to verify if a directory is a valid virtualenv
is_valid_virtualenv() {
    local venv_dir="$1"
    # Check for key virtualenv files/directories
    [ -f "$venv_dir/bin/activate" ] && \
    [ -d "$venv_dir/lib" ] && \
    [ -f "$venv_dir/pyvenv.cfg" ]
}

# Create and activate virtualenv using venv module
setup_virtualenv() {
    # If directory exists but is not a valid virtualenv, back it up
    if [ -d "$VENV_PATH" ] && ! is_valid_virtualenv "$VENV_PATH"; then
        local backup_dir="${VENV_PATH}_backup_$(date +%Y%m%d_%H%M%S)"
        log_message "Directory exists but is not a valid virtualenv. Removing contents in $VENV_PATH"
        # mv "$VENV_PATH" "$backup_dir"
        rm -rf "$VENV_PATH/*"
    fi

    if [ ! -d "$VENV_PATH" ] || ! is_valid_virtualenv "$VENV_PATH"; then
        log_message "Creating virtualenv at $VENV_PATH using venv module..."
        python -m venv "$VENV_PATH"
        if [ $? -ne 0 ] || ! is_valid_virtualenv "$VENV_PATH"; then
            log_message "Failed to create virtualenv"
            return 1
        fi
    else
        log_message "virtualenv already exists at $VENV_PATH"
    fi

    # Generate activation script
    cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
    chmod +x activate_venv.sh
    return 0
}

# Main execution
main() {
    log_message "Starting Python environment setup..."

    if ! install_pyenv; then
        log_message "Failed to set up pyenv"
        exit 1
    fi

    if ! install_python; then
        log_message "Failed to install Python"
        exit 1
    fi

    if ! setup_virtualenv; then
        log_message "Failed to set up virtualenv"
        exit 1
    fi

    log_message "Setup complete! To activate the virtualenv, run: source activate_venv.sh"
}

main