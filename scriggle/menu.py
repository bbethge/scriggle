from gettext import gettext as _

import gi
from gi.repository import GLib, Gdk, Pango, PangoCairo, Gtk


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
        style = self.get_style_context()
        color = style.get_color(style.get_state())
        Gdk.cairo_set_source_rgba(cr, color)
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
        super().__init__(focus_on_click=False, **props)

        self.__grid = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.__grid)

        self.__label = AutoSizeLabel(
            hexpand=True, halign=Gtk.Align.START, valign=Gtk.Align.BASELINE
        )
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
                f'<b> {GLib.markup_escape_text(kvs)}</b>'
            )
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
    def __init__(self, repeat=False, **props):
        """
        Create a menu item.

        If ‘repeat’ is False, the menu item will be activated once per
        key press, when the key is released.  This is similar to the way
        clicking on a button with the mouse works.  If ‘repeat’ is True,
        the menu item will be activated when the key is pressed and
        repeatedly as long as the key is held down.  This is similar to
        how keys normally work when editing text.
        """
        super().__init__(**props)
        self.__repeat = repeat

    def key_event(self, event):
        if self.is_sensitive():
            if event.type == Gdk.EventType.KEY_PRESS:
                self.set_state_flags(Gtk.StateFlags.ACTIVE, False)
                if self.__repeat:
                    self.clicked()
            else:
                self.unset_state_flags(Gtk.StateFlags.ACTIVE)
                if not self.__repeat:
                    self.clicked()
            return True
        else:
            return False


