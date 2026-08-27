return {
  "mrcjkb/rustaceanvim",
  lazy = false,
  config = function()
    vim.g.rustaceanvim = {
      tools = {},
      server = {
        default_settings = {
          -- rust-analyzer language server configuration
          ["rust-analyzer"] = {
            rust = {
              analyzerTargetDir = true,
            },
            files = {
              excludeDirs = { ".pixi", "target" },
            },
            cargo = {
              features = "all",
            },
            checkOnSave = {
              command = "check",
            },
          },
        },
      },
    }
  end,
}
