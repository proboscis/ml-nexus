#!/bin/bash

# Default values for environment variables
: "${PYENV_ROOT:="$HOME/.pyenv"}"
: "${PYTHON_VERSION:="3.11"}"
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

# Function for detailed debugging
debug_info() {
    log_message "===== DEBUGGING INFORMATION ====="
    log_message "Current user: $(whoami)"
    log_message "Current directory: $(pwd)"
    log_message "PYENV_ROOT: $PYENV_ROOT"
    log_message "PYTHON_VERSION: $PYTHON_VERSION"
    log_message "VENV_PATH: $VENV_PATH"

    # Check Python and venv
    log_message "Python executable: $(which python || echo 'Not found')"
    log_message "Python version: $(python --version 2>&1 || echo 'Failed to get version')"

    # Check directory permissions
    log_message "Parent directory for VENV_PATH: $(dirname "$VENV_PATH")"
    log_message "Parent directory exists? $([ -d "$(dirname "$VENV_PATH")" ] && echo 'Yes' || echo 'No')"

    if [ -d "$(dirname "$VENV_PATH")" ]; then
        log_message "Parent directory permissions: $(ls -ld "$(dirname "$VENV_PATH")")"
        log_message "Can write to parent directory? $([ -w "$(dirname "$VENV_PATH")" ] && echo 'Yes' || echo 'No')"
    fi

    # Try creating a test file to verify write permissions
    local test_file="$(dirname "$VENV_PATH")/test_write_$$"
    if touch "$test_file" 2>/dev/null; then
        log_message "Successfully created test file: $test_file"
        rm -f "$test_file"
    else
        log_message "Failed to create test file in parent directory"
    fi

    # Check disk space
    log_message "Disk space available: $(df -h "$(dirname "$VENV_PATH")" | tail -n 1)"

    # Check for existing venv directory
    if [ -d "$VENV_PATH" ]; then
        log_message "VENV_PATH exists as a directory"
        log_message "VENV_PATH permissions: $(ls -ld "$VENV_PATH")"
        log_message "VENV_PATH contents: $(ls -la "$VENV_PATH" | head -n 10)"
    else
        log_message "VENV_PATH directory does not exist"
    fi

    log_message "===== END DEBUGGING INFO ====="
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

# Create a temp directory virtualenv if we can't write to the specified location
create_temp_virtualenv() {
    local temp_venv_dir="$(mktemp -d -t venv-XXXXXX 2>/dev/null || echo "/tmp/temp_venv_$$")"
    if [ ! -d "$temp_venv_dir" ]; then
        mkdir -p "$temp_venv_dir" 2>/dev/null
    fi

    if [ ! -d "$temp_venv_dir" ] || [ ! -w "$temp_venv_dir" ]; then
        log_message "Failed to create temporary directory for virtualenv"
        return 1
    fi

    log_message "Creating temporary virtualenv at $temp_venv_dir"
    if python -m venv "$temp_venv_dir"; then
        log_message "Successfully created temporary virtualenv"
        log_message "To use this virtualenv, run: source $temp_venv_dir/bin/activate"

        # Create a symlink if possible
        if [ ! -e "$VENV_PATH" ] && [ -w "$(dirname "$VENV_PATH")" ]; then
            ln -sf "$temp_venv_dir" "$VENV_PATH"
            log_message "Created symlink from $VENV_PATH to $temp_venv_dir"
        else
            log_message "WARNING: Could not create symlink from $VENV_PATH to temporary virtualenv"
            log_message "Please use the temporary virtualenv directly"
        fi

        # Generate activation script for the temp virtualenv
        cat > activate_temp_venv.sh << EOF
#!/bin/bash
source "$temp_venv_dir/bin/activate"
EOF
        chmod +x activate_temp_venv.sh
        return 0
    else
        log_message "Failed to create temporary virtualenv"
        return 1
    fi
}

# Create virtualenv using Python's built-in venv module
setup_virtualenv() {
    # Check for permission to create the virtualenv directory
    local parent_dir="$(dirname "$VENV_PATH")"
    if [ ! -d "$parent_dir" ]; then
        log_message "Parent directory $parent_dir does not exist"
        if mkdir -p "$parent_dir" 2>/dev/null; then
            log_message "Created parent directory $parent_dir"
        else
            log_message "Failed to create parent directory $parent_dir"
            debug_info
            log_message "Attempting to create a temporary virtualenv instead"
            create_temp_virtualenv
            return $?
        fi
    fi

    if [ ! -w "$parent_dir" ]; then
        log_message "No write permission to parent directory $parent_dir"
        debug_info
        log_message "Attempting to create a temporary virtualenv instead"
        create_temp_virtualenv
        return $?
    fi

    # If directory exists but is not a valid virtualenv, clean it up
    if [ -d "$VENV_PATH" ]; then
        if ! is_valid_virtualenv "$VENV_PATH"; then
            log_message "Directory exists but is not a valid virtualenv. Removing $VENV_PATH"
            if rm -rf "$VENV_PATH" 2>/dev/null; then
                log_message "Successfully removed existing directory"
            else
                log_message "Failed to remove existing directory"
                debug_info
                log_message "Attempting to create a temporary virtualenv instead"
                create_temp_virtualenv
                return $?
            fi
        else
            log_message "Valid virtualenv already exists at $VENV_PATH"
            return 0
        fi
    fi

    log_message "Creating virtualenv at $VENV_PATH using venv module..."
    if python -m venv "$VENV_PATH"; then
        log_message "Successfully created virtualenv at $VENV_PATH"
        # Generate activation script
        cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
        chmod +x activate_venv.sh
        return 0
    else
        log_message "Failed to create virtualenv with venv module"
        debug_info
        log_message "Attempting to create a temporary virtualenv instead"
        create_temp_virtualenv
        return $?
    fi
}

# Main execution
main() {
    log_message "Starting Python environment setup..."

    if ! install_pyenv; then
        log_message "Failed to set up pyenv"
        debug_info
        exit 1
    fi

    if ! install_python; then
        log_message "Failed to install Python"
        debug_info
        exit 1
    fi

    if ! setup_virtualenv; then
        log_message "Failed to set up virtualenv"
        debug_info
        exit 1
    fi

    log_message "Setup complete! To activate the virtualenv, run: source $VENV_PATH/bin/activate"
}

main