class ToggleMenuItem(MenuItemMixin, Gtk.ToggleButton):
    def __init__(self, **props):
        super().__init__(**props)

    def key_event(self, event):
        if self.is_sensitive():
            if event.type == Gdk.EventType.KEY_PRESS:
                self.props.active = not self.props.active
            return True
        else:
            return False


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
        list(
            map(
                lambda kns: list(map(Gdk.keyval_from_name, kns)),
                [
                    ['q', 'w', 'e', 'r', 't'],
                    ['a', 's', 'd', 'f', 'g'],
                    ['z', 'x', 'c', 'v', 'b'],
                ]
            )
        ),
        # Side.RIGHT
        list(
            map(
                lambda kns: list(map(Gdk.keyval_from_name, kns)),
                [
                    ['y', 'u', 'i', 'o', 'p', 'bracketleft', 'bracketright'],
                    ['h', 'j', 'k', 'l', 'semicolon', 'apostrophe'],
                    ['n', 'm', 'comma', 'period', 'slash'],
                ]
            )
        )
    ]

    def __init__(self, stack, side, **props):
        """
        Create a new menu.

        ‘side’ tells which side of the keyboard to use (Side.LEFT
        or Side.RIGHT).

        ‘stack’ is the MenuStack this menu belongs to.  The menu will
        call methods on this object to notify it when commands are
        invoked.

        ‘props’ contains GObject properties to be set.

        Subclasses will probably want to call add_unused_keys at the end
        of their constructor.
        """
        super().__init__(
            row_homogeneous=True, column_homogeneous=True, hexpand=True,
            **props
        )
        self.__stack = stack
        self.__side = side
        self.__submenus = set()
        """
        The set of this menu’s submenus.

        This is used to add the submenus to the stack *after* this menu
        has been added to the stack.
        """
        self.__items = {}
        """A dictionary mapping keyvals to the MenuItems they are bound to."""
        self.focus_widget = None
        """The widget that will receive focus when the menu is shown."""
        self.__extra_widgets = set()
        """
        The set of extra (non-key) widgets added to this Menu.

        This is a set of tuples with the format (x, y, width, height, widget).
        """
        spacer = Gtk.Label()
        spacer.show()
        if self.__side == self.Side.LEFT:
            self.attach(spacer, 23, 2, 9, 1)
        else:
            self.attach(spacer, -4, 0, 4, 1)

    def bind_key_to_action(
            self, keyval_name, label, method_name, tooltip=None, repeat=False
    ):
        """
        Bind a key to an action and return it.

        Create a MenuItem with keyval given by keval_name, label
        ‘label’, and tooltip markup ‘tooltip’, put it in the appropriate
        place, and cause it to invoke method_name with no arguments on
        the editor when clicked.  Return the MenuItem.
        """
        item = MenuItem(repeat=repeat)
        item.connect(
            'clicked',
            lambda button: getattr(self.__stack.editor, method_name)()
        )
        self.__install_item(item, keyval_name, label, tooltip)
        return item

    def bind_key_to_toggle(
            self, keyval_name, label, method_name, tooltip=None
    ):
        item = ToggleMenuItem()
        item.connect(
            'toggled',
            lambda button:
                getattr(self.__stack.editor, method_name)(
                    button.props.active
                )
        )
        self.__install_item(item, keyval_name, label, tooltip)

    def bind_key_to_submenu(self, keyval_name, label, submenu, tooltip=None):
        self.__submenus.add(submenu)
        submenu.show_all()
        item = MenuItem()
        item.connect(
            'clicked', lambda button: self.__stack.show_submenu(submenu)
        )
        self.__install_item(item, keyval_name, label, tooltip)

    def bind_key_to_back_button(self, keyval_name):
        item = MenuItem()
        item.connect('clicked', lambda button: self.__stack.go_back())
        self.__install_item(
            item, keyval_name, _('Back'), _('Go back to the previous menu')
        )

    def bind_key_to_widget(self, keyval_name, label, widget, tooltip=None):
        item = MenuItem()
        # XXX: Will this mess up the focus managed by the MenuStack?
        item.connect('clicked', lambda button: self.__stack.pin_menu(widget))
        self.__install_item(item, keyval_name, label, tooltip)

    def __install_item(self, item, keyval_name, label, tooltip):
        keyval = Gdk.keyval_from_name(keyval_name)
        item.keyval = keyval
        item.label = label
        if tooltip is not None:
            item.props.tooltip_markup = tooltip
        item.show()
        x, y = self.__keyval_to_coörds(keyval)
        self.__check_key_for_overlap(x, y)
        self.attach(item, x, y, 4, 1)
        self.__items[keyval] = item

    def __keyval_to_coörds(self, keyval):
        for x, y, found_keyval in self.__iter_keyvals_with_coörds():
            if found_keyval == keyval:
                return x, y
        raise ValueError(
            f'Keyval {keyval} ({Gdk.keyval_name(keyval)}) not found'
        )

    def add_extra_widget(self, widget, x, y, width, height):
        self.__check_widget_for_overlap(x, y, width, height)
        self.attach(widget, x, y, width, height)
        self.__extra_widgets.add((x, y, width, height, widget))

    def add_unused_keys(self):
        """
        Add insensitive menu items for unbound keys.

        This must be called after all calls to bind_key_* and
        add_extra_widget and before using the menu.  Subclasses
        probably want to call this at the end of their constructor,
        although this makes it hard to derive further sub-subclasses.
        """
        for x, y, keyval in self.__iter_keyvals_with_coörds():
            if (
                    keyval not in self.__items
                    and not self.__key_overlaps_extra_widget(x, y)
            ):
                item = MenuItem(sensitive=False)
                item.keyval = keyval
                self.attach(item, x, y, 4, 1)

    def __key_overlaps_extra_widget(self, x, y):
        """
        Check whether a given key would overlap an existing extra widget.

        If the key at grid coördinates (x, y) overlaps a widget
        in self.__extra_widgets, return True.  Otherwise, False.
        """
        for widget_x, widget_y, width, height, widget in self.__extra_widgets:
            if -3 <= x - widget_x < width and 0 <= y - widget_y < height:
                # Key is inside an extra widget
                return True
        else:
            return False

    def __check_key_for_overlap(self, x, y):
        """
        Check whether a given key would overlap an existing extra widget.

        If the key at grid coördinates (x, y) overlaps a widget
        in self.__extra_widgets, raise a ValueError.
        """
        if self.__key_overlaps_extra_widget(x, y):
            raise ValueError(
                f'Key at ({x}, {y}) would overlap an extra widget'
            )

    def __check_widget_for_overlap(self, x, y, width, height):
        """
        Check whether a given rectangle would overlap a bound key.

        If the rectangle given by (x, y, width, height) overlaps one of
        the bound keys, raise a ValueError.
        """
        for key_x, key_y, keyval in self.__iter_keyvals_with_coörds():
            if (
                    keyval in self.__items
                    and x - 3 <= key_x < x + width and y <= key_y < y + height
            ):
                raise ValueError(
                    f'Widget at ({x}, {y}) ({width}×{height}) would '
                    f'overlap key {Gdk.keyval_name(keyval)}'
                )

    def __iter_keyvals_with_coörds(self):
        """
        Iterate over keyvals and their coördinates.

        This is an iterator that yields an (x, y, keyval) tuple for each
        key that is available on this side of the keyboard.
        """
        for y, keyvals in enumerate(self.__keyvals[self.__side]):
            for column, keyval in enumerate(keyvals):
                yield self.__get_key_x(column, y), y, keyval

    def do_parent_set(self, old_parent):
        if old_parent is None:
            for submenu in self.__submenus:
                self.__stack.add_submenu(submenu)

    @property
    def side(self):
        return self.__side

    @property
    def stack(self):
        return self.__stack

    @staticmethod
    def __get_key_x(column, y):
        """
        Return the grid column number of a key.

        Given the coördinates of a key, return the leftmost column
        its button occupies in the grid.
        """
        return 4*column + 3*y//2

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
