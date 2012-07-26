#! /usr/bin/env python3

from gi.repository import Gio, Gdk, Gtk

def _(x):
	return x

class MenuItem(Gtk.Button):
	'''
		A button that looks somewhat like a large gtk.ToolButton but
		has a key associated with it and is activated by that key.
		It goes inside a Menu.
	'''
	def __init__(self, label = None, stock_id = None, **props):
		super().__init__(**props )

		self.__grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
		self.add(self.__grid)

		self.__icon = Gtk.Image(expand=True)
			# ⬑ ‘expand’ is needed to make everything centered
			# inside the button.
		self.__grid.add(self.__icon)

		self.__label = Gtk.Label(hexpand=True, use_underline=True)
		self.__grid.add(self.__label)

		self.__keyval_label = Gtk.Label()
		self.__grid.add(self.__keyval_label)

		self.__stock_id = None
		self.label = label
		self.icon_size = Gtk.IconSize.LARGE_TOOLBAR
		self.stock_id = stock_id
		self.keyval = None

		self.__grid.show_all()

	@property
	def keyval(self):
		return self.__keyval
	@keyval.setter
	def keyval(self, keyval):
		if keyval is not None:
			self.__keyval_label.set_markup(
				'<b>'+Gdk.keyval_name(keyval)+'</b>')
		else:
			self.__keyval_label.props.label = ''

	@property
	def icon_size(self):
		return self.__icon_size
	@icon_size.setter
	def icon_size(self, icon_size):
		self.__icon_size = icon_size
		self.stock_id = self.__stock_id

	@property
	def label(self):
		return self.__label.props.label
	@label.setter
	def label(self, label):
		if label:
			self.__label.set_markup('<small>'+label+'</small>')
		else:
			self.__label.props.label = ''

	@property
	def stock_id(self):
		return self.__stock_id
	@stock_id.setter
	def stock_id(self, stock_id):
		if stock_id is not None:
			if len(self.__label.props.label) == 0:
				self.label = get_stock_label(stock_id)
			self.__icon.set_from_stock(stock_id, self.__icon_size)
		else:
			self.__icon.set_from_stock(
				Gtk.STOCK_MISSING_IMAGE, self.__icon_size )
		self.__stock_id = stock_id

def get_stock_label(stock_id):
	return Gtk.stock_lookup(stock_id).label

