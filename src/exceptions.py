class ModelVisibleError(Exception):
    """Base class for errors that should be visible to the AI model."""
    pass


class ParsingError(ModelVisibleError):
    """Error during command parsing."""
    pass


class MethodNotFoundError(ModelVisibleError):
    """Error when a method is not found on the client."""
    pass


class ArgumentError(ModelVisibleError):
    """Error due to invalid arguments for a method."""
    pass


class ExecutionError(ModelVisibleError):
    """Error during command execution in Telegram's API."""
    pass
