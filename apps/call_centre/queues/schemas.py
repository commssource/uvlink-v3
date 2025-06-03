from pydantic import BaseModel, Field
from typing import List, Optional

class QueueMember(BaseModel):
    extension: str
    interface: str
    hint: str
    penalty: Optional[int] = 0

class QueueConfig(BaseModel):
    name: str
    context: str = Field(..., description="Queue context name")
    cbcontext: str = Field(..., description="Callback context name")
    setinterfacevar: bool = True
    maxlen: int = 4
    timeout: int = 300
    joinempty: bool = True
    leavewhenempty: bool = False
    announce_holdtime: bool = True
    announce_position: bool = True
    announce_frequency: int = 30
    announce_round_seconds: int = 0
    members: List[QueueMember]
    strategy: str = "ringall"
    autofill: bool = True
    ringinuse: bool = False
    retry: int = 4
    wrapuptime: int = 4
    announce: str = Field(..., description="Announcement file path")

class QueueListResponse(BaseModel):
    items: List[QueueConfig]
    total: int
    page: int
    page_size: int
    total_pages: int 