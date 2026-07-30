bindkey -e

export EDITOR=nvim

path=(
    $PATH
    ~/.cargo/bin
    ~/.npm-packages
    ~/scripts
    $HOME/.spicetify
    $HOME/.local/bin
    /usr/bin
    /usr/local/bin
    /usr/local/cuda-13.0/bin
    $HOME/bin
    $HOME/go/bin
    $HOME/.pixi/bin
    $HOME/.sdocs/bin
)
export PATH="${(j/:/)path}"

source "${ZDOTDIR:-$HOME}/load-modules.zsh"

export ZSH="$HOME/.oh-my-zsh"
export ZSH_THEME=""

export EDITOR="nvim"
export TERMINAL="kitty"
export NIXPKGS_ALLOW_UNFREE=1

export POKEGO_CACHE_AGE=300

export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/cuda-13.0/lib64
export LD_FLAGS="-fuse-ld=mold"

export MANPAGER='nvim +Man!'   
export CLAUDE_CODE_NO_FLICKER=1

setopt NO_AUTO_CD
setopt hist_ignore_all_dups

autoload -z edit-command-line

zle -N menu-search
zle -N recent-paths
zle -N edit-command-line

bindkey '\e\x7f' backward-kill-word
bindkey '^ ' autosuggest-accept
bindkey '' edit-command-line

# fn to run on change pwd
chpwd() {
  set_platform_module
}

# disable CTRL+S and CTRL+Q XON/XOFF
stty -ixon
eval "$(tv init zsh)"
[[ -f  "$HOME/.local/share/../bin/env" ]] && . "$HOME/.local/share/../bin/env"
