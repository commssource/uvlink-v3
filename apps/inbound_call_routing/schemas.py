from pydantic import BaseModel
from typing import Optional, List

class InboundCallRoutingBase(BaseModel):
    did_number: str
    client_name: str
    destination: str
    destination_value: str
    status: bool = True

class InboundCallRoutingCreate(InboundCallRoutingBase):
    pass

class InboundCallRoutingUpdate(BaseModel):
    did_number: Optional[str] = None
    client_name: Optional[str] = None
    destination: Optional[str] = None
    destination_value: Optional[str] = None
    status: Optional[bool] = None

class InboundCallRouting(InboundCallRoutingBase):
    id: int

    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    items: List[InboundCallRouting]
    total: int
    page: int
    size: int
    pages: int 