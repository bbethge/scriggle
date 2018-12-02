#! /usr/bin/env python3
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
import os
import weakref

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Gtk', '3.0')
gi.require_version('GtkSource', '3.0')
gtk_minor_version = 14
from gi.repository import GLib, GObject, Gio, Gdk, Pango, PangoCairo, Gtk
from gi.repository import GtkSource


class AutoSizeLabel(Gtk.Widget):
    """
    A label that chooses an appropriate font size.

    Instead of requesting enough space to show its whole text, this
    label tries to reduce its font size to be able to show its whole
    text in the allocation it receives.
    """
    def __init__(self, markup='', **props):
        super().__init__(**props)
        # XXX: This should be done in the instance init function, but
        # PyGObject doesn’t want anyone to override the instance init
        # function except for Gtk.Template.
        self.set_has_window(False)
        self.markup = markup

    @property
    def markup(self):
        return self.__markup
    @markup.setter
    def markup(self, markup):
        self.__markup = markup
        if markup:
            layout = self.create_pango_layout(self.__markup)
            _ink_rect, log_rect = layout.get_pixel_extents()
            self.__preferred_width = log_rect.width
        else:
            self.__preferred_width = 0

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_width(self):
        return min(self.__preferred_width, 40), self.__preferred_width

    def do_get_preferred_height_and_baseline_for_width(self, width):
        layout = self.create_pango_layout(self.__markup)
        _ink_rect, log_rect = layout.get_pixel_extents()
        if layout.get_line_count() > 1:
            baseline = log_rect.height * 2 // 3
        else:
            baseline = layout.get_baseline() // Pango.SCALE
        return log_rect.height, log_rect.height, baseline, baseline

    def do_draw(self, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        baseline = self.get_allocated_baseline()
        layout = self.create_pango_layout('')
        layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        layout.set_width(width * Pango.SCALE)
        layout.set_height(height * Pango.SCALE)
        for size in ('medium', 'small', 'x-small', 'xx-small'):
            layout.set_markup(f'<span size="{size}">{self.__markup}</span>')
            if not layout.is_ellipsized():
                break
        _ink_rect, rect = layout.get_pixel_extents()
        layout_baseline = layout.get_baseline() // Pango.SCALE
        if baseline == -1:
            baseline = layout_baseline
        cr.translate(rect.x, rect.y + baseline - layout_baseline)
        PangoCairo.show_layout(cr, layout)
        return True


class MenuItemMixin:
    """
    Modify a Gtk.Button class to work with our menus.

    Inheriting from this class and a Gtk.Button (sub)class makes a
    button that has a key associated with it and is activated by that
    key.  It goes inside a Menu.
    """
    def __init__(self, **props):
        super().__init__(**dict(focus_on_click=False, **props))

        self.__grid = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.__grid)

        self.__label = AutoSizeLabel(hexpand=True, halign=Gtk.Align.START,
                                     valign=Gtk.Align.BASELINE)
        self.__grid.add(self.__label)

        self.__keyval_label = Gtk.Label(valign=Gtk.Align.BASELINE)
        self.__grid.add(self.__keyval_label)

        self.__grid.show_all()

        self.keyval = None

    @property
    def keyval(self):
        return self.__keyval
    @keyval.setter
    def keyval(self, keyval):
        if keyval is not None:
            kvs = chr(Gdk.keyval_to_unicode(keyval))
            self.__keyval_label.set_markup(
                f'<b> {GLib.markup_escape_text(kvs)}</b>')
        else:
            self.__keyval_label.set_markup('')
        self.__keyval = keyval

    @property
    def label(self):
        return self.__label.markup
    @label.setter
    def label(self, markup):
        self.__label.markup = markup


class MenuItem(MenuItemMixin, Gtk.Button):
    def __init__(self, **props):
        super().__init__(**props)

    def key_event(self, event):
        if event.type == Gdk.EventType.KEY_PRESS:
            self.set_state_flags(Gtk.StateFlags.ACTIVE, False)
        else:
            self.unset_state_flags(Gtk.StateFlags.ACTIVE)
            self.clicked()
        return True


class ToggleMenuItem(MenuItemMixin, Gtk.ToggleButton):
    def __init__(self, **props):
        super().__init__(**props)

    def key_event(self, event):
        if event.type == Gdk.EventType.KEY_PRESS:
            self.props.active = not self.props.active


