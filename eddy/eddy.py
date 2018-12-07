"""
Usage:
$ eddy [-h|--help] [file...]

--help  Show this help

Eddy is a graphical text editor based on the idea of keyboard menus:
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
        super().__init__(application_id='com.example.Eddy',
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.__unnamed_window_number = 1

    def do_open(self, files, _n_files, _hint):
        for file in files:
            editor = Editor(file)
            self.add_window(editor)
            editor.show()

    def do_activate(self):
        editor = Editor()
        self.add_window(editor)
        editor.show()

    def do_window_added(self, window):
        Gtk.Application.do_window_added(self, window)
        windows = self.get_windows()
        if window.filename is None:
            window.props.title = _('New File {:d}').format(
                self.__unnamed_window_number)
            self.__unnamed_window_number += 1
        else:
            basenames = self.__get_basenames(window)
            basename = GLib.path_get_basename(window.filename)
            if basename in basenames:
                for w in windows:
                    self.__maybe_set_window_title(w, basename)
            else:
                window.props.title = basename

    @staticmethod
    def __maybe_set_window_title(window, basename):
        if (GLib.path_get_basename(window.filename) == basename):
            window.props.title = home_substitute(window.filename)

    def __get_basenames(self, window):
        """
        Return the basenames of the filenames of all windows that have
        filenames, except ‘window’.
        """
        return {GLib.path_get_basename(w.filename) for w in self.get_windows()
                if w is not window and w.filename is not None}

    def do_window_removed(self, window):
        Gtk.Application.do_window_removed(self, window)
        if window.filename is None:
            return
        basename = GLib.path_get_basename(window.filename)
        other_windows = [
            w for w in self.get_windows()
            if w.filename is not None and w is not window
                and GLib.path_get_basename(w.filename) == basename]
        if len(other_windows) == 1:
            other_windows[0].props.title = basename

    def show_open_dialog(self, window):
        chooser = Gtk.FileChooserNative(title=_('Open File'),
                                        transient_for=window,
                                        action=Gtk.FileChooserAction.OPEN)
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
    gettext.bindtextdomain('eddy', localedir)
    gettext.textdomain('eddy')
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip())
        return 0
    if Gtk.get_minor_version() < gtk_minor_version:
        dialog = Gtk.MessageDialog(
            None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE,
            _('Eddy requires GTK+ version 3.{} or later').format(
                gtk_minor_version))
        dialog.run()
        return 1
    return Application().run(sys.argv)


if __name__ == '__main__':
    import sys
    sys.exit(main())
