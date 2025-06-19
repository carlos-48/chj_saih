class CHJSAIHError(Exception):
    """Base exception class for chj_saih specific errors."""
    pass

class APIError(CHJSAIHError):
    """Raised when there's an error communicating with the API."""
    pass

class DataParseError(CHJSAIHError):
    """Raised when there's an error parsing data from the API."""
    pass

class InvalidInputError(CHJSAIHError, ValueError):
    """Raised when invalid input is provided to a function."""
    pass