class Menu(Gtk.Grid):
    """
    A menu using a keyboard-like layout.

    A panel with several MenuItems arranged in a grid that mimics one
    half of the keyboard.  This will be shown by holding down the Ctrl
    key on the opposite side, and MenuItems can be activated by
    pressing the corresponding key.
    """
    class Side:
        LEFT = 0
        RIGHT = 1

    __keyvals = [
        # Side.LEFT
        list(map(lambda kns: list(map(Gdk.keyval_from_name, kns)),
                 [['q', 'w', 'e', 'r', 't'],
                  ['a', 's', 'd', 'f', 'g'],
                  ['z', 'x', 'c', 'v', 'b']])),
        # Side.RIGHT
        list(map(lambda kns: list(map(Gdk.keyval_from_name, kns)),
                 [['y', 'u', 'i', 'o', 'p', 'bracketleft', 'bracketright'],
                  ['h', 'j', 'k', 'l', 'semicolon', 'apostrophe'],
                  ['n', 'm', 'comma', 'period', 'slash']]))]

    def __init__(self, side, override_widgets=(), **props):
        """
        Create a new menu.

        ‘side’ tells which side of the keyboard to use (Side.LEFT
        or Side.RIGHT).

        override_widgets is a sequence of specifications for widgets
        that will replace some of the buttons.  Each specification is a
        sequence of five things: x, y, width, and height of the region
        to be used, and the widget itself.  The region is given in grid
        coördinates: each key has a width of four and the horizontal
        offset between the first and second rows is one.

        ‘props’ contains GObject properties to be set.
        """
        super().__init__(**dict(row_homogeneous=True, column_homogeneous=True,
                                hexpand=True, **props))
        self.__side = side
        self.__items = {}
        for row, row_contents in enumerate(self.__keyvals[side]):
            for column, keyval in enumerate(row_contents):
                grid_col = self.__key_coörds_to_grid_col(row, column)
                for x, y, width, height, _widget in override_widgets:
                    if x - 3 <= grid_col < x + width and y <= row < y + height:
                        break
                else:
                    item = MenuItem(sensitive=False)
                    item.keyval = keyval
                    item.show()
                    self.attach(item, grid_col, row, 4, 1)
                    self.__items[keyval] = item
        for x, y, width, height, widget in override_widgets:
            self.attach(widget, x, y, width, height)
        spacer = Gtk.Label()
        spacer.show()
        if side == self.Side.LEFT:
            self.attach(spacer, 23, 2, 9, 1)
        else:
            self.attach(spacer, -4, 0, 4, 1)

    def __get_item(self, row, column):
        return self.get_child_at(self.__key_coörds_to_grid_col(row, column),
                                 row)

    def __get_item_coördinates(self, item):
        return self.child_get(item, 'top-attach', 'left-attach')

    @property
    def side(self):
        return self.__side

    def bind_key(self, name, label, callback, tooltip=None):
        """
        Bind a key (MenuItem) to a callback.

        Make the MenuItem with keyval name ‘name’ call ‘callback’ when
        it is activated, and label it with ‘label’.  ‘tooltip’ is Pango
        markup to show as a tooltip.
        """ 
        item = self.__items[Gdk.keyval_from_name(name)]
        if isinstance(item, ToggleMenuItem):
            item = self.__reinstall_item(item, MenuItem)
        item.label = label
        if tooltip is not None:
            item.props.tooltip_markup = tooltip
        item.props.sensitive = True
        item.__handler_id = item.connect('clicked', callback)

    def __reinstall_item(self, item, class_):
        """
        Replace the menu item with a ‘class_’ object.

        Remove ‘item’ from ‘self’ and replace it with a new item of
        class ‘class_’ having the same keyval.  Return the new item.
        """
        keyval = item.keyval
        row, col = self.__get_item_coördinates(item)
        self.remove(item)
        if hasattr(item, '_Menu__handler_id'):
            item.disconnect(item.__handler_id)
            del item.__handler_id
        new_item = class_(sensitive=False)
        new_item.keyval = keyval
        new_item.show()
        self.attach(new_item, col, row, 4, 1)
        self.__items[keyval] = new_item
        return new_item

    def bind_toggle_key(self, name, label, callback, tooltip=None):
        """
        Make the key a ToggleMenuItem.

        Turn the MenuItem with keyval name ‘name’ into a ToggleMenuItem
        that calls ‘callback’ with the new button state when it is
        toggled, and label it with ‘label’.  ‘tooltip’ is Pango markup
        to show as a tooltip.
        """
        item = self.__items[Gdk.keyval_from_name(name)]
        if isinstance(item, MenuItem):
            item = self.__reinstall_item(item, ToggleMenuItem)
        item.label = label
        if tooltip is not None:
            item.props.tooltip_markup = tooltip
        item.props.sensitive = True
        item.__handler_id = item.connect(
            'toggled', lambda button: callback(button.props.active))
        
    def unbind_key(self, name):
        """Unbind the MenuItem with the given keyval name"""
        item = self.__items[Gdk.keyval_from_name(name)]
        item.disconnect(item.__handler_id)
        item.props.sensitive = False
        item.label = None
        del item.__handler_id

    @staticmethod
    def __key_coörds_to_grid_col(row, column):
        """
        Return the grid column number of a key.

        Given the coördinates of a key, return the leftmost column
        its button occupies in the grid.
        """
        return 4*column + row**2 - row//2

    def key_event(self, event):
        """
        Process a key event.

        Process a key event from another widget that should
        activate one of our buttons.
        """
        try:
            item = self.__items[event.keyval]
        except KeyError:
            return False
        return item.key_event(event)


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


