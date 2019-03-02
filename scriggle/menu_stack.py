from gettext import gettext as _
import weakref

import gi
from gi.repository import GLib, GObject, Gdk, Gtk, GtkSource

from .menu import Menu
from . import menus


class StatusArea(Gtk.Grid):
    # FIXME: Add this to the left menu
    def __init__(self, **props):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **props)
        self.__save_status = Gtk.Grid(
            orientation=Gtk.Orientation.HORIZONTAL, no_show_all=True
        )
        self.add(self.__save_status)

        save_label = Gtk.Label(_('Saving…'))
        save_label.show()
        self.__save_status.add(save_label)

        save_cancel_button = Gtk.Button.new_with_label(_('Cancel'))
        save_cancel_button.connect(
            'clicked', lambda b: self.emit('save-cancel-clicked')
        )
        save_cancel_button.show()
        self.__save_status.add(save_cancel_button)

        self.__cursor_position_label = Gtk.Label(
            hexpand=True, halign=Gtk.Align.END
        )
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
            .format(line=line+1, column=column+1)
        )

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


class MenuStack(Gtk.Stack):
    def __init__(self, editor, **props):
        """
        Create a new MenuStack

        Create a new MenuStack with all menus.
        ‘editor’ is the Editor that contains this widget.
        """
        super().__init__(
            transition_type=Gtk.StackTransitionType.OVER_UP_DOWN, **props
        )
        self.__editor = editor
        self.__history = []
        self.__menu_pinned = False
        self.__previous_focus = None

        self.__right_menu = menus.Right(self)
        self.__right_menu.show_all()
        self.add(self.__right_menu)

        self.__left_menu = menus.Left(self)
        self.__left_menu.show_all()
        self.add(self.__left_menu)

    def go_back(self):
        # XXX: This makes the assumption that pinned menus have no
        # submenus.
        self.unpin_menu()
        self.props.visible_child = self.__history.pop()

    def pin_menu(self, focus_widget):
        self.__previous_focus = self.get_toplevel().get_focus()
        self.__editor.menu_revealer.menu_pinned = True
        focus_widget.grab_focus()

    def unpin_menu(self):
        if self.__previous_focus is not None:
            self.__previous_focus.grab_focus()
            self.__previous_focus = None
        self.__editor.menu_revealer.menu_pinned = False

    def add_submenu(self, submenu):
        self.add(submenu)

    def show_submenu(self, submenu):
        if submenu.focus_widget is not None:
            self.pin_menu(submenu.focus_widget)
        self.__history.append(self.props.visible_child)
        self.props.visible_child = submenu

    def show_menu_instantly(self, menu):
        transition_type = self.props.transition_type
        self.props.transition_type = Gtk.StackTransitionType.NONE
        self.props.visible_child = menu
        self.props.transition_type = transition_type

    def on_language_activated(self, language_list, path):
        self.unpin_menu()

    @property
    def editor(self):
        return self.__editor

    @property
    def right_menu(self):
        return self.__right_menu

    @property
    def left_menu(self):
        return self.__left_menu

    def key_event(self, event):
        """Handle a key event from the window."""
        return self.props.visible_child.key_event(event)

    def __show_menu(self, menu):
        self.props.visible_child = menu
