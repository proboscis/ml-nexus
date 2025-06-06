#!/bin/bash

# This script ensures pyenv and a Python virtualenv are properly set up.
# It returns proper error codes if virtualenv creation fails.
# No fallback to temporary virtualenv - errors are propagated to the caller.
#
# Key features for mounted volume reuse:
# - Handles git ownership warnings for mounted pyenv directories
# - Attempts to reuse existing virtualenvs even with permission mismatches
# - Uses --clear flag to recreate virtualenvs in existing directories
# - Validates virtualenvs after creation to ensure they're usable

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
    
    # Handle git ownership issues for mounted volumes
    if [ -d "$PYENV_ROOT/.git" ]; then
        git config --global --add safe.directory "$PYENV_ROOT" 2>/dev/null || true
    fi
    
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
    
    # Handle git ownership issues first for any existing pyenv installation
    if [ -d "$PYENV_ROOT/.git" ]; then
        log_message "Configuring git to trust pyenv directory"
        git config --global --add safe.directory "$PYENV_ROOT" 2>/dev/null || true
    fi

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
               git config --global --add safe.directory "$PYENV_ROOT" && \
               git remote add origin "$PYENV_GIT_URL" && \
               git fetch && \
               git reset --hard origin/master; then
                log_message "Successfully initialized pyenv repository"
                cd - > /dev/null
            else
                log_message "Failed to initialize pyenv repository"
                return 1
            fi
        else
            # Existing git repo - make sure it's trusted
            git config --global --add safe.directory "$PYENV_ROOT" 2>/dev/null || true
        fi
    else
        log_message "Installing pyenv..."
        git clone "$PYENV_GIT_URL" "$PYENV_ROOT"
        git config --global --add safe.directory "$PYENV_ROOT" 2>/dev/null || true
    fi

    init_pyenv_env
}

# Install Python version if not already installed
install_python() {
    if ! command_exists pyenv; then
        log_message "pyenv command not available"
        return 1
    fi

    # Redirect stderr to avoid git warnings that are already handled
    if ! pyenv versions 2>/dev/null | grep -q "$PYTHON_VERSION"; then
        log_message "Installing Python $PYTHON_VERSION..."
        pyenv install "$PYTHON_VERSION" 2>&1 | grep -v "detected dubious ownership" || true
    else
        log_message "Python $PYTHON_VERSION already installed"
    fi
    pyenv global "$PYTHON_VERSION" 2>&1 | grep -v "detected dubious ownership" || true
}

