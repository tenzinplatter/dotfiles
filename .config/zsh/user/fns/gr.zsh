unalias gama 2>/dev/null

cdp() {
    cd $HOME/Repositories/platform/packages/platform_$1
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
