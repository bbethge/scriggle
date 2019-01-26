from gettext import gettext as _

import gi
from gi.repository import GLib, Gdk, Gtk, GtkSource

from .menu import Menu, Binding, SubmenuBinding, BackBinding


class Left(Menu):
    _side = Menu.Side.LEFT

    _bindings = {
        'z': Binding(_('Undo'), 'on_undo'),
        'x': Binding(_('Cut'), 'on_cut'),
        'c': Binding(_('Copy'), 'on_copy'),
        'v': Binding(_('Paste'), 'on_paste'),
        'e': Binding('↑', 'on_up', _('Move the cursor up')),
        's': Binding('←', 'on_left', _('Move the cursor left')),
        'd': Binding('↓', 'on_down', _('Move the cursor down')),
        'f': Binding('→', 'on_right', _('Move the cursor right')),
        'w': Binding(_('← Word'), 'on_left_word',
                     _('Move the cursor left by a word')),
        'r': Binding(_('→ Word'), 'on_right_word',
                     _('Move the cursor right by a word'))}


class Language(Menu):
    _side = Menu.Side.RIGHT

    _bindings = {'bracketright': BackBinding()}

    def __init__(self, stack, **props):
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        self.__language_list = LanguageList()
        super().__init__(
            stack, override_widgets=[[0, 0, 24, 3, scroller]],
            focus_widget=self.__language_list, **props)
        scroller.add(self.__language_list)
        self.__language_list.connect(
            'selection-changed',
            lambda _view: self.stack.on_language_changed(self.__language_list))
        self.__language_list.connect(
            'item-activated',
            lambda _view, path:
                self.stack.on_language_activated(self.__language_list, path))

    @property
    def language_list(self):
        return self.__language_list


class Style(Menu):
    _side = Menu.Side.RIGHT

    _bindings = {
        'bracketright': BackBinding(),
        'j': SubmenuBinding(
            _('Language…'), Language, 'language_menu',
            _('Set the computer language to highlight syntax for')),
        'k': Binding(
            _('Use Spaces'), 'on_use_spaces',
            _('Whether to indent with spaces instead of tabs'),
            toggle=True),
        'l': Binding(_('Tab Width'), 'on_tab_width')}


class Right(Menu):
    _side = Menu.Side.RIGHT

    _bindings = {
        'y': SubmenuBinding(_('Style…'), Style, 'style_menu',
                            _('Options related to code style')),
        'n': Binding(_('New'), 'on_new', _('Create a new document')),
        'i': Binding(_('Close'), 'on_close', _('Close the current document')),
        'o': Binding(_('Open…'), 'on_open'),
        'j': Binding(_('Find'), 'on_find'),
        'k': Binding(_('Save'), 'on_save')}


class LanguageList(Gtk.IconView):
    COLUMN_ID = 0
    COLUMN_TEXT = 1

    def __init__(self, **props):
        super().__init__(**dict(text_column=self.COLUMN_TEXT, item_padding=0,
                                item_orientation=Gtk.Orientation.HORIZONTAL,
                                row_spacing=0, activate_on_single_click=True,
                                # TODO: Remove hard-coded size?
                                item_width=144, **props))
        model = Gtk.ListStore(str, str)
        model.insert(-1, ['plain', _('Plain')])
        lang_man = GtkSource.LanguageManager.get_default()
        for lang_id in lang_man.props.language_ids:
            lang = lang_man.get_language(lang_id)
            if not lang.props.hidden:
                model.insert(-1, [lang_id, lang.props.name])
        self.props.model = model
        self.__search_string = ''
        self.__previous_selection = None
        self.__search_timeout = 0
        self.__select_item(Gtk.TreePath.new_first())

    def __select_item(self, path):
        self.set_cursor(path, None, False)
        # XXX: set_cursor should select the cursor path, but it doesn’t
        # seem to.  Is it something to do with the CellRenderer?
        self.select_path(path)

    def do_key_press_event(self, event):
        if Gtk.IconView.do_key_press_event(self, event):
            return True
        else:
            codepoint = Gdk.keyval_to_unicode(event.keyval)
            if event.keyval == Gdk.KEY_BackSpace:
                if self.__search_string:
                    self.__search_string = self.__search_string[:-1]
                self.__update_search()
                return True
            elif event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                return False
            elif codepoint:
                if not self.__search_string:
                    iters = self.get_selected_items()
                    if iters:
                        self.__previous_selection = iters[0]
                self.__search_string += chr(codepoint)
                self.__update_search()
                return True
            else:
                return False

    def __update_search(self):
        """
        Update the selection and reset the search timeout.

        Update the selection to the first item that starts (case-
        insensitively) with self.__search_string.  If
        self.__search_string is empty, reset the selection to
        self.__previous_selection instead.  Then reset the search
        timeout."""
        def callback(model, path, iter_):
            name, = model.get(iter_, self.COLUMN_TEXT)
            name = name.casefold().replace(' ', '')
            search_string = self.__search_string.casefold().replace(' ', '')
            if name.startswith(search_string):
                self.__select_item(path)
                return True
            else:
                return False
        if self.__search_string:
            self.props.model.foreach(callback)
        elif self.__previous_selection is not None:
            self.__select_item(self.__previous_selection)
        if self.__search_timeout:
            GLib.source_remove(self.__search_timeout)
        self.__search_timeout = GLib.timeout_add(1000,
                                                 self.__clear_search_string)

    def __clear_search_string(self):
        self.__search_string = ''
        self.__search_timeout = 0