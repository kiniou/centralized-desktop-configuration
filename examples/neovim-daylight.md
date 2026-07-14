# Recipe: make Neovim follow `desktopctl light` / `desktopctl dark`

Swapping a terminal's theme doesn't reach the editor already running inside it —
Neovim keeps the colors it drew at startup. Instead of pushing into Neovim,
let it *react* to the mode `desktopctl` already records at
`${XDG_STATE_HOME:-~/.local/state}/desktopctl/daylight`.

This needs **no `daylight.toml` entry**: every Neovim instance reads the mode at
startup and watches the file for changes, so instances opened later are correct
too. It works with any colorscheme that honours `&background` (solarized,
gruvbox, tokyonight, …).

## Module

Drop this in your config, e.g. `~/.config/nvim/lua/daylight.lua`:

```lua
-- Follow `desktopctl light` / `desktopctl dark` automatically.
local M = {}

local uv = vim.uv or vim.loop
local state = (vim.env.XDG_STATE_HOME or vim.fn.expand("~/.local/state"))
  .. "/desktopctl/daylight"

local function apply(mode)
  if mode ~= "dark" and mode ~= "light" then
    return
  end
  vim.o.background = mode
  -- Re-source the active colorscheme so its palette follows the new background.
  if vim.g.colors_name then
    pcall(vim.cmd.colorscheme, vim.g.colors_name)
  end
end

local function read_mode()
  local f = io.open(state, "r")
  if not f then
    return nil
  end
  local line = f:read("l")
  f:close()
  return line and line:gsub("%s+", "")
end

function M.setup()
  if M._handle then
    return -- already watching
  end
  apply(read_mode()) -- correct theme at startup

  local dir = vim.fn.fnamemodify(state, ":h")
  local fname = vim.fn.fnamemodify(state, ":t")
  vim.fn.mkdir(dir, "p") -- ensure the watched directory exists

  local handle = uv.new_fs_event()
  M._handle = handle
  handle:start(dir, {}, vim.schedule_wrap(function(err, filename)
    if not err and (filename == nil or filename == fname) then
      apply(read_mode())
    end
  end))
end

return M
```

## Wiring it in

Call `setup()` **after** your colorscheme has loaded, so `vim.g.colors_name`
is set and the startup re-apply takes effect.

- **Plain `init.lua`:** after your `vim.cmd.colorscheme(...)` line:
  ```lua
  require("daylight").setup()
  ```

- **lazy.nvim / LazyVim:** call it from the `config` of your colorscheme spec
  (put the module at `lua/config/daylight.lua` and require `"config.daylight"`):
  ```lua
  config = function(_, opts)
    require("solarized").setup(opts)
    vim.cmd.colorscheme("solarized")
    require("config.daylight").setup()
  end,
  ```

## Try it

Run `desktopctl dark` then `desktopctl light` in another window; open Neovim
instances repaint within a moment, and newly opened ones start in the current
mode. If a scheme needs different names per mode rather than a `background`
toggle, replace the `apply` body with your own
`pcall(vim.cmd.colorscheme, mode == "dark" and "..." or "...")`.
