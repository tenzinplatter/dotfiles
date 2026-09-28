return {
  "https://github.com/windwp/nvim-autopairs",
  event = "InsertEnter",
  config = function()
    local npairs = require("nvim-autopairs")
    local Rule = require("nvim-autopairs.rule")
    local cond = require("nvim-autopairs.conds")
    npairs.setup({
      disable_filetype = { "TelescopePrompt", "vim" },
    })
    npairs.add_rule(Rule("<", ">"):with_pair(cond.none()):with_move(cond.done()))
  end,
}
