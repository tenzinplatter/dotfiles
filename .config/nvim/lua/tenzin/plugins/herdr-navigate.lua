return {
  "bojackduy/nvim-herdr-navigation",
  submodules = false,
  cond = function()
    return vim.env.HERDR_PANE_ID ~= nil
  end,
  event = "VeryLazy",
  init = function(plugin)
    vim.opt.rtp:prepend(plugin.dir .. "/nvim-herdr-navigation")
  end,
  config = function()
    vim.schedule(function()
      local nav = require("herdr-navigation")
      local keybindings = {
        left = "<M-h>",
        down = "<M-j>",
        up = "<M-k>",
        right = "<M-l>",
      }
      nav.setup({ keybindings = keybindings })
      for direction, lhs in pairs(keybindings) do
        vim.keymap.set("t", lhs, function()
          nav.navigate(direction)
        end, { silent = true, desc = "Herdr navigate " .. direction })
      end
    end)
  end,
}
