#!/usr/bin/env zsh

container_from_pid() {
    if [[ -z "$1" ]]; then
        echo "Usage: container_from_pid <pid>"
        return 1
    fi

    local pid=$1
    local cgroup_file="/proc/$pid/cgroup"

    if [[ ! -f "$cgroup_file" ]]; then
        echo "No such process: $pid"
        return 1
    fi

    local cgroup
    cgroup=$(<"$cgroup_file")

    # Try cgroup v1 (docker/<id>) and v2 (docker-<id>.scope)
    local container_id
    container_id=$(echo "$cgroup" | grep -oP '(?<=docker/)[a-f0-9]{64}' | head -1)
    if [[ -z "$container_id" ]]; then
        container_id=$(echo "$cgroup" | grep -oP '(?<=docker-)[a-f0-9]{64}(?=\.scope)' | head -1)
    fi

    if [[ -z "$container_id" ]]; then
        echo "PID $pid is not running in a Docker container"
        return 1
    fi

    docker inspect --format '{{.Name}}  ({{slice .Id 0 12}})' "$container_id" | sed 's|^/||'
}

mkdirc() {
    mkdir -p $1
    cd $1
}

txa() {
    if [[ -z "$1" ]]; then
        tmux attach-session
    else
        tmux attach-session -t "$1"
    fi
}

txn() {
    if [[ -z "$1" ]]; then
        tmux new-session
    else
        tmux new-session -s "$1"
    fi
}

