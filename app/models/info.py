from typing import List, Optional

from pydantic import BaseModel

# Import data types
from app.models.user import PublicContact


class InfoModel(BaseModel):
    name: Optional[str] = "PlinkOnboard"
    description: Optional[str] = None
    credits: List[PublicContact]
