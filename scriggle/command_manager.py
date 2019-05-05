class CommandManager:
    """
    Manages a set of callbacks.

    This allows any object to send a signal that can be received by any
    other object without the sender having to register the signal
    before objects can connect a handler to it.

    Each command is an attribute of the CommandManager object.  To run
    the handlers connected to a command, just call the attribute:
        command_manager.foo_command()
    The handlers are run in undefined order.  To connect a handler:
        command_manager.foo_command.connect(handler)
    Connecting the same handler multiple times has no effect.  You can
    disconnect a handler by calling ‘disconnect’ on the command:
        command_manager.foo_command.disconnect(handler)
    You can use ‘connect’ as a decorator to connect a multiline handler
    as soon as it is defined:
        @command_manager.foo_command.connect
        def foo_callback():
            ...

    Each command can be disabled.  When it is disabled, it will not call
    its connected handlers.  The command can be disabled by setting its
    ‘enabled’ property to False, and reënabled by setting it back to
    True.  You can register callbacks to be called when the ‘enabled’
    property changes:
        command_manager.foo_command.enabled_connect(handler)
    and disconnect them with enabled_disconnect. As above,
    enabled_connect can be used as a decorator, and repeated
    attempts to attach the same handler are ignored.  The handler is
    called with the new value of ‘enabled’ as its argument when
    ‘enabled’ changes and when the handler is first connected.
    """
    def __getattr__(self, name):
        command = _Command()
        setattr(self, name, command)
        return command


class _Command:
    def __init__(self):
        self.__callbacks = set()
        self.__enabled = True
        self.__enabled_callbacks = set()

    def connect(self, callback):
        self.__callbacks.add(callback)
        return callback

    def disconnect(self, callback):
        self.__callbacks.remove(callback)

    def __call__(self, *args, **kwargs):
        if self.__enabled:
            for callback in self.__callbacks:
                callback(*args, **kwargs)

    def enabled_connect(self, callback):
        self.__enabled_callbacks.add(callback)
        callback(self.__enabled)
        return callback

    def enabled_disconnect(self, callback):
        self.__enabled_callbacks.remove(callback)

    @property
    def enabled(self):
        return self.__enabled

    @enabled.setter
    def enabled(self, value):
        self.__enabled = value
        for callback in self.__enabled_callbacks:
            callback(value)