return {
  {
    "zbirenbaum/copilot.lua",
    enabled = false,
    cmd = "Copilot",
    event = "InsertEnter",
    keys = {
      {
        "<C-Space>",
        function()
          require("copilot.suggestion").accept()
        end,
        mode = "i",
        desc = "Accept Copilot suggestion",
      },
      {
        "<C-Right>",
        function()
          require("copilot.suggestion").accept_word()
        end,
        mode = "i",
        desc = "Accept Copilot word",
      },
      {
        "<M-L>",
        function()
          require("copilot-lsp.nes").apply_pending_nes()
          require("copilot-lsp.nes").walk_cursor_end_edit()
        end,
        mode = { "i", "n" },
        desc = "Accept and goto NES suggestion",
      },
    },
    opts = {
      suggestion = {
        auto_trigger = true,
        enabled = false,
        keymap = {
          accept = false,
          accept_word = false,
          accept_line = false,
        },
      },
      panel = {
        enabled = false,
      },
      nes = {
        enabled = false,
        keymap = {
          accept_and_goto = false,
          accept = false,
          dismiss = "<Esc>",
        },
      },
    },
  },
}
