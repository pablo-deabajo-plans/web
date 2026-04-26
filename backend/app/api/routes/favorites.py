from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.dependencies import get_favorites_service
from backend.app.schemas.favorites import FavoriteCreateRequest, FavoriteListResponse
from backend.app.services.favorites import FavoritesService


router = APIRouter()


@router.get("", response_model=FavoriteListResponse)
def get_favorites(
    service: Annotated[FavoritesService, Depends(get_favorites_service)],
) -> FavoriteListResponse:
    return FavoriteListResponse.model_validate(service.list_payload())


@router.post("", response_model=FavoriteListResponse)
def create_favorite(
    payload: FavoriteCreateRequest,
    service: Annotated[FavoritesService, Depends(get_favorites_service)],
) -> FavoriteListResponse:
    try:
        return FavoriteListResponse.model_validate(service.create(payload.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("", response_model=FavoriteListResponse)
def clear_favorites(
    service: Annotated[FavoritesService, Depends(get_favorites_service)],
) -> FavoriteListResponse:
    return FavoriteListResponse.model_validate(service.clear())


@router.delete("/{favorite_id}", response_model=FavoriteListResponse)
def delete_favorite(
    favorite_id: str,
    service: Annotated[FavoritesService, Depends(get_favorites_service)],
) -> FavoriteListResponse:
    payload = service.delete(favorite_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return FavoriteListResponse.model_validate(payload)
