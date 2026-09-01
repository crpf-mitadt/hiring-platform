class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermissionDenied(DomainError):
    status_code = 403


class AuthenticationRequired(DomainError):
    status_code = 401


class NotFound(DomainError):
    status_code = 404


class InvalidTransition(DomainError):
    status_code = 409


class StructuredDomainError(InvalidTransition):
    def __init__(self, message: str, *, code: str, issues: list[dict]):
        super().__init__(message)
        self.code = code
        self.issues = issues
