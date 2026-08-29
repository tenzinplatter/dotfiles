return {
  "ThePrimeagen/harpoon",
  branch = "harpoon2",
  enabled = false,
  dependencies = { "nvim-lua/plenary.nvim" },
  event = "BufEnter",
  config = function()
    local harpoon = require("harpoon")
    harpoon:setup()

    local helpers = require("tenzin.helpers")
    _G.harpoon_tabline = helpers.harpoon_tabline
    if not helpers.in_codediff() then
      vim.o.showtabline = 2
      vim.o.tabline = "%!v:lua.harpoon_tabline()"
    end

    for i = 1, 9 do
      vim.keymap.set("n", "<leader>" .. i, function()
        harpoon:list():select(i)
      end, { desc = "Harpoon file " .. i })
    end
  end,
  keys = {
    {
      "<leader>a",
      function()
        require("harpoon"):list():add()
        vim.cmd.redrawtabline()
      end,
      desc = "Harpoon add file",
    },
    {
      "<leader>h",
      function()
        require("harpoon").ui:toggle_quick_menu(require("harpoon"):list())
      end,
      desc = "Harpoon menu",
    },
    {
      "H",
      function()
        require("harpoon"):list():prev()
      end,
      desc = "Harpoon prev",
    },
    {
      "L",
      function()
        require("harpoon"):list():next()
      end,
      desc = "Harpoon next",
    },
  },
}
