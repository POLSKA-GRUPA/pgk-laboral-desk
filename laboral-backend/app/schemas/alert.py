from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    alert_type: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    due_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    worker_name: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=100)
    severity: str = Field(default="info", pattern="^(info|warning|critical)$")


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    alert_type: str
    title: str
    description: str
    due_date: str
    worker_name: str
    category: str
    severity: str
    status: str
    created_at: Optional[datetime] = None
