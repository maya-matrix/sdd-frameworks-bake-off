class DomainError(Exception):
    """Base for rule violations the HTTP layer maps to a status code."""


class NotFound(DomainError):
    pass


class Invalid(DomainError):
    pass


class Conflict(DomainError):
    pass