nr() {
    if [ $# -eq 0 ]; then
        echo "Usage: nix-remove-many <package1> <package2> ..."
        echo "Example: nix-remove-many firefox git nodejs"
        return 1
    fi

    echo "Removing packages: $@"
    for package in "$@"; do
        echo "Removing: $package"
        nix-env -e "$package"
    done
}

ni() {
    # Check if at least one argument is provided
    if [[ $# -eq 0 ]]; then
        echo "Error: At least one package name is required"
        echo "Usage: nix-install <package1> [package2] [package3] ..."
        return 1
    fi

    # Loop through all arguments and try to install each package
    for package in "$@"; do
        echo "Installing package: $package"

        # Try to install the package using nix-env
        if nix-env -iA nixpkgs.$package; then
            echo "✅ Successfully installed: $package"
        else
            echo "❌ Failed to install: $package"
            echo "   Trying alternative installation method..."

            # Try installing without the nixpkgs prefix
            if nix-env -i $package; then
                echo "✅ Successfully installed: $package (alternative method)"
            else
                echo "❌ Failed to install: $package (both methods failed)"
            fi
        fi

        echo "---"
    done

    echo "Installation process completed for all packages."
}

inr() {
    sudo apt install ros-jazzy-$1
}

foxglove() {
    if ! command -v "ros2" >/dev/null 2>&1; then
        sr
    fi

    cmd="ros2 launch foxglove_bridge foxglove_bridge_launch.xml"

    if [[ ! -z "$1" ]]; then
        echo "Running: ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:="$1" > /dev/null 2>&1 &"
        ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:="$1" > /dev/null 2>&1 &
    else
        echo "Running: ros2 launch foxglove_bridge foxglove_bridge_launch.xml > /dev/null 2>&1 &"
        ros2 launch foxglove_bridge foxglove_bridge_launch.xml > /dev/null 2>&1 &
    fi
}

function findbin() {
    local purple='\e[1;35m' bright='\e[0;1m' green='\e[1;32m' reset='\e[0m'
    PM="pm.sh"
    # Try to find pm.sh in common locations
    if [ ! command -v "${PM}" ] &>/dev/null; then
        for path in "/usr/lib/hyde" "/usr/local/lib/hyde" "$HOME/.local/lib/hyde" "$HOME/.local/bin"; do
            if [[ -x "$path/pm.sh" ]]; then
                PM="$path/pm.sh"
                break
            else
                unset PM
            fi
        done
    fi

    if ! command -v "${PM}" &>/dev/null; then
        printf "${bright}${red}We cannot find package manager script (${purple}pm.sh${red}) from ${green}HyDE${reset}\n"
        return 127
    fi

    if ! "${PM}" fq "/usr/bin/$1"; then
        printf "${bright}${green}[ ${1} ]${reset} ${purple}NOT${reset} found in the system and no package provides it.\n"
        return 127
    else
        printf "${green}[ ${1} ] ${reset} might be provided by the above packages.\n"
        for entry in $entries; do
            # Assuming the entry already has ANSI color codes, we don't add more colors
            printf "  %s\n" "${entry}"
        done

    fi
    return 127
}

workon() {
    # idk from chatgpt
    setopt nullglob

    venv=""

    if [[ ! -z "$1" ]]; then
        venv=$1
    else
        # match hidden and normal dirs
        for d in */ .*/ ; do
            # $d ends in slash already, so don't include it in path
            if [[ -f "$d"bin/activate ]]; then
                venv=$d
                break
            fi
        done 2>/dev/null
    fi

    if [[ -z $venv ]]; then
        echo no venv found/provided, defaulting to \'.venv\'
        venv=".venv"
    elif [[ -d $venv && -f $venv/bin/activate ]]; then
        echo found venv \'$venv\', activating...
    else
        echo creating venv \'$venv\'
    fi

    if [[ ! -d $venv ]]; then
        python3 -m venv $venv
    fi

    source $venv/bin/activate
}

prepend-sudo() {
    # Store current cursor position
    local cursor_pos=$CURSOR

    # If buffer is empty or only whitespace, use last command from history
    if [[ -z "${BUFFER// }" ]]; then
        # Get the last command from history
        BUFFER=$(fc -ln -1)
        # Set cursor to end of buffer
        cursor_pos=${#BUFFER}
    fi

    # Trim leading whitespace from buffer
    local trimmed_buffer="${BUFFER#"${BUFFER%%[![:space:]]*}"}"

    # Check if command already starts with sudo
    if [[ "$trimmed_buffer" =~ ^sudo[[:space:]] ]]; then
        # Command already has sudo, do nothing
        return
    fi

    # Calculate how much whitespace was at the beginning
    local leading_space="${BUFFER%"$trimmed_buffer"}"

    # If there's any actual command content, prepend sudo
    if [[ -n "$trimmed_buffer" ]]; then
        BUFFER="${leading_space}sudo $trimmed_buffer"
        # Adjust cursor position (+5 for "sudo ")
        cursor_pos=$((cursor_pos + 5))
    else
        # Buffer was empty, just set to "sudo "
        BUFFER="sudo "
        cursor_pos=5
    fi

    # Restore cursor position
    CURSOR=$cursor_pos
}

swap() {
    # Check if exactly 2 arguments are provided
    if [[ $# -ne 2 ]]; then
        echo "Usage: swap <file1> <file2>"
        echo "Swaps the contents of two files"
        return 1
    fi

    local file1="$1"
    local file2="$2"

    # Check if both files exist
    if [[ ! -f "$file1" ]]; then
        echo "Error: '$file1' does not exist or is not a file"
        return 1
    fi

    if [[ ! -f "$file2" ]]; then
        echo "Error: '$file2' does not exist or is not a file"
        return 1
    fi

    # Check if files are readable and writable
    if [[ ! -r "$file1" || ! -w "$file1" ]]; then
        echo "Error: '$file1' is not readable or writable"
        return 1
    fi

    if [[ ! -r "$file2" || ! -w "$file2" ]]; then
        echo "Error: '$file2' is not readable or writable"
        return 1
    fi

    # Create a temporary file in the same directory as file1 for atomic operation
    local temp_file=$(mktemp "${file1}.swap.XXXXXX")

    # Perform the swap using a temporary file
    if cp "$file1" "$temp_file" && cp "$file2" "$file1" && cp "$temp_file" "$file2"; then
        rm "$temp_file"
        echo "Successfully swapped '$file1' and '$file2'"
    else
        # Clean up temp file if something went wrong
        [[ -f "$temp_file" ]] && rm "$temp_file"
        echo "Error: Failed to swap files"
        return 1
    fi
}

nvl() {
    eval "$(fc -ln -1)" | nvim -
}

newest() {
    ls -snew | tail -1
}

spicetify-refresh() {
    spicteify restore backup
    spicteify backup apply
}
