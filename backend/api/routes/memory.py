"""GET/POST/PATCH/DELETE /api/memory -- backs the Memory Panel's
edit/delete/correct controls (plan section 15.2, 8.5).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.memory_store import MemoryStore

router = APIRouter()
_store = MemoryStore()


class MemoryCorrection(BaseModel):
    content: str


@router.get("/memory")
def list_memory(company_id: str) -> list[dict]:
    return [m.model_dump() for m in _store.list_for_company(company_id)]


@router.patch("/memory/{memory_id}")
def correct_memory(memory_id: str, body: MemoryCorrection) -> dict:
    try:
        memory = _store.user_correct(memory_id, body.content)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
    return memory.model_dump()


@router.delete("/memory/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    _store.delete(memory_id)
    return {"deleted": memory_id}
