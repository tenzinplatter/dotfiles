vim.keymap.set("n", "zi", "za", { desc = "Toggle fold under cursor" })

vim.keymap.set("n", "<leader>w", function()
  vim.cmd("wall")
end, { desc = "Save all buffers" })

vim.keymap.set("n", "ZZ", function()
  -- Close all sidekick terminals if any are open
  require("persistence").save()

  local Terminal = require("sidekick.cli.terminal")
  for _, term in pairs(Terminal.terminals) do
    term:close()
  end

  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_valid(buf) and vim.bo[buf].buftype ~= "terminal" then
      if vim.bo[buf].modified then
        vim.api.nvim_buf_call(buf, function()
          vim.cmd("write")
        end)
      end
      vim.api.nvim_buf_delete(buf, { force = false })
    end
  end
  vim.cmd("quit")
end, { desc = "Save session, close all buffers and quit" })

vim.keymap.set("n", "<C-l>", "xp", { desc = "Swap character with next" })
vim.keymap.set("n", "<C-h>", "xhP", { desc = "Swap character with previous" })

vim.keymap.set({ "n", "v" }, "<leader>y", '"+y', { desc = "Copy to clipboard" })

vim.keymap.set("n", "<leader>%", "ggVG", { desc = "Select entire buffer" })

vim.keymap.set("n", "<leader>yy", '"+yy', { desc = "Copy line to clipboard" })

vim.keymap.set("v", "<leader>p", '"+p', { desc = "Paste from clipboard" })
vim.keymap.set("n", "<leader>p", '"+p', { desc = "Paste from clipboard" })

vim.keymap.set("n", "<leader>j", function()
  vim.cmd("cnext")
end, { desc = "Next quickfix item" })
vim.keymap.set("n", "<leader>k", function()
  vim.cmd("cprev")
end, { desc = "Previous quickfix item" })
vim.keymap.set("n", "<leader>qf", function()
  vim.cmd("copen")
end, { desc = "Open quickfix list" })

vim.keymap.set("n", "j", "gj", { desc = "Move down by display line" })
vim.keymap.set("n", "k", "gk", { desc = "Move up by display line" })

vim.keymap.set("n", "<C-c>", function()
  vim.cmd("nohlsearch")
end, { desc = "Clear search highlights" })

vim.keymap.set("n", "=", [[<cmd>vertical resize +5<cr>]], { desc = "Increase window width" })
vim.keymap.set("n", "-", [[<cmd>vertical resize -5<cr>]], { desc = "Decrease window width" })
vim.keymap.set("n", "+", [[<cmd>horizontal resize +2<cr>]], { desc = "Increase window height" })
vim.keymap.set("n", "_", [[<cmd>horizontal resize -2<cr>]], { desc = "Decrease window height" })

vim.keymap.set("v", "<C-j>", ":m '>+1<CR>gv=gv", { desc = "Move selection down" })
vim.keymap.set("v", "<C-k>", ":m '<-2<CR>gv=gv", { desc = "Move selection up" })

vim.keymap.set("n", "<C-j>", function()
  vim.cmd("move .+1")
  vim.cmd("normal! ==")
end, { desc = "Move line down" })

vim.keymap.set("n", "<C-k>", function()
  vim.cmd("move .-2")
  vim.cmd("normal! ==")
end, { desc = "Move line up" })

-- Terminal window navigation
vim.keymap.set("t", "<C-w>h", "<C-\\><C-n><C-w>h", { desc = "Navigate left from terminal" })
vim.keymap.set("t", "<C-w>j", "<C-\\><C-n><C-w>j", { desc = "Navigate down from terminal" })
vim.keymap.set("t", "<C-w>k", "<C-\\><C-n><C-w>k", { desc = "Navigate up from terminal" })
vim.keymap.set("t", "<C-w>l", "<C-\\><C-n><C-w>l", { desc = "Navigate right from terminal" })

vim.keymap.set("n", "q", function()
  for _, win in ipairs(vim.api.nvim_list_wins()) do
    if vim.api.nvim_win_get_config(win).relative ~= "" then
      vim.api.nvim_win_close(win, false)
      return
    end
  end
  vim.fn.feedkeys("q", "n")
end, { desc = "Close floating window or record macro" })

vim.keymap.set("v", "<", "<gv", { desc = "Indent left and reselect" })
vim.keymap.set("v", ">", ">gv", { desc = "Indent right and reselect" })

vim.keymap.set({ "n", "v" }, "<leader>hs", function()
  require("tenzin.helpers").herdr_shell_at_path()
end, { desc = "Open herdr shell at path under cursor" })

-- Split other windows with current buffer
vim.keymap.set("n", "<leader>wsh", function()
  require("tenzin.helpers").split_window_with_current_buffer("h", false)
end, { desc = "Split left window with current buffer" })

vim.keymap.set("n", "<leader>wsj", function()
  require("tenzin.helpers").split_window_with_current_buffer("j", false)
end, { desc = "Split bottom window with current buffer" })

vim.keymap.set("n", "<leader>wsk", function()
  require("tenzin.helpers").split_window_with_current_buffer("k", false)
end, { desc = "Split top window with current buffer" })

vim.keymap.set("n", "<leader>wsl", function()
  require("tenzin.helpers").split_window_with_current_buffer("l", false)
end, { desc = "Split right window with current buffer" })

vim.keymap.set("n", "<leader>wvh", function()
  require("tenzin.helpers").split_window_with_current_buffer("h", true)
end, { desc = "VSplit left window with current buffer" })

vim.keymap.set("n", "<leader>wvj", function()
  require("tenzin.helpers").split_window_with_current_buffer("j", true)
end, { desc = "VSplit bottom window with current buffer" })

vim.keymap.set("n", "<leader>wvk", function()
  require("tenzin.helpers").split_window_with_current_buffer("k", true)
end, { desc = "VSplit top window with current buffer" })

vim.keymap.set("n", "<leader>wvl", function()
  require("tenzin.helpers").split_window_with_current_buffer("l", true)
end, { desc = "VSplit right window with current buffer" })
