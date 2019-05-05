from gettext import gettext as _

import gi
from gi.repository import GLib, GObject, Gio, Gdk, Gtk, GtkSource

from .command_manager import CommandManager
from .menu_stack import MenuArea


class Editor(Gtk.ApplicationWindow):
    __ROW_TEXT_VIEW = 0
    __ROW_SAVE_INDICATOR = 1
    __ROW_MENU = 2

    def __init__(self, file=None, **props):
        super().__init__(
            default_width=640, default_height=480, icon_name='scriggle',
            **props
        )
        self.__file = file
        self.__saved = True
        self.__close_after_save = False
        self.__command_manager = CommandManager()

        grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)
        self.add(grid)

        self.__save_indicator = SaveIndicator()
        grid.attach(self.__save_indicator, 0, self.__ROW_SAVE_INDICATOR, 1, 1)

        self.__menu_revealer = MenuRevealer(self.__command_manager)
        grid.attach(self.__menu_revealer, 0, self.__ROW_MENU, 1, 1)

        scroller = Gtk.ScrolledWindow(
            shadow_type=Gtk.ShadowType.IN, expand=True
        )

        self.__source_view = GtkSource.View(expand=True, monospace=True)
        scroller.add(self.__source_view)
        self.buffer.connect('mark-set', self.__on_mark_set)
        self.__command_manager.undo.enabled = False
        self.buffer.connect('notify::can-undo', self.__forward_can_undo)
        self.__on_cursor_position_changed(self.buffer.get_start_iter())

        SearchManager(self.__command_manager, self.__source_view)

        self.__command_manager.undo.connect(self.on_undo)
        self.__command_manager.cut.connect(self.on_cut)
        self.__command_manager.copy.connect(self.on_copy)
        self.__command_manager.paste.connect(self.on_paste)
        self.__command_manager.up.connect(self.on_up)
        self.__command_manager.left.connect(self.on_left)
        self.__command_manager.down.connect(self.on_down)
        self.__command_manager.right.connect(self.on_right)
        self.__command_manager.left_word.connect(self.on_left_word)
        self.__command_manager.right_word.connect(self.on_right_word)
        self.__command_manager.new.connect(self.on_new)
        self.__command_manager.close.connect(self.on_close)
        self.__command_manager.open.connect(self.on_open)
        self.__command_manager.save.connect(self.on_save)
        self.__command_manager.set_use_spaces.connect(self.on_use_spaces)
        self.__command_manager.set_tab_width.connect(self.on_tab_width_changed)
        self.__command_manager.set_language.connect(self.on_language_changed)

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
        scroller.show_all()
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

    @property
    def menu_revealer(self):
        return self.__menu_revealer

    def do_window_state_event(self, event):
        if event.changed_mask & Gdk.WindowState.FOCUSED:
            self.__menu_revealer.window_focus_changed(
                bool(event.new_window_state & Gdk.WindowState.FOCUSED)
            )
        return Gtk.ApplicationWindow.do_window_state_event(self, event)

    def do_key_press_event(self, event):
        if self.__menu_revealer.key_event(event):
            return True
        else:
            return Gtk.ApplicationWindow.do_key_press_event(self, event)

    def do_key_release_event(self, event):
        if self.__menu_revealer.key_event(event):
            return True
        else:
            return Gtk.ApplicationWindow.do_key_release_event(self, event)

    def __on_mark_set(self, _buffer, location, mark):
        if mark.props.name == 'insert':
            self.__on_cursor_position_changed(location)

    def __on_buffer_changed(self, buffer):
        location = buffer.get_iter_at_mark(buffer.get_insert())
        self.__on_cursor_position_changed(location)
        self.__saved = False

    def __on_cursor_position_changed(self, location):
        self.__menu_revealer.cursor_position = (
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

    def on_tab_width_changed(self, tab_width):
        self.__source_view.props.tab_width = tab_width

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

    def on_find(self, needle):
        # TODO
        print(f'Find “{needle}”')

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
        cancel_handler = self.__save_indicator.connect(
            'cancel-clicked', lambda b: cancellable.cancel()
        )
        self.__save_indicator.show_all()
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
        self.__save_indicator.hide()
        self.__save_indicator.disconnect(cancel_handler)

    def __forward_can_undo(self, buffer_, pspec):
        self.__command_manager.undo.enabled = buffer_.props.can_undo

    def on_undo(self):
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


class SearchManager:
    def __init__(self, command_manager, view):
        self.__command_manager = command_manager
        self.__view = view
        self.__buffer = view.props.buffer
        self.__buffer.connect('mark-set', self.__mark_set_cb)
        self.__search_context = GtkSource.SearchContext.new(
            self.__buffer, None
        )
        self.__search_settings = self.__search_context.props.settings
        self.__command_manager.find_next.connect(self.__on_find_next)
        self.__command_manager.replace.connect(self.__on_replace)
        self.__command_manager.replace.enabled = False
        self.__command_manager.replace_all.connect(self.__on_replace_all)
        self.__command_manager.replace_all.enabled = False
        self.__command_manager.find_match_case.connect(
            self.__on_find_match_case
        )
        self.__command_manager.find_regex.connect(self.__on_find_regex_changed)

    def __on_find_next(self, text_to_find):
        self.__search_settings.props.search_text = text_to_find
        self.__find_current_search_text()

    def __find_current_search_text(self):
        self.__command_manager.find_next.enabled = False
        self.__command_manager.replace.enabled = False
        self.__command_manager.replace_all.enabled = False
        self.__search_context.forward_async(
            self.__buffer.get_iter_at_mark(self.__buffer.get_insert()),
            None, lambda context, result: self.__find_finished_cb(result)
        )

    def __find_finished_cb(self, result):
        matched, start, end, _wrapped = (
            self.__search_context.forward_finish2(result)
        )
        if matched:
            # First argument will be the insertion point -- we want that
            # to be the end of the match.
            self.__buffer.select_range(end, start)
            self.__selection_changed_since_find = False
            # Scroll to the start *and* the end to get as much as
            # possible of the match into view.
            # See the documentation of Gtk.TextView.scroll_to_iter for a
            # possible issue about computing line heights.  Since we
            # will almost certainly have fixed line heights, this
            # shouldn’t be a problem.
            self.__view.scroll_to_iter(start, 0.1, False, 0, 0)
            self.__view.scroll_to_iter(end, 0.1, False, 0, 0)
        self.__command_manager.replace.enabled = matched
        self.__command_manager.replace_all.enabled = matched
        self.__command_manager.find_next.enabled = True

    def __mark_set_cb(self, buffer_, iter_, mark):
        if mark.props.name in ('insert', 'selection_bound'):
            self.__command_manager.replace.enabled = False

    def __replacement_is_valid(self, replacement):
        result = True
        if self.__search_settings.props.regex_enabled:
            try:
                GLib.regex_check_replacement(replacement)
            except GLib.Error as error:
                if error.matches(
                        GLib.regex_error_quark(), GLib.RegexError.REPLACE
                ):
                    result = False
                else:
                    raise
        return result

    def __on_replace(self, replacement):
        # FIXME: Show user why replacement is invalid.
        if self.__replacement_is_valid(replacement):
            start, end = self.__buffer.get_selection_bounds()
            self.__search_context.replace2(start, end, replacement, -1)
            self.__find_current_search_text()

    def __on_replace_all(self, text_to_find, replacement):
        # XXX: Could the user conceivably edit the buffer while this is
        #      happening?
        # FIXME: Show user why replacement is invalid.
        if self.__replacement_is_valid(replacement):
            self.__search_settings.props.search_text = text_to_find
            self.__command_manager.find_next.enabled = False
            self.__command_manager.replace.enabled = False
            self.__command_manager.replace_all.enabled = False
            self.__buffer.begin_user_action()
            self.__search_context.forward_async(
                self.__buffer.get_start_iter(), None,
                lambda context, result:
                    self.__replace_all_finished_one_cb(result, replacement)
            )

    def __replace_all_finished_one_cb(self, result, replacement):
        matched, start, end, wrapped = (
            self.__search_context.forward_finish2(result)
        )
        if matched and not wrapped:
            self.__search_context.replace2(start, end, replacement, -1)
            GLib.idle_add(self.__replace_all_idle_cb, end, replacement)
        else:
            self.__buffer.end_user_action()
            self.__command_manager.find_next.enabled = True

    def __replace_all_idle_cb(self, start_iter, replacement):
        self.__search_context.forward_async(
            start_iter, None,
            lambda context, result:
                self.__replace_all_finished_one_cb(result, replacement)
        )
        return False

    def __on_find_match_case(self, match_case):
        self.__search_settings.props.case_sensitive = match_case

    def __on_find_regex_changed(self, use_regex):
        self.__search_settings.props.regex_enabled = use_regex


class SaveIndicator(Gtk.Grid):
    def __init__(self, **props):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL, no_show_all=True
        )

        save_label = Gtk.Label(_('Saving…'))
        self.add(save_label)

        save_cancel_button = Gtk.Button.new_with_label(_('Cancel'))
        save_cancel_button.connect(
            'clicked', lambda b: self.emit('cancel-clicked')
        )
        self.add(save_cancel_button)

    @GObject.Signal
    def cancel_clicked(self):
        pass


