from gettext import gettext as _

import gi
from gi.repository import GLib, Gdk, Gtk, GtkSource

from .menu import Menu, make_menu_class


class Left(Menu):
    def __init__(self, command_manager):
        super().__init__(Menu.Side.LEFT, command_manager)
        undo = self.bind_key_to_action('z', _('Undo'), 'undo')
        @command_manager.undo.enabled_connect
        def on_set_can_undo(can_undo):
            undo.props.sensitive = can_undo
        self.bind_key_to_action('x', _('Cut'), 'cut')
        self.bind_key_to_action('c', _('Copy'), 'copy')
        self.bind_key_to_action('v', _('Paste'), 'paste')
        self.bind_key_to_action(
            'e', '↑', 'up', _('Move the cursor up'), repeat=True
        )
        self.bind_key_to_action(
            's', '←', 'left', _('Move the cursor left'), repeat=True
        )
        self.bind_key_to_action(
            'd', '↓', 'down', _('Move the cursor down'), repeat=True
        )
        self.bind_key_to_action(
            'f', '→', 'right', _('Move the cursor right'), repeat=True
        )
        self.bind_key_to_action(
            'w', _('← Word'), 'left_word',
            _('Move the cursor left by a word'), repeat=True
        )
        self.bind_key_to_action(
            'r', _('→ Word'), 'right_word',
            _('Move the cursor right by a word'), repeat=True
        )
        self.add_unused_keys()


class Right(Menu):
    def __init__(self, command_manager):
        super().__init__(Menu.Side.RIGHT, command_manager)
        self.bind_key_to_submenu(
            'y', _('Style…'), Style(command_manager),
            _('Options related to code style')
        )
        self.bind_key_to_action(
            'n', _('New'), 'new', _('Create a new document')
        )
        self.bind_key_to_action(
            'i', _('Close'), 'close', _('Close the current document')
        )
        self.bind_key_to_action('o', _('Open…'), 'open')
        self.bind_key_to_submenu(
            'j', _('Find…'), Find(command_manager), _("Find and replace")
        )
        self.bind_key_to_action('k', _('Save'), 'save')
        self.add_unused_keys()


class Style(Menu):
    def __init__(self, command_manager):
        super().__init__(Menu.Side.RIGHT, command_manager)
        self.bind_key_to_back_button('bracketright')
        self.bind_key_to_submenu(
            'j', _('Language…'), Language(command_manager),
            _('Set the computer language to highlight syntax for')
        )
        self.bind_key_to_toggle(
            'k', _('Use Spaces'), 'set_use_spaces',
            _('Whether to indent with spaces instead of tabs')
        )
        tab_width_selector = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(8, 2, 8, 1, 2, 0)
        )
        tab_width_selector.connect(
            'value-changed',
            lambda selector:
                command_manager.set_tab_width(selector.props.value)
        )
        # XXX: The menu was pinned by the MenuStack when it showed the
        # style menu and found it had a focus widget.  This seems too
        # complicated.
        tab_width_selector.connect(
            'activate', lambda selector: self.stack.unpin_menu()
        )
        self.add_extra_widget(tab_width_selector, 8, 0, 4, 1)
        self.bind_key_to_widget('u', _('Tab Width:'), tab_width_selector)
        self.add_unused_keys()


class Language(Menu):
    def __init__(self, command_manager):
        super().__init__(Menu.Side.RIGHT, command_manager)
        self.__command_manager = command_manager
        self.bind_key_to_back_button('bracketright')
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        self.__language_list = LanguageList()
        scroller.add(self.__language_list)
        self.add_extra_widget(scroller, 0, 0, 24, 3)
        self.focus_widget = self.__language_list
        self.__language_list.connect(
            'selection-changed', self.__on_language_changed
        )
        self.__language_list.connect(
            'item-activated',
            # TODO
            lambda _view, path:
                self.stack.on_language_activated(self.__language_list, path)
        )
        self.add_unused_keys()

    @property
    def language_list(self):
        return self.__language_list

    def __on_language_changed(self, language_list):
        iters = language_list.get_selected_items()
        if iters:
            iter_ = language_list.props.model.get_iter(iters[0])
            (id_,) = language_list.props.model.get(
                iter_, language_list.COLUMN_ID
            )
            self.__command_manager.set_language(id_)


class LanguageList(Gtk.IconView):
    COLUMN_ID = 0
    COLUMN_TEXT = 1

    def __init__(self, **props):
        super().__init__(
            text_column=self.COLUMN_TEXT, item_padding=0,
            item_orientation=Gtk.Orientation.HORIZONTAL, row_spacing=0, 
            activate_on_single_click=True,
            # TODO: Remove hard-coded size?
            item_width=144, **props
        )
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
        self.__search_timeout = GLib.timeout_add(
            1000, self.__clear_search_string
        )

    def __clear_search_string(self):
        self.__search_string = ''
        self.__search_timeout = 0


class Find(make_menu_class(Gtk.Grid)):
    __ROW_ENTRIES = 0
    __ROW_KEYBOARD = 1
    # TODO: Switch columns for right-to-left languages.
    __COLUMN_FIND = 0
    __COLUMN_REPLACE = 1
    __N_COLUMNS = 2

    def __init__(self, command_manager, **props):
        super().__init__(Menu.Side.RIGHT, command_manager, **props)
        self.__find_entry = Gtk.Entry()
        self.__find_entry.props.placeholder_text = _('Text to find')
        self.focus_widget = self.__find_entry
        self.attach(
            self.__find_entry, self.__COLUMN_FIND, self.__ROW_ENTRIES, 1, 1
        )
        self.__replace_entry = Gtk.Entry()
        self.__replace_entry.props.placeholder_text = _('Replacement text')
        self.attach(
            self.__replace_entry, self.__COLUMN_REPLACE, self.__ROW_ENTRIES,
            1, 1
        )
        self.__key_grid = Gtk.Grid()
        self._set_grid(self.__key_grid)
        self.attach(
            self.__key_grid, 0, self.__ROW_KEYBOARD, self.__N_COLUMNS, 1
        )
        self.bind_key_to_widget('u', _('Text to find'), self.__find_entry)
        self.bind_key_to_widget(
            'o', _('Replacement text'), self.__replace_entry
        )
        self.bind_key_to_back_button('bracketright')
        search = self.bind_key_to_callback(
            'j', _('Find next'),
            lambda: command_manager.find_next(self.__find_entry.props.text)
        )
        @command_manager.find_next.enabled_connect
        def on_search_enabled_disabled(state):
            search.props.sensitive = state
        replace = self.bind_key_to_callback(
            'k', _('Replace'),
            lambda: command_manager.replace(self.__replace_entry.props.text)
        )
        @command_manager.replace.enabled_connect
        def on_replace_enabled_disabled(state):
            replace.props.sensitive = state
        self.bind_key_to_toggle('l', _('Match case'), 'find_match_case')
        self.bind_key_to_toggle(
            'semicolon', _('Regular expression'), 'find_regex'
        )
        replace_all = self.bind_key_to_callback(
            'comma', _('Replace all'),
            lambda:
                command_manager.replace_all(
                    self.__find_entry.props.text,
                    self.__replace_entry.props.text
                )
        )
        @command_manager.replace_all.enabled_connect
        def on_replace_all_enabled_disabled(state):
            replace_all.props.sensitive = state
        self.add_unused_keys()
