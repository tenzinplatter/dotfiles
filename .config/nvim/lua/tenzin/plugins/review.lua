return {
  "vuki656/review.nvim",
  config = function()
    local review = require("review")
    review.setup()
    local qc = require("review.quick_comments")
    vim.keymap.set("n", "<leader>rv", "<cmd>Review<cr>", { desc = "Toggle review" })
    vim.keymap.set("n", "<leader>rc", qc.add, { desc = "Add comment on current line" })
    vim.keymap.set("v", "<leader>rc", qc.add_visual, { desc = "Add comment on visual selection" })
    vim.keymap.set("n", "<leader>rC", review.clear_comments, { desc = "Clear all comments" })
    vim.keymap.set("n", "<leader>rt", qc.toggle_panel, { desc = "Toggle quick comment panel" })
    vim.keymap.set("n", "<leader>re", qc.export, { desc = "Export review to clipboard" })
    vim.keymap.set("n", "<leader>rE", qc.export, { desc = "Export review to clipboard and clear comments" })
  end,
}
