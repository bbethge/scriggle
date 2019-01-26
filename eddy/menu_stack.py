from gettext import gettext as _
import weakref

import gi
from gi.repository import GLib, GObject, Gdk, Gtk, GtkSource

from .menu import Menu
from . import menus


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


class MenuStack(Gtk.Overlay):
    def __init__(self, window, **props):
        """
        Create a new MenuStack

        Create a new MenuStack, with a status area and all menus.
        """
        super().__init__(**props)
        self.__window = window
        self.__history = []
        self.__menu_pinned = False

        self.__stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.OVER_UP_DOWN)
        self.add(self.__stack)

        self.__status_area = StatusArea()
        self.__status_area.show_all()
        self.__stack.add(self.__status_area)

        self.__position_label = None

        self.__right_menu = menus.Right(self)
        self.__right_menu.show_all()
        self.__stack.add(self.__right_menu)

        self.__left_menu = menus.Left(self)
        self.__left_menu.show_all()
        self.__stack.add(self.__left_menu)

    def go_back(self):
        self.__unpin_menu(self)
        self.__stack.props.visible_child = self.__history.pop()

    def __unpin_menu(self):
        if hasattr(self, '_MenuStack__previous_focus'):
            self.__previous_focus.grab_focus()
            del self.__previous_focus
        self.__menu_pinned = False

    def add_submenu(self, submenu):
        self.__stack.add(submenu)

    def show_submenu(self, submenu):
        if submenu.focus_widget is not None:
            self.__previous_focus = self.get_toplevel().get_focus()
        self.__history.append(self.__stack.props.visible_child)
        self.__stack.props.visible_child = submenu
        if submenu.focus_widget is not None:
            self.__menu_pinned = True
            submenu.focus_widget.grab_focus()

    def on_language_changed(self, language_list):
        iters = language_list.get_selected_items()
        if iters:
            iter_ = language_list.props.model.get_iter(iters[0])
            id_, = language_list.props.model.get(iter_,
                                                 language_list.COLUMN_ID)
            self.emit('language-changed', id_)

    def on_language_activated(self, language_list, path):
        # TODO: Provide an unpin_menu method and have the menu invoke it?
        self.show_status_area()

    @GObject.Signal(arg_types=(str,))
    def language_changed(self, language_id):
        pass

    @property
    def window(self):
        return self.__window

    @property
    def status_area(self):
        return self.__status_area

    @property
    def right_menu(self):
        return self.__right_menu

    @property
    def left_menu(self):
        return self.__left_menu

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
        self.__unpin_menu()
        self.__stack.props.visible_child = self.__status_area
