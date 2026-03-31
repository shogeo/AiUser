class ModelCommandError(Exception):
    pass

class ParsingError(ModelCommandError):
    pass

class CommandNotFoundError(ModelCommandError):
    pass

class InvalidArgumentError(ModelCommandError):
    pass

class SystemCommandError(Exception):
    pass

class FileOperationError(SystemCommandError):
    pass
