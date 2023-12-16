class InvalidBody(Exception):
    """Exception raised when a request body is invalid.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, message = "Invalid request body"):
        self.message = message
        super().__init__(self.message)
        
class InvalidToken(Exception):
    """Exception raised when a token is invalid.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, message = "Invalid token"):
        self.message = message
        super().__init__(self.message)
        
class ObjectNotFound(Exception):
    """Exception raised when an object is not found.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, object_name):
        self.message = f"{object_name} not found"
        super().__init__(self.message)
        
class GenericError(Exception):
    """Exception raised when an unknown error occurs.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, message = "Unknown error"):
        self.message = message
        super().__init__(self.message)