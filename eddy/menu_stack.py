from gettext import gettext as _
import weakref

import gi
from gi.repository import GLib, GObject, Gdk, Gtk, GtkSource

from .menu import Menu


class StatusArea(Gtk.Grid):
    def __init__(self, **props):
        super().__init__(**dict(orientation=Gtk.Orientation.HORIZONTAL,
                                **props))
        self.__save_status = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL,
                                      no_show_all=True)
        self.add(self.__save_status)

        save_label = Gtk.Label(_('Saving…'))
        save_label.show()
        self.__save_status.add(save_label)

        save_cancel_button = Gtk.Button.new_with_label(_('Cancel'))
        save_cancel_button.connect('clicked',
                                   lambda b: self.emit('save-cancel-clicked'))
        save_cancel_button.show()
        self.__save_status.add(save_cancel_button)

        self.__cursor_position_label = Gtk.Label(hexpand=True,
                                                 halign=Gtk.Align.END)
        self.add(self.__cursor_position_label)

    def show_save_status(self):
        self.__save_status.show()

    def hide_save_status(self):
        self.__save_status.hide()

    @GObject.Signal
    def save_cancel_clicked(self):
        pass

    def set_cursor_position(self, line, column):
        """
        Update cursor position display.

        Set the (zero-based) line and column number for cursor position
        display.
        """
        self.__cursor_position_label.set_text(
            _('Line {line}, Column {column}')
            .format(line=line+1, column=column+1))

    def pop_out_cursor_position_label(self):
        """
        Remove and retrieve the cursor position label.

        Remove the cursor position label from ‘self’ and return it
        so it can be added to another widget.  You should still
        call self.set_cursor_position to update the label.
        """
        self.remove(self.__cursor_position_label)
        return self.__cursor_position_label

    def pop_in_cursor_position_label(self):
        """
        Undo pop_out_cursor_position_label.

        Add the cursor position label back to ‘self’.  It should be
        removed from any other container before calling this.
        """
        self.add(self.__cursor_position_label)


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


