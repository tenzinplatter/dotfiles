return {
  -- "folke/sidekick.nvim",
  "https://github.com/rmarganti/sidekick.nvim",
  branch = "herdr",
  opts = {
    nes = {
      enabled = false,
    },
    cli = {
      mux = {
        backend = "herdr",
        enabled = true,
      },
      tools = {
        claude = { native_scroll = true },
      },
    },
  },
  -- stylua: ignore
  init = function ()
    require("sidekick.nes").disable()
  end,
  keys = {
    {
      "<leader>as",
      function()
        require("sidekick.cli").send({ selection = true })
      end,
      mode = { "v" },
      desc = "Sidekick Send Visual Selection",
    },
    {
      "<leader>ap",
      function()
        require("sidekick.cli").prompt()
      end,
      mode = { "n", "v" },
      desc = "Sidekick Select Prompt",
    },
    {
      "<leader>ac",
      function()
        require("sidekick.cli").toggle({ name = "claude", focus = true })
      end,
      desc = "Sidekick Claude Toggle",
      mode = { "n", "v" },
    },
  },
}
