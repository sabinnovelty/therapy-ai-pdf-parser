from pydantic import BaseModel

class ExportVisitsRequest(BaseModel):
    visits: list[int]