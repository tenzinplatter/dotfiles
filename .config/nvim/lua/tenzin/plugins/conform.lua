return {
  "stevearc/conform.nvim",
  opts = {
    default_format_opts = {
      lsp_format = "fallback",
    },
    formatters_by_ft = {
      python = { "ruff_organize_imports", "ruff_format" },
      c = { "clang-format" },
      cpp = { "clang-format" },
      lua = { "stylua" },
      yaml = { "yamlfmt" },
      rust = { "rustfmt" },
      ts = { "prettier" },
      javascript = { "prettier" },
      javascriptreact = { "prettier" },
      typescript = { "prettier" },
      typescriptreact = { "prettier" },
      bash = { "beautysh" },
      zsh = { "beautysh" },
      sh = { "beautysh" },
      html = { "prettier" },
      toml = { "taplo" },
      go = { "gofmt" }
    },
    formatters = {
      ruff_format = {
        args = { "format", "--stdin-filename", "$FILENAME", "-" },
      },
    },
  },
  keys = {
    {
      "<leader>=",
      function()
        require("conform").format()
      end,
      mode = { "n" },
    },
    {
      "<leader>=",
      function()
        require("conform").format({
          range = {
            start = { vim.fn.line("'<"), 0 },
            ["end"] = { vim.fn.line("'>"), 0 },
          },
        })
      end,
      mode = "v",
      desc = "Format selection",
    },
  },
}