class MenuRevealer(Gtk.Revealer):
    def __init__(self, command_manager):
        super().__init__(transition_type=Gtk.RevealerTransitionType.SLIDE_UP)
        self.__command_manager = command_manager
        self.__menu_area = MenuArea(command_manager)
        self.add(self.__menu_area)
        self.__menu_pinned = False
        self.__control_pressed = False

    @property
    def menu_pinned(self):
        return self.__menu_pinned

    @menu_pinned.setter
    def menu_pinned(self, value):
        if not value and not self.__control_pressed:
            self.props.reveal_child = False
        self.__menu_pinned = value

    @property
    def left_menu(self):
        return self.__menu_area.left_menu

    @property
    def right_menu(self):
        return self__menu_area.right_menu

    @property
    def cursor_position(self):
        return self.__menu_area.cursor_position

    @cursor_position.setter
    def cursor_position(self, position):
        self.__menu_area.cursor_position = position

    def key_event(self, event):
        if event.keyval in [Gdk.KEY_Control_L, Gdk.KEY_Control_R]:
            if event.type == Gdk.EventType.KEY_PRESS:
                return self.__on_control_pressed(event.keyval)
            else:
                return self.__on_control_released()
        elif event.state & Gdk.ModifierType.CONTROL_MASK:
            return self.__menu_area.key_event(event)
        else:
            return False

    def __on_control_pressed(self, keyval):
        self.__control_pressed = True
        self.props.reveal_child = True
        if not self.__menu_pinned:
            if keyval == Gdk.KEY_Control_L:
                self.__menu_area.show_menu_immediately(
                    self.__menu_area.right_menu
                )
            else:
                self.__menu_area.show_menu_immediately(
                    self.__menu_area.left_menu
                )

    def __on_control_released(self):
        self.__control_pressed = False
        if not self.__menu_pinned:
            self.props.reveal_child = False

    def window_focus_changed(self, focused):
        """
        Notify ‘self’ of focus changes in its toplevel window

        Treat loss of window focus the same as Ctrl being released.
        """
        if not focused:
            self.__on_control_released()
