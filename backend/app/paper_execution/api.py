"""Authenticated API boundary for human paper-track selection."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.paper_execution.auth import ClerkActor, ClerkPaperTrackingAuthenticator
from app.paper_execution.selection import (
    PaperTrackingSelectionError,
    PaperTrackingSelectionService,
)


class PaperTrackingConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str = Field(min_length=1)
    opportunity_version_id: str = Field(min_length=1)
    confirmed_scenario_hash: str = Field(min_length=64, max_length=64)


class PaperTrackingSelectionResponse(BaseModel):
    execution_id: str
    position_id: str
    opportunity_id: str
    opportunity_version_id: str
    status: str
    selected_at: datetime
    actor_id: str


class PaperTrackingConfirmationResponse(BaseModel):
    opportunity_id: str
    opportunity_version_id: str
    confirmed_scenario_hash: str


def create_paper_tracking_router(
    *,
    selection_service: PaperTrackingSelectionService,
    authenticator: ClerkPaperTrackingAuthenticator,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/paper-tracking", tags=["paper-tracking"])

    def actor(request: Request) -> ClerkActor:
        return authenticator.authenticate(request)

    @router.get(
        "/confirmation",
        response_model=PaperTrackingConfirmationResponse,
    )
    async def get_confirmation(
        opportunity_id: str,
        opportunity_version_id: str,
        _: ClerkActor = Depends(actor),
    ) -> PaperTrackingConfirmationResponse:
        try:
            confirmation = await selection_service.confirmation_by_reference(
                opportunity_id=opportunity_id,
                opportunity_version_id=opportunity_version_id,
            )
        except PaperTrackingSelectionError as error:
            raise _selection_error(error) from None
        return PaperTrackingConfirmationResponse(**confirmation)

    @router.post(
        "/selections",
        response_model=PaperTrackingSelectionResponse,
        status_code=status.HTTP_200_OK,
    )
    async def select(
        request: PaperTrackingConfirmationRequest,
        actor_identity: ClerkActor = Depends(actor),
    ) -> PaperTrackingSelectionResponse:
        try:
            selection = await selection_service.select_by_reference(
                opportunity_id=request.opportunity_id,
                opportunity_version_id=request.opportunity_version_id,
                actor_id=actor_identity.user_id,
                confirmed_scenario_hash=request.confirmed_scenario_hash,
            )
        except PaperTrackingSelectionError as error:
            raise _selection_error(error) from None
        return PaperTrackingSelectionResponse(
            execution_id=selection.execution.execution_id,
            position_id=selection.position.position_id,
            opportunity_id=selection.opportunity_id,
            opportunity_version_id=selection.opportunity_version_id,
            status=selection.execution.state.value,
            selected_at=selection.selected_at,
            actor_id=selection.selection_event.actor_id or actor_identity.user_id,
        )

    return router


def _selection_error(error: PaperTrackingSelectionError):
    from fastapi import HTTPException

    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
