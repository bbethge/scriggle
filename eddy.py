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
	def __init__(self, keyval, label = None, stock_id = None):
		super().__init__(relief=Gtk.ReliefStyle.NONE)

		self.__vbox = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
		self.add(self.__vbox)
		self.__vbox.show()

		self.__icon = Gtk.Image()
		self.__vbox.add(self.__icon)
		self.__icon.show()
		self.set_stock_id(stock_id)

		self.__label = Gtk.Label()
		self.__vbox.add(self.__label)
		self.__label.show()
		self.set_label(label)

		self.__keyval_label = Gtk.Label()
		self.__vbox.add(self.__keyval_label)
		self.__keyval_label.show()
		self.set_keyval(keyval)

	def set_keyval(self, keyval):
		self.__keyval = keyval
		self.__keyval_label.set_markup(
			'<big><b>' + Gdk.keyval_name(keyval) + '</b></big>')

	def get_keyval(self):
		return self.__keyval

	def set_label(self, label):
		if label is not None:
			self.__label.set_text(label)

	def set_stock_id(self, stock_id):
		if stock_id is not None:
			self.__icon.set_from_stock(
				stock_id, Gtk.IconSize.LARGE_TOOLBAR)
		else:
			self.__icon.set_from_stock(
				Gtk.STOCK_MISSING_IMAGE,
				Gtk.IconSize.LARGE_TOOLBAR)

class Menu(Gtk.Window):
	'''
		A popup widow with several MenuItems arranged in a keyboard-
		like layout that can be activated by the corresponding keys.
	'''
	class __KeyInfo:
		def __init__(self, keyval, row, col):
			self.keyval = keyval
			self.row = row
			self.col = col

	__keyinfo = (
		__KeyInfo(Gdk.keyval_from_name('j'), 0, 0),
		__KeyInfo(Gdk.keyval_from_name('k'), 0, 1),
		__KeyInfo(Gdk.keyval_from_name('l'), 0, 2),
		__KeyInfo(Gdk.keyval_from_name('semicolon'), 0, 3))

	def __init__(self):
		super().__init__(
			type=Gtk.WindowType.POPUP,
			events=Gdk.EventMask.KEY_PRESS_MASK|Gdk.EventMask.KEY_RELEASE_MASK)
		self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

		frame = Gtk.Frame()
		frame.set_shadow_type(Gtk.ShadowType.OUT)
		self.add(frame)
		frame.show()

		self.__table = Gtk.Grid(
			row_homogeneous=True, column_homogeneous=True)
		frame.add(self.__table)
		self.__table.show()

		self.__buttons = {}

	def add_item(self, item, index):
		item.set_keyval(Menu.__keyinfo[index].keyval)
		item.show()
		self.__buttons[index] = item
		self.__table.attach(
			item, Menu.__keyinfo[index].col, Menu.__keyinfo[index].row,
			1, 1)

	def remove_item(self, index):
		if self.__buttons[index] is not None:
			self.__table.remove(self.__buttons[index])
			self.__buttons[index] = None

	def __keyval_to_index(keyval):
		for i in range(0, len(Menu.__keyinfo)):
			if Menu.__keyinfo[i].keyval == keyval:
				return i
		return -1

	def key_press_event(self, event):
		return False

	def key_release_event(self, event):
		for index, keyinfo in enumerate(Menu.__keyinfo):
			if keyinfo.keyval == event.keyval:
				self.__buttons[index].activate()
				return True
		return False

class TextView(Gtk.TextView):
	def __init__(self, **props):
		super().__init__(**props)
		self.menu = Menu()
		self.menu.add_item(MenuItem(keyval, 'New', Gtk.STOCK_NEW), 0)
		self.menu.add_item(MenuItem(keyval, 'Close', Gtk.STOCK_CLOSE), 1)
		item = MenuItem(keyval, 'Copy', Gtk.STOCK_COPY)
		item.connect('clicked',
			lambda w: self.props.buffer.copy_clipboard(
				self.get_clipboard(Gdk.SELECTION_CLIPBOARD)))
		self.menu.add_item(item, 2)
		item = MenuItem(keyval, 'Paste', Gtk.STOCK_PASTE)
		item.connect('clicked',
			lambda w: self.props.buffer.paste_clipboard(
				self.get_clipboard(Gdk.SELECTION_CLIPBOARD), None, True))
		self.menu.add_item(item, 3)

	def do_hierarchy_changed(self, prev_toplevel):
		toplevel = self.get_toplevel()
		if isinstance(toplevel, Gtk.Window):
			self.menu.set_transient_for(toplevel)

	def do_key_press_event(self, event):
		if event.keyval == Gdk.KEY_Control_L:
			self.menu.present_with_time(event.time)
			return True
		if self.menu.props.visible:
			return self.menu.key_press_event(event)
		return Gtk.TextView.do_key_press_event(self, event)

	def do_key_release_event(self, event):
		if event.keyval == Gdk.KEY_Control_L:
			self.menu.hide()
			return True
		if self.menu.props.visible:
			return self.menu.key_release_event(event)
		return Gtk.TextView.do_key_release_event(self, event)

class Application(Gtk.Application):
	def __init__(self):
		super().__init__(
			application_id='com.example.Eddy',
			flags=Gio.ApplicationFlags.HANDLES_OPEN|Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
		self.connect('open', lambda *args: print(args))

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
				Gio.File.new_for_commandline_arg(arg) for arg in args[1:] ]
			self.do_open(files, len(files), '')

	def do_open(self, files, _n_files, _hint):
		for file in files:
			window = Gtk.ApplicationWindow()
			self.add_window(window)
			grid = Gtk.Grid()
			label = Gtk.Label(_('Loading…'))
			grid.add(label)
			def callback(file, result, _data=None):
				status, contents, _etag = file.load_contents_finish(result)
				window.remove(grid)
				if status:
					text_buf = Gtk.TextBuffer()
					text_buf.set_text(str(contents, 'utf-8', 'replace'))
					text_view = TextView(buffer=text_buf)
					sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
					sw.add(text_view)
					sw.show_all()
					window.add(sw)
				else:
					label.props.text = _('Error!')
					window.add(label)
			cancellable = Gio.Cancellable()
			file.load_contents_async(cancellable, callback, None)
			cancel_button = Gtk.Button.new_from_stock(Gtk.STOCK_CANCEL)
			cancel_button.connect('clicked', lambda w: cancellable.cancel())
			grid.add(cancel_button)
			grid.show_all()
			window.add(grid)
			window.show()

	def do_activate(self):
		window = Gtk.ApplicationWindow()
		self.add_window(window)
		text_view = TextView()
		sw = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
		sw.add(text_view)
		window.add(sw)
		window.show_all()

if __name__ == '__main__':
	import sys

	keyval = Gdk.keyval_from_name('0')

	sys.exit(Application().run(sys.argv))
