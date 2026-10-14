alias nvcg="cd ~/.config/greenroom && nv && cd -"

alias gvr="gama vessel down && gama vessel up"
alias gv="gama vessel"

alias ss5="ssh gr@10.71.11.33"
alias ssr="ssh rock@rock-5b"
alias ssb="ssh gr@blueboat"
alias ssp="ssh pandora@pandora"
alias ssj="ssh gr@lookout-tack-amcs"
alias ssc="ssh gr-clanker"
alias ssgp="ssh gr-sim-perth@gr-sim-perth"
alias ssl1="ssh gr@lookout-1-carrack-leidos-au"
alias ssl2="ssh gr@lookout-2-carrack-leidos-au"
alias ssm="ssh gr@gr-monolith"

alias cb="colcon build"
alias cbuild="colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
alias cbuilds="colcon build --symlink-install --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
alias pbuild="platform ros build -- --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"

alias pub="pixi publish --to /tmp/gr-dev-channel"
