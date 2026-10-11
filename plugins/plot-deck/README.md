# plot-deck (spop)

A Claude Code mod that adds a side panel named `spop` with a list of plot images.

- `/spop <folder>` lists every PNG and JPG in the folder. `/spop` alone shows the latest plots in the working directory and its `figures`, `plots`, `output`, `out` and `results` folders.
- Enter on a name copies the image to the Windows clipboard and opens a copy in the default image viewer. The original file is never opened or locked.
- Image paths that Bash or PowerShell calls in the chat mention or print are added to the top of the list.
- `/plots` is an alias for `/spop`.

Windows only (PowerShell, `System.Windows.Forms` clipboard). Install by copying this folder into a Claude Code dev-mods directory and running `/reload-plugins`.
