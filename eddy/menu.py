from dataclasses import dataclass
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


@dataclass
class Binding:
    """
    Represents an ordinary or toggle key binding.

    This is used when constructing Menu._bindings to represent a binding
    to an ordinary command (toggle=False) or toggle control
    (toggle=True).  ‘label’ and ‘tooltip’ are used to construct the
    button.  ‘method’ is the name of the method to be invoked on the
    stack that owns the menu.  If toggle=False, the method is invoked
    with no arguments; if toggle=True, the method receives a single
    argument, the state of the toggle.
    """
    label: str
    method: str
    tooltip: str = None
    toggle: bool = False


@dataclass
class SubmenuBinding:
    """
    Represents a submenu binding.

    This is used when constructing Menu._bindings to represent a binding
    that opens a submenu.  ‘label’ and ‘tooltip’ are used to construct
    the button, submenu_class gives the Menu subclass that will be
    instantiated (with the menu stack as the only argument) to create
    the submenu, and ‘attr’ gives the attribute name used to store a
    reference to the submenu on the menu being created.
    """
    label: str
    submenu_class: type
    attr: str
    tooltip: str = None


class BackBinding():
    """
    Represents a back button binding.

    This is used when constructing Menu._bindings to represent a binding
    that goes back to the parent menu.
    """
    __slots__ = ()


class Menu(Gtk.Grid):
    """
    A menu using a keyboard-like layout.

    A panel with several MenuItems arranged in a grid that mimics one
    half of the keyboard.  This will be shown by holding down the Ctrl
    key on the opposite side, and MenuItems can be activated by
    pressing the corresponding key.

    This is an abstract class.  All menus must be an instance of a
    Menu subclass.  See Menu._side and Menu._bindings.
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

    _side = NotImplemented
    """Which side of the keyboard to use.  Must be overriden by subclasses."""

    _bindings = NotImplemented
    """
    Dictionary describing key bindings for Menu subclasses.

    Menu subclasses must override this attribute.  It is a dictionary
    having keyval names as keys and instances of Binding,
    SubmenuBinding, or BackBinding as values.
    """

    def __init__(self, stack, override_widgets=(), focus_widget=None, **props):
        """
        Create a new menu.

        ‘side’ tells which side of the keyboard to use (Side.LEFT
        or Side.RIGHT).

        ‘stack’ is the MenuStack this menu belongs to.  The menu will
        call methods on this object to notify it when commands are
        invoked.

        override_widgets is a sequence of specifications for widgets
        that will replace some of the buttons.  Each specification is a
        sequence of five things: x, y, width, and height of the region
        to be used, and the widget itself.  The region is given in grid
        coördinates: each key has a width of four, the first row starts
        at column 0, the second at column 1, and the third at column 3.

        focus_widget is one of the widgets in override_widgets that will
        be focused when the menu pops up, taking focus from the source
        view.  This implies that the menu will be pinned (prevented from
        disappearing when the Ctrl key is released) so that the user can
        type into it with both hands.

        ‘props’ contains GObject properties to be set.
        """
        super().__init__(**dict(row_homogeneous=True, column_homogeneous=True,
                                hexpand=True, **props))
        self.__focus_widget = focus_widget
        self.__stack = stack
        self.__submenus = []
        self.__items = {}
        for row, row_contents in enumerate(self.__keyvals[self._side]):
            for column, keyval in enumerate(row_contents):
                grid_col = self.__key_coörds_to_grid_col(row, column)
                check = self.__check_for_overlap(row, grid_col,
                                                 override_widgets)
                if check is None:
                    self.__install_item(keyval, row, grid_col)
                elif Gdk.keyval_name(keyval) in self._bindings:
                    raise ValueError(
                        f'Override widget at ({check[0]}, {check[1]}) '
                        f'overlaps bound key at ({row}, {grid_col}).')
        for x, y, width, height, widget in override_widgets:
            self.attach(widget, x, y, width, height)
        spacer = Gtk.Label()
        spacer.show()
        if self._side == self.Side.LEFT:
            self.attach(spacer, 23, 2, 9, 1)
        else:
            self.attach(spacer, -4, 0, 4, 1)

    def __check_for_overlap(self, row, grid_col, override_widgets):
        """
        Check whether a given key overlaps an override widget.

        If the key at grid coördinates (row, grid_col) overlaps a widget
        in override_widgets, return the grid coördinates of that widget.
        Otherwise, return None.
        """
        for x, y, width, height, _widget in override_widgets:
            if x - 3 <= grid_col < x + width and y <= row < y + height:
                # Key is inside an override widget
                return x, y
        return None

    def __install_item(self, keyval, row, grid_col):
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name not in self._bindings:
            item = MenuItem(sensitive=False)
        else:
            binding = self._bindings[keyval_name]
            if isinstance(binding, Binding):
                if binding.toggle:
                    item = ToggleMenuItem(tooltip_markup=binding.tooltip)
                    item.connect(
                        'toggled',
                        lambda button:
                            getattr(self.__stack.window, binding.method)(
                                button.props.active))
                else:
                    item = MenuItem(tooltip_markup=binding.tooltip)
                    item.connect(
                        'clicked',
                        lambda _button:
                            getattr(self.__stack.window, binding.method)())
                item.label = binding.label
            elif isinstance(binding, SubmenuBinding):
                submenu = binding.submenu_class(self.__stack)
                setattr(self, binding.attr, submenu)
                self.__submenus.append(submenu)
                submenu.show_all()
                item = MenuItem(tooltip_markup=binding.tooltip)
                item.connect(
                    'clicked',
                    lambda button:
                        self.__stack.show_submenu(getattr(self, binding.attr)))
                item.label = binding.label
            elif isinstance(binding, BackBinding):
                item = MenuItem(
                    tooltip_markup=_('Go back to the previous menu'))
                item.connect('clicked', lambda button: self.__stack.go_back())
                item.label = _('Back')
            else:
                assert False
        item.keyval = keyval
        item.show()
        self.attach(item, grid_col, row, 4, 1)
        self.__items[keyval] = item

    def do_parent_set(self, old_parent):
        if old_parent is None:
            for submenu in self.__submenus:
                self.__stack.add_submenu(submenu)

    @property
    def side(self):
        return self._side

    @property
    def stack(self):
        return self.__stack

    @property
    def focus_widget(self):
        return self.__focus_widget

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
