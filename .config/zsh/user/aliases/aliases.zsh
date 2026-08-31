[[ -f ~/.zsh/machine.zsh ]] && source ~/.zsh/machine.zsh

alias suspend="systemctl suspend"

alias cpwd="pwd | tr -d '\n' | wl-copy"
alias yz="yazi"
alias dash="gh dash"
alias nvc="cd ~/.config; nv; cd -"

alias cl="claude"
alias yz="yazi"

alias capson="sudo systemctl enable --now udevmon"
alias capsoff="sudo systemctl disable --now udevmon"

alias dk="docker"
alias dcu="docker compose up -d"
alias dcub="docker compose up -d --build"
alias dkc="docker compose"

alias srz="source $ZDOTDIR/.zshrc"
alias new="exec zsh"

alias killpgad="kill $(pidof $HOME/.scripts/open_pgadmin.sh)"
alias workoff="deactivate"
alias cinit='eval "$($HOME/anaconda3/bin/conda shell.zsh hook)" && conda init'
alias pgres="sudo -u postgres -i /bin/bash"

alias gdb="gdb --tui"
alias cx="chmod u+x"
alias ff="pokego -r 1 --no-title | fastfetch --file-raw -"
alias c="clear"
alias cat='bat'
alias mk="make"
alias cc="clang"
alias p='python'
alias python="python3"
alias mkdir="mkdir -p"
alias rmd="rm -rf"

alias db='distrobox'
alias dbr="distrobox enter ros"
alias dbs="distrobox enter siri"

alias tmuxkill="tmux kill-session"
alias srtx="tmux source ~/.tmux.conf"
alias tx="tmux"

alias pkginfo="pacman -Qq | tv --preview-command 'pacman -Qil {0} | bat -fpl yml'"

alias ..='cd ..'
alias ...='cd ../..'
alias .3='cd ../../..'
alias .4='cd ../../../..'
alias .5='cd ../../../../..'

alias zb="zen-browser"
alias icat="kitten icat"
alias ks="kitten ssh"

alias cw="y .worktrees "
