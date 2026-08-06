return {
  "vuki656/review.nvim",
  config = function()
    require("review").setup()
    local qc = require("review.quick_comments")
    vim.keymap.set("n", "<leader>rv", "<cmd>Review<cr>", { desc = "Toggle review" })
    vim.keymap.set("n", "<leader>rc", qc.add, { desc = "Add comment on current line" })
    vim.keymap.set("v", "<leader>rc", qc.add_visual, { desc = "Add comment on visual selection" })
    vim.keymap.set("n", "<leader>re", qc.export, { desc = "Export review to clipboard" })
  end,
}
