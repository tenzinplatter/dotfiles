return {
  "mrjones2014/smart-splits.nvim",
  -- Must load at startup: the kitty integration sets the IS_NVIM user-var then,
  -- so do NOT lazy-load this plugin.
  lazy = false,
  enabled = false,
  opts = {
    -- At a nvim window edge, hand off to the neighbouring kitty window.
    -- smart-splits' built-in kitty backend relies on the (uninstalled)
    -- neighboring_window.py kitten, so it can't make this move itself; this
    -- callback fires once the backend gives up and drives kitty natively.
    at_edge = function(ctx)
      -- Only hand off locally. Over SSH there's no KITTY_LISTEN_ON, so this
      -- no-ops and behaves like "stop" while the tmux backend owns the edge.
      local listen = vim.env.KITTY_LISTEN_ON
      if not listen or #listen == 0 then
        return
      end
      -- SmartSplitsDirection is 'left'|'right'|'up'|'down'; kitty wants top/bottom.
      local neighbor = ({ left = "left", right = "right", up = "top", down = "bottom" })[ctx.direction]
      if not neighbor then
        return
      end
      -- Focuses the neighbour if one exists (exit 0); errors harmlessly at the
      -- outer edge (exit 1, "no matching windows") so the cursor just stays put.
      vim.system({ "kitty", "@", "focus-window", "--match", "neighbor:" .. neighbor })
    end,
  },
  config = function(_, opts)
    local ss = require("smart-splits")
    ss.setup(opts)
    -- Seamless navigation across nvim windows, kitty splits, and tmux panes.
    -- smart-splits auto-detects the multiplexer (kitty locally, tmux when remote).
    vim.keymap.set({ "n", "t" }, "<M-h>", ss.move_cursor_left, { desc = "Navigate left (nvim/kitty/tmux)" })
    vim.keymap.set({ "n", "t" }, "<M-j>", ss.move_cursor_down, { desc = "Navigate down (nvim/kitty/tmux)" })
    vim.keymap.set({ "n", "t" }, "<M-k>", ss.move_cursor_up, { desc = "Navigate up (nvim/kitty/tmux)" })
    vim.keymap.set({ "n", "t" }, "<M-l>", ss.move_cursor_right, { desc = "Navigate right (nvim/kitty/tmux)" })
  end,
}
