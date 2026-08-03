unalias gama 2>/dev/null

cdp() {
    cd $HOME/Repositories/platform/packages/platform_$1
}

# missim() {
#     # Unset the function temporarily to check for the real command
#     unset -f missim

#     # Check if missim command exists
#     if command -v missim > /dev/null 2>&1; then
#         # Call the actual missim command with all arguments
#         missim "$@"
#     else
#         # Source the virtual environment
#         local venv_path="$HOME/Repositories/missim/missim"

#         if [[ ! -f "$venv_path/bin/activate" ]]; then
#             echo "Error: Virtual environment not found at $venv_path"
#             # Restore the function before returning
#             source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
#             return 1
#         fi

#         # Source the virtual environment and call missim
#         source "$venv_path/bin/activate"

#         # Check if missim is now available
#         if command -v missim > /dev/null 2>&1; then
#             missim "$@"
#             # Deactivate venv after command execution
#             deactivate
#         else
#             echo "Error: missim command not found even after sourcing virtual environment"
#             # Deactivate venv and restore the function before returning
#             deactivate
#             source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
#             return 1
#         fi
#     fi

#     # Restore the function for next time
#     source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
# }

lookout() {
    # Unset the function temporarily to check for the real command
    unset -f lookout

    # Use environment variable if set (direnv in worktrees), otherwise hardcoded path
    local venv_path="${LOOKOUT_VENV_PATH:-$HOME/Repositories/lookout/lookout}"

    if [[ ! -f "$venv_path/bin/activate" ]]; then
        echo "Error: Virtual environment not found at $venv_path"
        # Restore the function before returning
        source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
        return 1
    fi

    # Source the virtual environment and call lookout
    source "$venv_path/bin/activate"

    # Check if lookout is now available
    if command -v lookout > /dev/null 2>&1; then
        command lookout "$@"
        # Deactivate venv after command execution
        deactivate
    else
        echo "Error: lookout command not found even after sourcing virtual environment"
        # Deactivate venv and restore the function before returning
        deactivate
        source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
        return 1
    fi

    # Restore the function for next time
    source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
}

gama() {
    # Unset the function temporarily to check for the real command
    unset -f gama

    # Source the virtual environment first
    local venv_path="$HOME/Repositories/gama/gama"

    if [[ ! -f "$venv_path/bin/activate" ]]; then
        echo "Error: Virtual environment not found at $venv_path"
        # Restore the function before returning
        source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
        return 1
    fi

    # Source the virtual environment and call gama
    source "$venv_path/bin/activate"

    # Check if gama is now available
    if command -v gama > /dev/null 2>&1; then
        command gama "$@"
        # Deactivate venv after command execution
        deactivate
    else
        echo "Error: gama command not found even after sourcing virtual environment"
        # Deactivate venv and restore the function before returning
        deactivate
        source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
        return 1
    fi

    # Restore the function for next time
    source "${ZDOTDIR:-$HOME/.config/zsh}/user/fns/gr.zsh"
}

set_platform_module() {
    local dir_name="${PWD:t}"
    export PLATFORM_MODULE="${dir_name}"
}

autoload -U add-zsh-hook
add-zsh-hook chpwd set_platform_module

pbc() {
    local install=""
    local deps=""
    local extra_flags=()

    # Parse options
    zparseopts -D -E -F i=install -install=install d=deps -deps=deps e=env -env=env || return 1

    # Check for '--' separator to split packages from extra flags
    local packages=()
    local found_separator=0
    for arg in "$@"; do
        if [[ "$arg" == "--" ]]; then
            found_separator=1
            continue  # Skip the '--' itself, don't add it to any array
        fi

        if [[ $found_separator -eq 0 ]]; then
            packages+=("$arg")
        else
            extra_flags+=("$arg")
        fi
    done

    # Get platform module from current directory
    local platform_module="${PWD:t}"

    if [[ -z "$env" ]]; then
      sr
    fi

    if [[ -n "$install" ]]; then
        platform pkg install-deps || return 1
    fi

    # Build colcon command
    local colcon_cmd=(colcon build --merge-install --install-base "/opt/greenroom/${platform_module}" --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON)

    # Add package selection flags if packages are specified
    if [[ ${#packages[@]} -gt 0 ]]; then
        if [[ -n "$deps" ]]; then
            colcon_cmd+=(--packages-up-to "${packages[@]}")
        else
            colcon_cmd+=(--packages-select "${packages[@]}")
        fi
    fi

    # Add extra flags if provided
    if [[ ${#extra_flags[@]} -gt 0 ]]; then
        colcon_cmd+=("${extra_flags[@]}")
    fi

    "${colcon_cmd[@]}"
}
