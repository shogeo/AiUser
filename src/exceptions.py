class ParsingError(Exception):
    """Error during command parsing."""
    pass


class MethodNotFoundError(Exception):
    """Error when a method is not found on the client."""
    pass


class ArgumentError(Exception):
    """Error due to invalid arguments for a method."""
    pass


class ExecutionError(Exception):
    """Error during command execution in Telegram's API."""
    pass
