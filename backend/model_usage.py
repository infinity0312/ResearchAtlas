"""Public, credential-free usage and budget API."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .model_runtime import get_budget, set_budget, usage_summary

router = APIRouter(prefix='/api/model-usage', tags=['model-usage'])


class BudgetInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    daily_tokens: int | None = Field(default=None, gt=0)
    task_tokens: int | None = Field(default=None, gt=0)
    task_calls: int | None = Field(default=None, gt=0)


@router.get('')
def summary(day: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    try:
        return usage_summary(day=day, limit=limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get('/budget')
def budget():
    return get_budget()


@router.put('/budget')
def configure_budget(data: BudgetInput):
    # Omitted fields preserve earlier caps; an explicit null disables that cap.
    return set_budget(data.model_dump(exclude_unset=True))
