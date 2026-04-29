from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    occupation: Optional[str] = None
    goals: Optional[list[str]] = None


class HealthMetric(BaseModel):
    metric: str
    value: float
    unit: Optional[str] = ""
    notes: Optional[str] = ""
