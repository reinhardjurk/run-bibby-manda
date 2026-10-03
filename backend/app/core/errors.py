"""Domain errors mapped to HTTP responses with German `detail` messages."""

from __future__ import annotations

from fastapi import HTTPException, status


class NotFound(HTTPException):
    def __init__(self, detail: str = "Nicht gefunden.") -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class Conflict(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_409_CONFLICT, detail)


class BadRequest(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail)


class Forbidden(HTTPException):
    def __init__(self, detail: str = "Keine Berechtigung für diese Aktion.") -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, detail)


class Unauthorized(HTTPException):
    def __init__(self, detail: str = "Nicht angemeldet.") -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class TooManyRequests(HTTPException):
    def __init__(self, detail: str = "Zu viele Anfragen. Bitte später erneut versuchen.") -> None:
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, detail)


class ServiceUnavailable(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, detail)
