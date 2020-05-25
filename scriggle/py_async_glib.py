import gi
from gi.repository import GLib, GtkSource


def _call_next(it, value=None):
    """
    Helper function to run the next step of the coroutine.

    Given an iterator ‘it’, send it a value, and, if it generates another
    object, assume it is a callable and call it with the iterator as an
    argument.
    """
    try:
        f = it.send(value)
    except StopIteration:
        pass
    else:
        f(it)


def wrap(coroutine):
    """
    Wrap a coroutine that calls GLib async functions.
    
    ‘coroutine’ is a coroutine that awaits one or more of the
    awaitables in this module which wrap GLib-style async
    functions.  The result is a normal function that runs until
    it calls a GLib-style async function and then returns.  When the
    GLib-style async function is complete, the coroutine will resume.
    """
    return lambda *a, **k: _call_next(coroutine(*a, **k).__await__())


class idle:
    """Awaitable that schedules the awaiter to be resumed later."""

    def __await__(self):
        def do_it(it):
            def source_func(*args, **kwargs):
                _call_next(it)
                return False
            GLib.idle_add(source_func)
        yield do_it


class GtkSourceSave:
    """Wrapper for GtkSource.save_async."""

    def __init__(self, saver, priority, cancellable, progress_callback):
        self.__saver = saver
        self.__priority = priority
        self.__cancellable = cancellable
        self.__progress_callback = progress_callback

    def __await__(self):
        def do_it(it):
            self.__saver.save_async(
                self.__priority, self.__cancellable, self.__progress_callback,
                None, lambda s, r, *a: _call_next(it, (s, r)), None
            )
        saver, result = yield do_it
        saver.save_finish(result)
# Have to wrap GtkSourceSave in an actual function so it will be
# automatically converted into a method.
GtkSource.FileSaver.save_pyasync = lambda *a, **k: GtkSourceSave(*a, **k)


class GtkSourceLoad:
    """Wrapper for GtkSource.load_async."""

    def __init__(self, loader, priority, cancellable, progress_callback):
        self.__loader = loader
        self.__priority = priority
        self.__cancellable = cancellable
        self.__progress_callback = progress_callback

    def __await__(self):
        def do_it(it):
            self.__loader.load_async(
                self.__priority, self.__cancellable, self.__progress_callback,
                None, lambda L, r, *a: _call_next(it, (L, r)), None
            )
        loader, result = yield do_it
        loader.load_finish(result)
GtkSource.FileLoader.load_pyasync = lambda *a, **k: GtkSourceLoad(*a, **k)


class GtkSourceSearchForward:
    """Wrapper for GtkSource.SearchContext.forward_async."""

    def __init__(self, context, text_iter, cancellable):
        self.__context = context
        self.__text_iter = text_iter
        self.__cancellable = cancellable

    def __await__(self):
        def do_it(it):
            self.__context.forward_async(
                self.__text_iter, self.__cancellable,
                lambda c, r, *a: _call_next(it, (c, r))
            )
        context, result = yield do_it
        return context.forward_finish2(result)
GtkSource.SearchContext.forward_pyasync = (
    lambda *a, **k: GtkSourceSearchForward(*a, **k)
)
