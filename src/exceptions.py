# Base class for errors that should be reported back to the model
class ModelCommandError(Exception):
    """Base exception for errors caused by the model's command generation."""
    pass

class ParsingError(ModelCommandError):
    """Raised when a command string from the model is syntactically incorrect."""
    pass

class CommandNotFoundError(ModelCommandError):
    """Raised when the model tries to call a non-existent command."""
    pass

class InvalidArgumentError(ModelCommandError):
    """Raised when the model provides invalid arguments to a command."""
    pass

# Base class for internal system errors that should NOT be reported to the model
class SystemCommandError(Exception):
    """Base exception for internal errors during command execution."""
    pass

class FileOperationError(SystemCommandError):
    """Raised for errors during file download or upload."""
    pass
