local M = {}

-- Only show cursorline in the active window
vim.api.nvim_create_augroup("CursorLineOnlyInActiveWindow", { clear = true })
vim.api.nvim_create_autocmd({ "VimEnter", "WinEnter", "BufWinEnter" }, {
  group = "CursorLineOnlyInActiveWindow",
  callback = function()
    if vim.bo.filetype == "noice" then
      vim.opt_local.cursorline = false
      return
    end
    vim.opt_local.cursorline = true
  end,
})
vim.api.nvim_create_autocmd("WinLeave", {
  group = "CursorLineOnlyInActiveWindow",
  callback = function()
    vim.opt_local.cursorline = false
  end,
})

-- Split a different window and show current buffer in the new split
function M.split_window_with_current_buffer(direction, vertical)
  local current_win = vim.api.nvim_get_current_win()
  local current_buf = vim.api.nvim_get_current_buf()

  -- Try to move to the target window
  vim.cmd("wincmd " .. direction)
  local target_win = vim.api.nvim_get_current_win()

  -- Check if we actually moved to a different window
  if target_win == current_win then
    print("No window in that direction")
    return
  end

  -- Split the target window
  if vertical then
    vim.cmd("vsplit")
  else
    vim.cmd("split")
  end

  -- Set the new split to show the original buffer
  vim.api.nvim_win_set_buf(0, current_buf)

  -- Return to original window
  vim.api.nvim_set_current_win(current_win)
end

-- Go to definition in a split of a different window
function M.goto_definition_in_split(direction, vertical)
  local current_win = vim.api.nvim_get_current_win()
  local current_buf = vim.api.nvim_get_current_buf()

  -- Try to move to the target window
  vim.cmd("wincmd " .. direction)
  local target_win = vim.api.nvim_get_current_win()

  -- Check if we actually moved to a different window
  if target_win == current_win then
    print("No window in that direction")
    return
  end

  -- Split the target window
  if vertical then
    vim.cmd("vsplit")
  else
    vim.cmd("split")
  end

  -- Set the new split to show the original buffer
  vim.api.nvim_win_set_buf(0, current_buf)

  -- Go to definition in the new split
  vim.lsp.buf.definition()
end

-- Inlay hint preferences persistence
function M.load_inlay_hint_preferences()
  local data_path = vim.fn.stdpath("data") .. "/inlay-hints.json"
  local file = io.open(data_path, "r")

  if not file then
    return {}
  end

  local content = file:read("*all")
  file:close()

  local ok, decoded = pcall(vim.fn.json_decode, content)
  if ok and type(decoded) == "table" then
    return decoded
  end

  return {}
end

function M.save_inlay_hint_preference(filetype, enabled)
  local data_path = vim.fn.stdpath("data") .. "/inlay-hints.json"
  local preferences = M.load_inlay_hint_preferences()

  preferences[filetype] = enabled

  -- Ensure directory exists
  local data_dir = vim.fn.stdpath("data")
  vim.fn.mkdir(data_dir, "p")

  local ok, encoded = pcall(vim.fn.json_encode, preferences)
  if not ok then
    vim.notify("Failed to encode inlay hint preferences", vim.log.levels.ERROR)
    return
  end

  local file = io.open(data_path, "w")
  if not file then
    vim.notify("Failed to save inlay hint preferences", vim.log.levels.ERROR)
    return
  end

  file:write(encoded)
  file:close()
end

function M.get_inlay_hint_preference(filetype)
  local preferences = M.load_inlay_hint_preferences()
  return preferences[filetype]
end

function M.harpoon_tabline()
  local harpoon = require("harpoon")
  local list = harpoon:list()
  local current = vim.api.nvim_buf_get_name(0)
  local parts = {}

  for i = 1, list:length() do
    local item = list:get(i)
    if item then
      local name = vim.fn.fnamemodify(item.value, ":t")
      local is_active = current == vim.fn.fnamemodify(item.value, ":p")
      if is_active then
        table.insert(parts, "%#TabLineSel# " .. i .. " " .. name .. " %#TabLine#")
      else
        table.insert(parts, "%#TabLine# " .. i .. " " .. name .. " ")
      end
    end
  end

  if #parts == 0 then
    return "%#TabLine# harpoon: <leader>a to add %#TabLineFill#"
  end
  return table.concat(parts, "│") .. "%#TabLineFill#"
end

function M.in_codediff()
  local codediff_lifecycle = require("codediff.ui.lifecycle")
  local current_tab = vim.api.nvim_get_current_tabpage()
  return codediff_lifecycle.get_session(current_tab)
end

function M.in_herdr_session()
  return os.getenv("HERDR_ENV") == "1"
end

return M
