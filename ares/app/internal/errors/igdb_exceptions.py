from app.utils.loggers import base_logger as logger

class IGDBInvalidReponseCode(Exception):
    """Exception raised when IGDB API returns an invalid response code.
    
    Attributes:
        code -- response code
        message -- explanation of the error
    """
    
    def __init__(self, code, message = "Invalid response code from IGDB API"):
        self.code = code
        self.message = message
        super().__init__(self.message)
        
class IGDBInvalidReponse(Exception):
    """Exception raised when IGDB API returns an invalid response.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, message = "Invalid response from IGDB API"):
        self.message = message
        super().__init__(self.message)