# Scriggle
Scriggle is a text editor.  I created it to try out an idea I had for reducing mouse usage during text editing.  Scriggle replaces traditional menus, shortcuts, and keybindings with a type of menu inspired by pie menus but adapted to the keyboard.  Hold down one of the Ctrl keys, and a representation of the opposite half of the keyboard shows up, with the keys labeled with commands.  Press one of the keys to execute the command.  It’s like shortcuts, but discoverable.  It’s like menus, but doesn’t take your fingers off the home row.  It’s like Vim’s command mode, but quasi-modal.  Of course, in the future, some of the keys will open up new menus to accommodate more commands.

## Status
It’s still bare-bones, but you can:

 * Open files from the command line
 * Move the cursor using RCtrl+ESDF
 * Open and close multiple windows
 * Save files
 * Cut, copy, and paste; although there’s no good way to select text with the keyboard
 * Use syntax highlighting
 * Set indentation options

## Requirements
Scriggle uses Python 3 and GTK+ 3 (including the Python GObject Introspection bindings).  On Linux, you probably have both of these installed by default.  On Windows, see the [Python Releases for Windows][1] page and the [GTK+ installation instructions for Windows][2] (make sure to install the Python bindings).

[1]: https://www.python.org/downloads/windows/
[2]: https://www.gtk.org/download/windows.php

If you modify the icon, you will need [Inkscape][5] to rebuild the PNG files using `build_icons.py`.

[5]: https://inkscape.org/

## Running from the source directory
You can try Scriggle without installing it by running

    python3 -m scriggle.scriggle

from the source code directory.

## Installation
Once you have installed the requirements and checked out the code, you can install Scriggle using [pip][3] (not from the [PyPI][4], though: you have to check out the git repository).  Use

    pip3 install /path/to/scriggle

On Linux (and probably MacOS), this will install to your home directory, so you don’t need to be superuser.  Afterward, you can run `scriggle` from any directory and (on Linux) it will appear in your applications menu.

[3]: https://pip.pypa.io/en/stable/
[4]: https://pypi.org/