class Menu(Gtk.Grid):
	'''
		A panel with several MenuItems arranged in a keyboard-
		like layout that can be activated by the corresponding keys.
	'''
	_keyvals = NotImplemented

	def __init__(self, **props):
		super().__init__(
			row_homogeneous=False, column_homogeneous=True,
			events=
				Gdk.EventMask.KEY_PRESS_MASK
				| Gdk.EventMask.KEY_RELEASE_MASK,
			**props)
		if type(self) == Menu:
			raise NotImplementedError('Abstract class')
		self.__buttons = {}

	def add_item(self, item, row, column):
		keyval = self._keyvals[row][column]
		item.keyval = keyval
		item.icon_size = (
			Gtk.IconSize.LARGE_TOOLBAR if row == 1
			else Gtk.IconSize.MENU )
		item.show()
		self.attach(item, 4*column+row**2-row//2, row, 4, 1)
		self.__buttons[keyval] = item

	def remove_item(self, row, column):
		keyval = self._keyvals[row][column]
		if keyval in self.__buttons:
			self.remove(self.__buttons[keyval])
			del self.__buttons[keyval]

	def key_press_event(self, event):
		if event.keyval in self.__buttons:
			self.__buttons[event.keyval].activate()
			return True
		return False

	def key_release_event(self, event):
		return False

class LMenu(Menu):
	_keyvals = tuple(map(
		lambda kns: tuple(map(Gdk.keyval_from_name, kns)),
		(	('q', 'w', 'e', 'r', 't'),
			('a', 's', 'd', 'f', 'g'),
			('z', 'x', 'c', 'v', 'b') ) ) )

class RMenu(Menu):
	_keyvals = tuple(map(
		lambda kns: tuple(map(Gdk.keyval_from_name, kns)),
		(	('y', 'u', 'i', 'o', 'p', 'bracketleft', 'bracketright'),
			('h', 'j', 'k', 'l', 'semicolon', 'apostrophe'),
			('n', 'm', 'comma', 'period', 'slash') ) ) )

class Editor(Gtk.ApplicationWindow):
	def __init__(self, file=None, **props):
		super().__init__(**props)

		grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
		self.add(grid)

		self.__right_menu = RMenu(
			expand=False, halign=Gtk.Align.END, no_show_all=True)
		grid.add(self.__right_menu)
		def add_R(stock, r, c, cb):
			item = MenuItem(stock_id=stock)
			self.__right_menu.add_item(item, r, c)
			if cb is not None:
				item.connect('clicked', lambda w: cb())
		add_R(Gtk.STOCK_NEW, 0, 1, self._on_new)
		add_R(Gtk.STOCK_CLOSE, 0, 2, self._on_close)
		add_R(Gtk.STOCK_FIND, 1, 1, None)

		self.__left_menu = LMenu(
			expand=False, halign=Gtk.Align.START, no_show_all=True)
		grid.add(self.__left_menu)
		def add_L(stock, r, c, cb):
			item = MenuItem(stock_id=stock)
			self.__left_menu.add_item(item, r, c)
			if cb is not None:
				item.connect('clicked', lambda w: cb())
		add_L(Gtk.STOCK_UNDO, 2, 0, None)
		add_L(Gtk.STOCK_CUT, 2, 1, self._on_cut)
		add_L(Gtk.STOCK_COPY, 2, 2, self._on_copy)
		add_L(Gtk.STOCK_PASTE, 2, 3, self._on_paste)
		add_L(Gtk.STOCK_GO_UP, 0, 2, self._on_up)
		add_L(Gtk.STOCK_GO_BACK, 1, 1, self._on_left)
		add_L(Gtk.STOCK_GO_DOWN, 1, 2, self._on_down)
		add_L(Gtk.STOCK_GO_FORWARD, 1, 3, self._on_right)

		tv_scroller = Gtk.ScrolledWindow(
			shadow_type=Gtk.ShadowType.IN, expand=True)

		self.__text_view = Gtk.TextView()
		tv_scroller.add(self.__text_view)
		self.__text_view.connect(
			'key-press-event', self._on_key_press_event)
		self.__text_view.connect(
			'key-release-event', self._on_key_release_event)

		if file is None:
			grid.add(tv_scroller)
		else:
			hgrid= Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL)
			label = Gtk.Label(_('Loading…'))
			hgrid.add(label)
			cancel_button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
			hgrid.add(cancel_button)
			grid.add(hgrid)
			hgrid.show_all()

			def callback(file, result, _data=None):
				status, contents, _etag = \
					file.load_contents_finish(result)
				grid.remove(hgrid)
				if status:
					buffer = Gtk.TextBuffer()
					buffer.set_text(str(contents, 'utf-8', 'replace'))
					self.__text_view.props.buffer = buffer
					tv_scroller.show_all()
					grid.add(tv_scroller)
				else:
					label.props.label = _('Error!')
					grid.add(label)

			cancellable = Gio.Cancellable()
			file.load_contents_async(cancellable, callback, None)
			cancel_button.connect('clicked', lambda b: cancellable.cancel())

		grid.show_all()

	@property
	def buffer(self):
		return self.__text_view.props.buffer
	@buffer.setter
	def buffer(self, buffer):
		self.text_view.props.buffer = buffer

	def _on_key_press_event(self, _text_view, event):
		if event.keyval == Gdk.KEY_Control_L:
			self.__right_menu.show()
			return True
		if (event.keyval == Gdk.KEY_Control_R
				and not self.__right_menu.props.visible):
			self.__left_menu.show()
			return True
		if self.__left_menu.props.visible:
			return self.__left_menu.key_press_event(event)
		if self.__right_menu.props.visible:
			return self.__right_menu.key_press_event(event)
		return False

	def _on_key_release_event(self, _text_view, event):
		if event.keyval == Gdk.KEY_Control_L:
			self.__right_menu.hide()
			return True
		if event.keyval == Gdk.KEY_Control_R:
			self.__left_menu.hide()
			return True
		if self.__left_menu.props.visible:
			return self.__left_menu.key_release_event(event)
		if self.__right_menu.props.visible:
			return self.__right_menu.key_release_event(event)
		return False

	def _on_new(self):
		if self.props.application is not None:
			self.props.application.activate()

	def _on_close(self):
		self.hide()
		if self.props.application is not None:
			self.props.application.remove_window(self)

	def _on_cut(self):
		clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
		self.buffer.cut_clipboard(clip, True)

	def _on_copy(self):
		clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
		self.buffer.copy_clipboard(clip)

	def _on_paste(self):
		clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
		self.buffer.paste_clipboard(clip, None, True)

	def _on_up(self):
		self.__text_view.emit(
			'move-cursor', Gtk.MovementStep.DISPLAY_LINES, -1,
			False )

	def _on_down(self):
		self.__text_view.emit(
			'move-cursor', Gtk.MovementStep.DISPLAY_LINES, 1,
			False )

	def _on_left(self):
		self.__text_view.emit(
			'move-cursor', Gtk.MovementStep.VISUAL_POSITiONS, -1,
			False )

	def _on_right(self):
		self.__text_view.emit(
			'move-cursor', Gtk.MovementStep.VISUAL_POSITIONS, 1,
			False )

class Application(Gtk.Application):
	def __init__(self):
		super().__init__(
			application_id='com.example.Eddy',
			flags=
				Gio.ApplicationFlags.HANDLES_OPEN
				| Gio.ApplicationFlags.HANDLES_COMMAND_LINE )

	def do_command_line(self, command_line):
		'''
			This is overridden only to work around the fact that do_open is
			invoked incorrectly when called from C.
		'''
		args = command_line.get_arguments()
		if len(args) <= 1:
			self.activate()
		else:
			files = [
				Gio.File.new_for_commandline_arg(arg)
				for arg in args[1:] ]
			self.do_open(files, len(files), '')

	def do_open(self, files, _n_files, _hint):
		for file in files:
			editor = Editor(file)
			self.add_window(editor)
			editor.show()

	def do_activate(self):
		editor = Editor()
		self.add_window(editor)
		editor.show()

if __name__ == '__main__':
	import sys
	sys.exit(Application().run(sys.argv))
