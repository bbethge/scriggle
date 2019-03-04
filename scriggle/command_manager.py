class _Command:
    def __init__(self):
        self.__callbacks = set()

    def connect(self, callback):
        self.__callbacks.add(callback)
        return callback

    def disconnect(self, callback):
        self.__callbacks.remove(callback)

    def __call__(self, *args, **kwargs):
        for callback in self.__callbacks:
            callback(*args, **kwargs)


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
    """
    def __getattr__(self, name):
        command = _Command()
        setattr(self, name, command)
        return command