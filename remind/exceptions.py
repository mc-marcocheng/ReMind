class ReMindError(Exception):
    """Base exception class for ReMind errors."""
    pass


class DatabaseOperationError(ReMindError):
    """Raised when a database operation fails."""
    pass


class UnsupportedTypeException(ReMindError):
    """Raised when an unsupported type is provided."""
    pass


class InvalidInputError(ReMindError):
    """Raised when invalid input is provided."""
    pass


class NotFoundError(ReMindError):
    """Raised when a requested resource is not found."""
    pass


class AuthenticationError(ReMindError):
    """Raised when there's an authentication problem."""
    pass


class ConfigurationError(ReMindError):
    """Raised when there's a configuration problem."""
    pass


class ExternalServiceError(ReMindError):
    """Raised when an external service (e.g., AI model) fails."""
    pass


class RateLimitError(ReMindError):
    """Raised when a rate limit is exceeded."""
    pass


class FileOperationError(ReMindError):
    """Raised when a file operation fails."""
    pass


class NetworkError(ReMindError):
    """Raised when a network operation fails."""
    pass


class NoTranscriptFound(ReMindError):
    """Raised when no transcript is found for a video."""
    pass
