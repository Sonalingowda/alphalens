"""Server-side Clerk authentication for protected paper tracking actions."""

from dataclasses import dataclass

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import HTTPException, Request, status


@dataclass(frozen=True, slots=True)
class ClerkActor:
    """The only actor identity allowed into paper-tracking persistence."""

    user_id: str


class ClerkPaperTrackingAuthenticator:
    """Authenticate and authorize one configured Clerk development user."""

    def __init__(
        self,
        *,
        secret_key: str | None,
        authorized_parties: tuple[str, ...],
        authorized_user_id: str | None,
    ) -> None:
        self._secret_key = secret_key
        self._authorized_parties = authorized_parties
        self._authorized_user_id = authorized_user_id

    def authenticate(self, request: Request) -> ClerkActor:
        """Return the verified actor or fail closed without exposing credentials."""
        if not self._secret_key or not self._authorized_user_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Paper tracking authentication is not configured.",
            )
        try:
            clerk = Clerk(bearer_auth=self._secret_key)
            request_state = clerk.authenticate_request(
                request,
                AuthenticateRequestOptions(
                    secret_key=self._secret_key,
                    authorized_parties=list(self._authorized_parties),
                    accepts_token=["session_token"],
                ),
            )
        except Exception as error:  # noqa: BLE001 - SDK boundary must fail closed
            del error
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication could not be verified.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None
        if not request_state.is_authenticated or not request_state.payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication could not be verified.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = request_state.payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated actor identity is unavailable.",
            )
        if user_id != self._authorized_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The authenticated user is not authorized for paper tracking.",
            )
        return ClerkActor(user_id=user_id)