class Editor(Gtk.ApplicationWindow):
    __ROW_TEXT_VIEW = 0
    __ROW_MENU = 1

    def __init__(self, file=None, **props):
        super().__init__(**dict(default_width=640, default_height=480,
                                icon_name='eddy', **props))
        self.__file = file
        self.__saved = True
        self.__close_after_save = False

        grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.add(grid)
        
        self.__menu_stack = MenuStack(self)
        grid.attach(self.__menu_stack, 0, self.__ROW_MENU, 1, 1)
        self.__menu_stack.connect('language-changed',
                                  self.__on_language_changed)

        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN,
                                      expand=True)

        self.__source_view = GtkSource.View(expand=True, monospace=True)
        scroller.add(self.__source_view)
        scroller.show_all()
        self.buffer.connect('mark-set', self.__on_mark_set)
        self.__on_cursor_position_changed(self.buffer.get_start_iter())

        if file is None:
            grid.attach(scroller, 0, self.__ROW_TEXT_VIEW, 1, 1)
            self.buffer.connect('changed', self.__on_buffer_changed)
        else:
            hgrid = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL)
            label = Gtk.Label(_('Loading…'))
            hgrid.add(label)
            cancel_button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
            hgrid.add(cancel_button)
            grid.attach(hgrid, 0, self.__ROW_TEXT_VIEW, 1, 1)
            hgrid.show_all()

            cancellable = Gio.Cancellable()
            source_file = GtkSource.File(location=file)
            loader = GtkSource.FileLoader(buffer=self.buffer, file=source_file)
            # TODO: Show progress
            loader.load_async(GLib.PRIORITY_DEFAULT, cancellable, None, None,
                              lambda loader, result:
                                  self.__finish_loading(loader, result,
                                                        grid, hgrid, scroller))
            cancel_button.connect('clicked', lambda b: cancellable.cancel())

        grid.show_all()

    def __finish_loading(self, loader, result, main_grid, progress_grid,
                         scroller):
        try:
            loader.load_finish(result)
        except GLib.Error as error:
            message = (_('Unable to load “{filename}”: {message}')
                       .format(filename=loader.props.location.get_path(),
                               message=error.message))
            dialog = Gtk.MessageDialog(self,
                                       Gtk.DialogFlags.MODAL
                                       | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                       Gtk.MessageType.ERROR,
                                       Gtk.ButtonsType.CLOSE, message)
            dialog.run()
            dialog.destroy()
        main_grid.remove(progress_grid)
        main_grid.attach(scroller, 0, self.__ROW_TEXT_VIEW, 1, 1)
        self.__source_view.grab_focus()
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.connect('changed', self.__on_buffer_changed)

    @property
    def buffer(self):
        return self.__source_view.props.buffer

    @property
    def filename(self):
        if self.__file is None:
            return None
        else:
            return self.__file.get_path()

    def do_window_state_event(self, event):
        if event.changed_mask & Gdk.WindowState.FOCUSED:
            self.__menu_stack.window_focus_changed(
                bool(event.new_window_state & Gdk.WindowState.FOCUSED))
        return Gtk.ApplicationWindow.do_window_state_event(self, event)

    def do_key_press_event(self, event):
        if (event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]
                or event.state & Gdk.ModifierType.CONTROL_MASK):
            return self.__menu_stack.key_event(event)
        else:
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

    def do_key_release_event(self, event):
        if (event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]
                or event.state & Gdk.ModifierType.CONTROL_MASK):
            return self.__menu_stack.key_event(event)
        return Gtk.ApplicationWindow.do_key_release_event(self, event)

    def __on_mark_set(self, _buffer, location, mark):
        if mark.props.name == 'insert':
            self.__on_cursor_position_changed(location)

    def __on_buffer_changed(self, buffer):
        location = buffer.get_iter_at_mark(buffer.get_insert())
        self.__on_cursor_position_changed(location)
        self.__saved = False

    def __on_cursor_position_changed(self, location):
        self.__menu_stack.status_area.set_cursor_position(
            location.get_line(), location.get_line_offset())

    def __on_language_changed(self, _stack, language_id):
        lang_man = GtkSource.LanguageManager.get_default()
        if language_id == 'plain':
            self.buffer.set_language(None)
        else:
            self.buffer.set_language(lang_man.get_language(language_id))

    def on_use_spaces(self, use_spaces):
        self.__source_view.props.insert_spaces_instead_of_tabs = use_spaces

    def on_new(self, _widget):
        if self.props.application is not None:
            self.props.application.activate()

    def do_delete_event(self, _event):
        self.on_close()
        return True

    def on_close(self, _widget=None):
        if not self.__saved:
            DISCARD = 0
            SAVE = 1
            dialog = Gtk.MessageDialog(self,
                                       Gtk.DialogFlags.MODAL,
                                       Gtk.MessageType.QUESTION,
                                       Gtk.ButtonsType.NONE,
                                       _('Save changes to {} before closing?')
                                           .format(self.props.title))
            dialog.add_buttons(_('Close without Saving'), DISCARD,
                               _('Cancel'), Gtk.ResponseType.CANCEL,
                               _('Save'), SAVE)
            dialog.set_default_response(SAVE)
            response = dialog.run()
            dialog.destroy()
            if response in [Gtk.ResponseType.CANCEL,
                            Gtk.ResponseType.DELETE_EVENT]:
                return
            elif response == SAVE:
                self.__close_after_save = True
                self.on_save()
                return
        self.__finish_close()

    def __finish_close(self):
        """
        Finish closing the window.

        Remove ‘self’ from its application and destroy it.
        """
        if self.props.application is not None:
            self.props.application.remove_window(self)
        self.destroy()

    def on_open(self, _widget):
        self.props.application.show_open_dialog(self)

    def on_save(self, _widget=None):
        if self.__file is None:
            chooser = Gtk.FileChooserNative.new(
                _('Save As…'), self, Gtk.FileChooserAction.SAVE, None, None)
            response = chooser.run()
            if response != Gtk.ResponseType.ACCEPT:
                return
            filename = chooser.get_filename()
            self.__file = Gio.File.new_for_path(filename)
        assert self.__file is not None
        assert self.__file.get_path() is not None
        source_file = GtkSource.File(location=self.__file)
        cancellable = Gio.Cancellable()
        cancel_handler = self.__menu_stack.status_area.connect(
            'save-cancel-clicked', lambda b: cancellable.cancel())
        self.__menu_stack.status_area.show_save_status()
        saver = GtkSource.FileSaver(buffer=self.buffer, file=source_file)
        # TODO: Show progress
        saver.save_async(GLib.PRIORITY_DEFAULT, cancellable, None, None,
                         self.__finish_saving, cancel_handler)

    def __finish_saving(self, saver, result, cancel_handler):
        try:
            saver.save_finish(result)
        except GLib.Error as error:
            message = (_('Unable to save file “{filename}”: {message}')
                       .format(filename=saver.props.location.get_path(),
                               message=error.message))
            dialog = Gtk.MessageDialog(self,
                                       Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                       Gtk.MessageType.ERROR,
                                       # XXX: Is ‘Close’ confusing (it
                                       # will not close the file)?
                                       Gtk.ButtonsType.CLOSE, message)
            dialog.run()
            dialog.destroy()
            self.__save_terminated(cancel_handler)
            return
        self.__save_terminated(cancel_handler)
        self.__saved = True
        if self.__close_after_save:
            self.__finish_close()
            self.__close_after_save = False

    def __save_terminated(self, cancel_handler):
        """Called when a save is finished or aborted due to error."""
        self.__menu_stack.status_area.disconnect(cancel_handler)
        self.__menu_stack.status_area.hide_save_status()

    def on_undo(self, _widget):
        # TODO: Set sensitivity of the button depending on
        # self.buffer.can_undo.
        self.buffer.undo()

    def on_cut(self, _widget):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.cut_clipboard(clip, True)

    def on_copy(self, _widget):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.copy_clipboard(clip)

    def on_paste(self, _widget):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.paste_clipboard(clip, None, True)

    def on_up(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.DISPLAY_LINES, -1, False)

    def on_down(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.DISPLAY_LINES, 1, False)

    def on_left(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.VISUAL_POSITIONS, -1, False)

    def on_right(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.VISUAL_POSITIONS, 1, False)

    def on_left_word(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.WORDS, -1, False)

    def on_right_word(self, _widget):
        self.__source_view.emit('move-cursor',
                                Gtk.MovementStep.WORDS, 1, False)


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
