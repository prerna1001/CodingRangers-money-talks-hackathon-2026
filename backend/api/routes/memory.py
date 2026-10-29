"""GET/POST/PATCH/DELETE /api/memory -- backs the Memory Panel's
edit/delete/correct controls (plan section 15.2, 8.5).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth0_setup
from services.memory_store import MemoryStore

router = APIRouter()
_store = MemoryStore()


class MemoryCorrection(BaseModel):
    content: str


@router.get("/memory")
def list_memory(
    company_id: str,
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> list[dict]:
    return [m.model_dump() for m in _store.list_for_company(company_id, user_id=user_id)]


@router.patch("/memory/{memory_id}")
def correct_memory(
    memory_id: str,
    body: MemoryCorrection,
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> dict:
    try:
        memory = _store.user_correct(memory_id, body.content, user_id=user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
    return memory.model_dump()


@router.delete("/memory/{memory_id}")
def delete_memory(
    memory_id: str,
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> dict:
    if not _store.delete(memory_id, user_id=user_id):
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
    return {"deleted": memory_id}
