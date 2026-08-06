-- local review = require("review")
-- local qc = require("review.quick_comments")

return {
  "vuki656/review.nvim",
  cmd = "Review",
  keys = {
    { "<leader>rv", "<cmd>Review<cr>", desc = "Toggle review" },
    -- {
    --   "<leader>rc",
    --   qc.add,
    --   desc = "Add comment on current line",
    -- },
    -- {
    --   "<leader>rc",
    --   qc.add_visual,
    --   desc = "Add comment on visual selection",
    --   mode = "v",
    -- },
    -- {
    --   "<leader>re",
    --   qc.export,
    --   desc = "Export review to clipboard",
    --   mode = "v",
    -- },
  },
  opts = {},
}
