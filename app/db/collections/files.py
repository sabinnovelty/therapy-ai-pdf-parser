from typing import TypedDict, NotRequired

from pymongo.asynchronous.collection import AsyncCollection

from app.db.db import database


class FileSchema(TypedDict):
    name: str
    status: str
    extension: NotRequired[str]
    result: NotRequired[dict]


COLLECTION_NAME = "files"
files_collection: AsyncCollection = database[COLLECTION_NAME]
