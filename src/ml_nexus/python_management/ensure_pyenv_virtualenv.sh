#!/bin/bash

# This script ensures pyenv and a Python virtualenv are properly set up.
# It returns proper error codes if virtualenv creation fails.
# No fallback to temporary virtualenv - errors are propagated to the caller.

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

# Removed temp virtualenv creation - script now returns errors properly

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
            return 1
        fi
    fi

    if [ ! -w "$parent_dir" ]; then
        log_message "No write permission to parent directory $parent_dir"
        debug_info
        return 1
    fi

    # Check if VENV_PATH exists (as file, directory, or symlink)
    if [ -e "$VENV_PATH" ] || [ -L "$VENV_PATH" ]; then
        # Check if it's a symlink
        if [ -L "$VENV_PATH" ]; then
            # Get the direct symlink target (without resolving all symlinks in path)
            local SYMLINK_TARGET=$(readlink "$VENV_PATH")
            log_message "Detected symlink: $VENV_PATH -> $SYMLINK_TARGET"
            
            # Create parent directories at the target location if needed
            local target_parent=$(dirname "$SYMLINK_TARGET")
            if [ ! -d "$target_parent" ]; then
                log_message "Creating parent directory for symlink target: $target_parent"
                if ! mkdir -p "$target_parent" 2>/dev/null; then
                    log_message "Failed to create parent directory for symlink target"
                    debug_info
                    return 1
                fi
            fi
            
            # Check if target has a valid virtualenv
            if [ -d "$SYMLINK_TARGET" ] && is_valid_virtualenv "$SYMLINK_TARGET"; then
                log_message "Valid virtualenv already exists at symlink target: $SYMLINK_TARGET"
                return 0
            else
                log_message "Creating virtualenv at symlink target: $SYMLINK_TARGET"
                # Create virtualenv at the symlink target
                if python -m venv "$SYMLINK_TARGET"; then
                    log_message "Successfully created virtualenv at symlink target"
                    
                    # Verify symlink still points correctly
                    local current_target=$(readlink "$VENV_PATH")
                    if [ "$current_target" != "$SYMLINK_TARGET" ]; then
                        log_message "ERROR: Symlink was modified during virtualenv creation!"
                        return 1
                    fi
                    
                    # Generate activation script
                    cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
                    chmod +x activate_venv.sh
                    return 0
                else
                    log_message "Failed to create virtualenv at symlink target"
                    debug_info
                    return 1
                fi
            fi
        else
            # Not a symlink - check if it's a valid virtualenv directory
            if [ -d "$VENV_PATH" ]; then
                if is_valid_virtualenv "$VENV_PATH"; then
                    log_message "Valid virtualenv already exists at $VENV_PATH"
                    return 0
                else
                    log_message "Directory exists but is not a valid virtualenv. Removing $VENV_PATH"
                    if rm -rf "$VENV_PATH" 2>/dev/null; then
                        log_message "Successfully removed existing directory"
                    else
                        log_message "Failed to remove existing directory"
                        debug_info
                        return 1
                    fi
                fi
            fi
        fi
    fi

    # Path doesn't exist - check if parent directory is a symlink
    if [ -L "$parent_dir" ]; then
        # Parent is a symlink - get its direct target
        local PARENT_TARGET=$(readlink "$parent_dir")
        local VENV_NAME=$(basename "$VENV_PATH")
        local TARGET_PATH="$PARENT_TARGET/$VENV_NAME"
        
        log_message "Parent directory is a symlink: $parent_dir -> $PARENT_TARGET"
        log_message "Creating virtualenv at target path: $TARGET_PATH"
        
        # Ensure target parent exists
        if [ ! -d "$PARENT_TARGET" ]; then
            if ! mkdir -p "$PARENT_TARGET" 2>/dev/null; then
                log_message "Failed to create target parent directory"
                debug_info
                return 1
            fi
        fi
        
        if python -m venv "$TARGET_PATH"; then
            log_message "Successfully created virtualenv at target path"
            
            # Create the final symlink if needed
            if [ ! -e "$VENV_PATH" ]; then
                ln -s "$TARGET_PATH" "$VENV_PATH"
                log_message "Created symlink: $VENV_PATH -> $TARGET_PATH"
            fi
            
            # Generate activation script
            cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
            chmod +x activate_venv.sh
            return 0
        else
            log_message "Failed to create virtualenv at resolved path"
            debug_info
            return 1
        fi
    fi
    
    # Normal creation - no symlinks involved
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
        return 1
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