# Function to verify if a directory is a valid virtualenv
is_valid_virtualenv() {
    local venv_dir="$1"
    # Check for key virtualenv files/directories
    # Also check if we can actually use it (permission check)
    if [ -f "$venv_dir/bin/activate" ] && \
       [ -d "$venv_dir/lib" ] && \
       [ -f "$venv_dir/pyvenv.cfg" ]; then
        # Try to read the activate script to verify permissions
        if [ -r "$venv_dir/bin/activate" ]; then
            return 0
        else
            log_message "Virtualenv exists but lacks read permissions"
            return 1
        fi
    else
        return 1
    fi
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
                # Use --clear flag if target exists
                local venv_flags=""
                if [ -d "$SYMLINK_TARGET" ]; then
                    venv_flags="--clear"
                    log_message "Target directory exists, using --clear flag"
                fi
                
                # Create virtualenv at the symlink target
                local venv_output
                local venv_exit_code
                venv_output=$(python -m venv $venv_flags "$SYMLINK_TARGET" 2>&1)
                venv_exit_code=$?
                
                if [ $venv_exit_code -eq 0 ]; then
                    log_message "Successfully created virtualenv at symlink target"
                    
                    # Verify symlink still points correctly
                    local current_target=$(readlink "$VENV_PATH")
                    if [ "$current_target" != "$SYMLINK_TARGET" ]; then
                        log_message "ERROR: Symlink was modified during virtualenv creation!"
                        return 1
                    fi
                    
                    # Verify the virtualenv is valid
                    if is_valid_virtualenv "$SYMLINK_TARGET"; then
                        log_message "Virtualenv validation successful"
                        # Generate activation script
                        cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
                        chmod +x activate_venv.sh
                        return 0
                    else
                        log_message "Created virtualenv but validation failed"
                        return 1
                    fi
                else
                    log_message "Failed to create virtualenv at symlink target (exit code: $venv_exit_code)"
                    log_message "Error output: $venv_output"
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
                    log_message "Directory exists but is not a valid virtualenv at $VENV_PATH"
                    # Check if directory is empty or nearly empty
                    local file_count=$(find "$VENV_PATH" -type f 2>/dev/null | wc -l)
                    if [ "$file_count" -le 1 ]; then
                        log_message "Directory is empty or nearly empty, will try to create virtualenv in it"
                    else
                        log_message "Directory contains $file_count files, attempting removal"
                        if rm -rf "$VENV_PATH" 2>/dev/null; then
                            log_message "Successfully removed existing directory"
                        else
                            log_message "Failed to remove existing directory due to permissions"
                            # Try to create virtualenv anyway - it might work
                            log_message "Will attempt to create virtualenv despite existing directory"
                        fi
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
        
        # Use --clear flag if target exists
        local venv_flags=""
        if [ -d "$TARGET_PATH" ]; then
            venv_flags="--clear"
            log_message "Target directory exists, using --clear flag"
        fi
        
        local venv_output
        local venv_exit_code
        venv_output=$(python -m venv $venv_flags "$TARGET_PATH" 2>&1)
        venv_exit_code=$?
        
        if [ $venv_exit_code -eq 0 ]; then
            log_message "Successfully created virtualenv at target path"
            
            # Create the final symlink if needed
            if [ ! -e "$VENV_PATH" ]; then
                ln -s "$TARGET_PATH" "$VENV_PATH"
                log_message "Created symlink: $VENV_PATH -> $TARGET_PATH"
            fi
            
            # Verify the virtualenv is valid
            if is_valid_virtualenv "$TARGET_PATH"; then
                log_message "Virtualenv validation successful"
                # Generate activation script
                cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
                chmod +x activate_venv.sh
                return 0
            else
                log_message "Created virtualenv but validation failed"
                return 1
            fi
        else
            log_message "Failed to create virtualenv at resolved path (exit code: $venv_exit_code)"
            log_message "Error output: $venv_output"
            debug_info
            return 1
        fi
    fi
    
    # Normal creation - no symlinks involved
    log_message "Creating virtualenv at $VENV_PATH using venv module..."
    # Try with --clear flag if directory exists to handle permission issues
    local venv_flags=""
    if [ -d "$VENV_PATH" ]; then
        venv_flags="--clear"
        log_message "Directory exists, using --clear flag for venv creation"
    fi
    
    # Capture stderr to see the actual error
    local venv_output
    local venv_exit_code
    venv_output=$(python -m venv $venv_flags "$VENV_PATH" 2>&1)
    venv_exit_code=$?
    
    if [ $venv_exit_code -eq 0 ]; then
        log_message "Successfully created virtualenv at $VENV_PATH"
        # Verify the virtualenv is valid
        if is_valid_virtualenv "$VENV_PATH"; then
            log_message "Virtualenv validation successful"
            # Generate activation script
            cat > activate_venv.sh << EOF
#!/bin/bash
source "$VENV_PATH/bin/activate"
EOF
            chmod +x activate_venv.sh
            return 0
        else
            log_message "Created virtualenv but validation failed"
            debug_info
            return 1
        fi
    else
        log_message "Failed to create virtualenv with venv module (exit code: $venv_exit_code)"
        log_message "Error output: $venv_output"
        debug_info
        return 1
    fi
}

# Main execution
main() {
    log_message "Starting Python environment setup..."
    
    # Set git safe directory early to prevent ownership warnings
    if [ -d "$PYENV_ROOT/.git" ]; then
        log_message "Pre-configuring git to trust pyenv directory"
        git config --global --add safe.directory "$PYENV_ROOT" 2>/dev/null || true
    fi

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