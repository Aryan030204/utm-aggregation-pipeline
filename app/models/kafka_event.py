from pydantic import BaseModel, ConfigDict
from typing import Optional

class EtlCompletedEvent(BaseModel):
    eventType: str
    jobId: str
    completedAt: str
    recomputeDays: Optional[int] = 1

    model_config = ConfigDict(extra='ignore')

class UtmAggregateCompletedEvent(BaseModel):
    eventType: str
    brand: str
    jobId: str
    completedAt: str
    status: str

    model_config = ConfigDict(extra='ignore')

class UtmAggregateFailedEvent(BaseModel):
    eventType: str
    brand: str
    jobId: str
    completedAt: str
    status: str
    error: str

    model_config = ConfigDict(extra='ignore')
