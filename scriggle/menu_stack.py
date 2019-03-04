from gettext import gettext as _
import weakref

import gi
from gi.repository import GLib, GObject, Gdk, Gtk, GtkSource

from .menu import Menu
from . import menus


class MenuArea(Gtk.Overlay):
    def __init__(self, command_manager, **props):
        """
        Create a new MenuArea.

        This widget contains the cursor position indicator along with
        the menu stack.
        """
        super().__init__()
        self.__command_manager = command_manager

        self.__stack = MenuStack(command_manager)
        self.add(self.__stack)

        # TODO: Switch ‘halign’ based on the text direction.
        self.__position_label = CursorPositionLabel(
            halign=Gtk.Align.END, valign=Gtk.Align.START
        )
        self.__position_label.props.no_show_all = True
        self.add_overlay(self.__position_label)

    @property
    def left_menu(self):
        return self.__stack.left_menu

    @property
    def right_menu(self):
        return self.__stack.right_menu

    @property
    def cursor_position(self):
        return self.__position_label.position

    @cursor_position.setter
    def cursor_position(self, position):
        self.__position_label.position = position

    def show_menu_immediately(self, menu):
        if menu.side == Menu.Side.LEFT:
            self.__position_label.show()
        else:
            self.__position_label.hide()
        self.__stack.show_menu_immediately(menu)

    def key_event(self, event):
        return self.__stack.key_event(event)


class CursorPositionLabel(Gtk.Label):
    def __init__(self, **props):
        super().__init__(**props)
        self.position = 0, 0

    @property
    def position(self):
        """A pair containing the zero-based line and column number."""
        return self.__line, self.__column

    @position.setter
    def position(self, position):
        self.__line, self.__column = position
        self.props.label = _('Line {0}, Column {1}').format(
            self.__line + 1, self.__column + 1
        )


class MenuStack(Gtk.Stack):
    def __init__(self, command_manager, **props):
        super().__init__(
            transition_type=Gtk.StackTransitionType.OVER_UP_DOWN, **props
        )
        self.__command_manager = command_manager
        self.__history = []
        self.__previous_focus = None

        self.__right_menu = menus.Right(command_manager)
        self.__right_menu.show_all()
        self.add(self.__right_menu)

        self.__left_menu = menus.Left(command_manager)
        self.__left_menu.show_all()
        self.add(self.__left_menu)

    @property
    def menu_revealer(self):
        return self.props.parent.props.parent

    def on_go_back(self):
        # XXX: This makes the assumption that pinned menus have no
        # submenus.
        self.unpin_menu()
        self.props.visible_child = self.__history.pop()

    def pin_menu(self, focus_widget):
        self.__previous_focus = self.get_toplevel().get_focus()
        self.menu_revealer.menu_pinned = True
        focus_widget.grab_focus()

    def unpin_menu(self):
        if self.__previous_focus is not None:
            self.__previous_focus.grab_focus()
            self.__previous_focus = None
        self.menu_revealer.menu_pinned = False

    def on_add_submenu(self, submenu):
        self.add(submenu)

    def on_show_submenu(self, submenu):
        if submenu.focus_widget is not None:
            self.pin_menu(submenu.focus_widget)
        self.__history.append(self.props.visible_child)
        self.props.visible_child = submenu

    def show_menu_immediately(self, menu):
        transition_type = self.props.transition_type
        self.props.transition_type = Gtk.StackTransitionType.NONE
        self.props.visible_child = menu
        self.props.transition_type = transition_type

    def on_language_activated(self, language_list, path):
        self.unpin_menu()

    @property
    def right_menu(self):
        return self.__right_menu

    @property
    def left_menu(self):
        return self.__left_menu

    def key_event(self, event):
        """Handle a key event from the window."""
        return self.props.visible_child.key_event(event)
