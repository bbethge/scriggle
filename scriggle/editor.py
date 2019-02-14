from gettext import gettext as _

import gi
from gi.repository import GLib, Gio, Gdk, Gtk, GtkSource

from .menu_stack import MenuStack


class Editor(Gtk.ApplicationWindow):
    __ROW_TEXT_VIEW = 0
    __ROW_MENU = 1

    def __init__(self, file=None, **props):
        super().__init__(
            default_width=640, default_height=480, icon_name='scriggle',
            **props
        )
        self.__file = file
        self.__saved = True
        self.__close_after_save = False

        grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.add(grid)
        
        self.__menu_stack = MenuStack(self)
        grid.attach(self.__menu_stack, 0, self.__ROW_MENU, 1, 1)

        scroller = Gtk.ScrolledWindow(
            shadow_type=Gtk.ShadowType.IN, expand=True
        )

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
            loader.load_async(
                GLib.PRIORITY_DEFAULT, cancellable, None, None,
                lambda loader, result:
                    self.__finish_loading(
                        loader, result, grid, hgrid, scroller
                    )
            )
            cancel_button.connect('clicked', lambda b: cancellable.cancel())

        grid.show_all()

    def __finish_loading(
            self, loader, result, main_grid, progress_grid, scroller
    ):
        try:
            loader.load_finish(result)
        except GLib.Error as error:
            message = (
                _('Unable to load “{filename}”: {message}')
                .format(
                    filename=loader.props.location.get_path(),
                    message=error.message
                )
            )
            dialog = Gtk.MessageDialog(
                self,
                Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, message
            )
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
                bool(event.new_window_state & Gdk.WindowState.FOCUSED)
            )
        return Gtk.ApplicationWindow.do_window_state_event(self, event)

    def do_key_press_event(self, event):
        if (
                event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]
                or event.state & Gdk.ModifierType.CONTROL_MASK
        ):
            return self.__menu_stack.key_event(event)
        else:
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

    def do_key_release_event(self, event):
        if (
                event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]
                or event.state & Gdk.ModifierType.CONTROL_MASK
        ):
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
            location.get_line(), location.get_line_offset()
        )

    def on_language_changed(self, language_id):
        lang_man = GtkSource.LanguageManager.get_default()
        if language_id == 'plain':
            self.buffer.set_language(None)
        else:
            self.buffer.set_language(lang_man.get_language(language_id))

    def on_use_spaces(self, use_spaces):
        self.__source_view.props.insert_spaces_instead_of_tabs = use_spaces

    def on_tab_width(self):
        # TODO: Turn Tab Width into a focus binding so we don’t need this
        pass

    def on_new(self):
        if self.props.application is not None:
            self.props.application.activate()

    def do_delete_event(self, _event):
        self.on_close()
        return True

    def on_close(self):
        if not self.__saved:
            DISCARD = 0
            SAVE = 1
            dialog = Gtk.MessageDialog(
                self, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.NONE,
                _('Save changes to {} before closing?')
                .format(self.props.title)
            )
            dialog.add_buttons(
                _('Close without Saving'), DISCARD,
                _('Cancel'), Gtk.ResponseType.CANCEL, _('Save'), SAVE
            )
            dialog.set_default_response(SAVE)
            response = dialog.run()
            dialog.destroy()
            if response in [
                    Gtk.ResponseType.CANCEL, Gtk.ResponseType.DELETE_EVENT
            ]:
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

    def on_open(self):
        self.props.application.show_open_dialog(self)

    def on_find(self):
        print('“Find” activated')

    def on_save(self):
        if self.__file is None:
            chooser = Gtk.FileChooserNative.new(
                _('Save As…'), self, Gtk.FileChooserAction.SAVE, None, None
            )
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
            'save-cancel-clicked', lambda b: cancellable.cancel()
        )
        self.__menu_stack.status_area.show_save_status()
        saver = GtkSource.FileSaver(buffer=self.buffer, file=source_file)
        # TODO: Show progress
        saver.save_async(
            GLib.PRIORITY_DEFAULT, cancellable, None, None,
            self.__finish_saving, cancel_handler
        )

    def __finish_saving(self, saver, result, cancel_handler):
        try:
            saver.save_finish(result)
        except GLib.Error as error:
            message = (
                _('Unable to save file “{filename}”: {message}')
                .format(
                    filename=saver.props.location.get_path(),
                    message=error.message
                )
            )
            dialog = Gtk.MessageDialog(
                self, Gtk.DialogFlags.DESTROY_WITH_PARENT,
                Gtk.MessageType.ERROR,
                # XXX: Is ‘Close’ confusing (it
                # will not close the file)?
                Gtk.ButtonsType.CLOSE, message
            )
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

    def on_undo(self):
        # TODO: Set sensitivity of the button depending on
        # self.buffer.can_undo.
        self.buffer.undo()

    def on_cut(self):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.cut_clipboard(clip, True)

    def on_copy(self):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.copy_clipboard(clip)

    def on_paste(self):
        clip = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)
        self.buffer.paste_clipboard(clip, None, True)

    def on_up(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.DISPLAY_LINES, -1, False
        )

    def on_down(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.DISPLAY_LINES, 1, False
        )

    def on_left(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.VISUAL_POSITIONS, -1, False
        )

    def on_right(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.VISUAL_POSITIONS, 1, False
        )

    def on_left_word(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.WORDS, -1, False
        )

    def on_right_word(self):
        self.__source_view.emit(
            'move-cursor', Gtk.MovementStep.WORDS, 1, False
        )
