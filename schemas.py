from pydantic import BaseModel
from typing import List

class DeleteRequest(BaseModel):
    ids: List[int]

class RenameRequest(BaseModel):
    url: str
    filename: str

class ValidateRequest(BaseModel):
    url: str