class MenuStack(Gtk.Overlay):
    def __init__(self, window, **props):
        """
        Create a new MenuStack

        Create a new MenuStack, with a status area and all menus.
        ‘window’ is the widget that contains this stack, and should
        implement handlers (named starting with 'on_') for all actions
        that can be triggered by menu items.  ‘window’ is weakly
        referenced, so it must be around as long as the MenuStack.
        """
        super().__init__(**props)
        self.__window = weakref.proxy(window)
        self.__history = []
        self.__menu_pinned = False

        self.__stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.OVER_UP_DOWN)
        self.add(self.__stack)

        self.__status_area = StatusArea()
        self.__status_area.show_all()
        self.__stack.add(self.__status_area)

        self.__position_label = None

        self.__right_menu = Menu(Menu.Side.RIGHT)
        self.__right_menu.show_all()
        self.__stack.add(self.__right_menu)
        self.__right_menu.bind_key('y', _('Style…'), self.__on_style,
                                   tooltip=_('Options related to code style'))
        self.__right_menu.bind_key('n', _('New'), self.__window.on_new,
                                   tooltip=_('Create a new document'))
        self.__right_menu.bind_key('i', _('Close'), self.__window.on_close,
                                   tooltip=_('Close the current document'))
        self.__right_menu.bind_key('o', _('Open…'), self.__window.on_open)
        self.__right_menu.bind_key('j', _('Find'),
                                   lambda b: print('“Find” activated'))
        self.__right_menu.bind_key('k', _('Save'), self.__window.on_save)

        self.__left_menu = Menu(Menu.Side.LEFT)
        self.__left_menu.show_all()
        self.__stack.add(self.__left_menu)
        self.__left_menu.bind_key('z', _('Undo'), self.__window.on_undo)
        self.__left_menu.bind_key('x', _('Cut'), self.__window.on_cut)
        self.__left_menu.bind_key('c', _('Copy'), self.__window.on_copy)
        self.__left_menu.bind_key('v', _('Paste'), self.__window.on_paste)
        self.__left_menu.bind_key('e', '↑', self.__window.on_up,
                                  tooltip=_('Move the cursor up'))
        self.__left_menu.bind_key('s', '←', self.__window.on_left,
                                  tooltip=_('Move the cursor left'))
        self.__left_menu.bind_key('d', '↓', self.__window.on_down,
                                  tooltip=_('Move the cursor down'))
        self.__left_menu.bind_key('f', '→', self.__window.on_right,
                                  tooltip=_('Move the cursor right'))
        self.__left_menu.bind_key('w', '← Word', self.__window.on_left_word,
                                  tooltip=_('Move the cursor left by a word'))
        self.__left_menu.bind_key('r', '→ Word', self.__window.on_right_word,
                                  tooltip=_('Move the cursor right by a word'))

        self.__style_menu = Menu(Menu.Side.RIGHT)
        self.__style_menu.show_all()
        self.__stack.add(self.__style_menu)
        self.__style_menu.bind_key('bracketright', _('Back'), self.__on_back,
                                   tooltip=_('Show the previous menu'))
        self.__style_menu.bind_key(
            'j', _('Language…'), self.__on_language,
            tooltip=_('Set the computer language to highlight syntax for'))
        self.__style_menu.bind_toggle_key(
            'k', _('Use Spaces'), self.__window.on_use_spaces,
            tooltip=_('Whether to indent with spaces instead of tabs'))
        self.__style_menu.bind_key('l', _('Tab Width'),
                                   lambda b: print('“Tab Width” activated'))

        lang_scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        self.__language_menu = Menu(Menu.Side.RIGHT,
                                    [[0, 0, 24, 3, lang_scroller]])
        self.__stack.add(self.__language_menu)
        self.__language_menu.bind_key('bracketright', _('Back'),
                                      self.__on_back,
                                      tooltip=_('Show the previous menu'))
        self.__language_list = LanguageList()
        lang_scroller.add(self.__language_list)
        self.__language_list.connect('selection-changed',
                                     self.__on_language_changed)
        self.__language_list.connect('item-activated',
                                     self.__on_language_activated)
        self.__language_menu.show_all()

    def __on_back(self, button):
        if hasattr(self, '_MenuStack__language_list_previous_focus'):
            self.__language_list_previous_focus.grab_focus()
            del self.__language_list_previous_focus
        self.__stack.props.visible_child = self.__history.pop()
        self.__menu_pinned = False

    def __on_style(self, button):
        self.__history.append(self.__stack.props.visible_child)
        self.__stack.props.visible_child = self.__style_menu

    def __on_language(self, button):
        self.__history.append(self.__stack.props.visible_child)
        self.__language_list_previous_focus = self.get_toplevel().get_focus()
        self.__stack.props.visible_child = self.__language_menu
        self.__menu_pinned = True
        self.__language_list.grab_focus()

    def __on_language_changed(self, language_list):
        iters = language_list.get_selected_items()
        if iters:
            iter_ = language_list.props.model.get_iter(iters[0])
            id_, = language_list.props.model.get(iter_,
                                                 language_list.COLUMN_ID)
            self.emit('language-changed', id_)

    def __on_language_activated(self, language_list, path):
        self.show_status_area()
        self.__menu_pinned = False

    @GObject.Signal(arg_types=(str,))
    def language_changed(self, language_id):
        pass

    @property
    def status_area(self):
        return self.__status_area

    def key_event(self, event):
        """Handle a key event from the window."""
        menu = None
        if event.keyval == Gdk.KEY_Control_L:
            menu = self.__right_menu
        elif event.keyval == Gdk.KEY_Control_R:
            menu = self.__left_menu
        if menu is not None:
            if not self.__menu_pinned:
                if event.type == Gdk.EventType.KEY_PRESS:
                    self.__show_menu(menu)
                else:
                    self.show_status_area()
            return True
        elif self.__stack.props.visible_child is not self.__status_area:
            return self.__stack.props.visible_child.key_event(event)
        return False

    def __show_menu(self, menu):
        self.__stack.props.visible_child = menu
        if menu.side == Menu.Side.LEFT:
            self.__position_label = (
                self.__status_area.pop_out_cursor_position_label())
            self.__position_label.props.halign = Gtk.Align.END
            self.__position_label.props.valign = Gtk.Align.START
            self.add_overlay(self.__position_label)

    def window_focus_changed(self, focused):
        """Notify ‘self’ of focus changes in its toplevel window"""
        if not focused and not self.__menu_pinned:
            self.show_status_area()

    def show_status_area(self):
        """Hide any shown menu and show the status area instead."""
        # FIXME: The cursor position label is momentarily covered by
        # the background of the menu as it slides away.
        if self.__position_label is not None:
            self.remove(self.__position_label)
            self.__status_area.pop_in_cursor_position_label()
            self.__position_label = None
        self.__stack.props.visible_child = self.__status_area
