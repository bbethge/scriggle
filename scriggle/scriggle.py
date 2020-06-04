"""
Usage:
$ scriggle [-h|--help] [file...]

--help  Show this help

Scriggle is a graphical text editor based on the idea of keyboard menus:
every (non-application-wide) menu is an image of half of the keyboard
with actions labeling each key.  A menu is shown by holding down a Ctrl
key, and a menu item is activated by pressing the corresponding key.
This should enable the user to keep their hands on the keyboard and not
spend time reaching for the mouse.
"""

import gettext
from gettext import gettext as _

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '3.0')
gtk_minor_version = 14
from gi.repository import GLib, Gio, Gdk, Gtk

from .editor import Editor


def home_substitute(filename):
    """
    Replace home directory with '~'.

    If ‘filename’ refers to a file in the user’s home directory, return
    ‘filename’ with the home directory path replaced by '~', otherwise
    return ‘filename’ unmodified.  ‘filename’ should be an absolute
    path.
    """
    home = GLib.get_home_dir()
    if not home:
        return filename
    if filename.startswith(home):
        return '~' + filename[len(home):]
    else:
        return filename


class Application(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id='com.example.Scriggle',
            flags=Gio.ApplicationFlags.HANDLES_OPEN
        )
        self.__unnamed_window_number = 1

    def do_open(self, files, _n_files, _hint):
        for file in files:
            editor = Editor(file)
            self.add_window(editor)
            editor.show_all()

    def do_activate(self):
        editor = Editor()
        self.add_window(editor)
        editor.show_all()

    def do_window_added(self, window):
        Gtk.Application.do_window_added(self, window)
        if window.filename is None:
            window.__window_number = self.__unnamed_window_number
            self.__unnamed_window_number += 1
        self.__refresh_window_title(window)
        window.connect(
            'notify::modified', lambda w, p: self.__refresh_window_title(w)
        )

    def __refresh_window_title(self, window):
        title = self.__get_display_filename(window)
        if window.props.modified:
            title = '✍ ' + title
        window.props.title = title

    def __get_display_filename(self, window):
        windows = self.get_windows()
        if window.filename is None:
            return _('New File {:d}').format(window.__window_number)
        else:
            basenames = self.__get_basenames(window)
            basename = GLib.path_get_basename(window.filename)
            if basename in basenames:
                return home_substitute(window.filename)
            else:
                return basename

    def __get_basenames(self, window):
        """
        Return the basenames of the filenames of all windows that have
        filenames, except ‘window’.
        """
        return {
            GLib.path_get_basename(w.filename) for w in self.get_windows()
            if w is not window and w.filename is not None
        }

    def do_window_removed(self, window):
        Gtk.Application.do_window_removed(self, window)
        for w in self.get_windows():
            self.__refresh_window_title(w)

    def show_open_dialog(self, window):
        chooser = Gtk.FileChooserNative(
            title=_('Open File'), transient_for=window,
            action=Gtk.FileChooserAction.OPEN
        )
        response = chooser.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = chooser.get_filename()
            file = Gio.File.new_for_path(filename)
            self.open([file], '')


def main():
    from os.path import abspath, dirname, isdir, join
    import sys
    # This is the locale directory if we are not installed.
    localedir = abspath(join(dirname(sys.argv[0]), 'locale'))
    if not isdir(localedir):
        localedir = None
    gettext.bindtextdomain('scriggle', localedir)
    gettext.textdomain('scriggle')
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip())
        return 0
    if Gtk.get_minor_version() < gtk_minor_version:
        dialog = Gtk.MessageDialog(
            None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE,
            _('Scriggle requires GTK+ version 3.{} or later').format(
                gtk_minor_version
            )
        )
        dialog.run()
        return 1
    return Application().run(sys.argv)


if __name__ == '__main__':
    import sys
    sys.exit(main())
