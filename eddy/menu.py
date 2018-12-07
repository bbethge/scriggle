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
