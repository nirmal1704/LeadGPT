import logging
from pymongo import MongoClient

from config import settings

logger = logging.getLogger(__name__)

class _LazyMongoClient:
    def __init__(self):
        self._client = None
        self._db = None

    def _initialize(self):
        if self._client is None and settings.MONGO_URI:
            try:
                self._client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
                # Ensure connection is valid
                self._client.admin.command('ping')
                self._db = self._client.get_database("leadgpt")
                logger.info("MongoDB connection established.")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                self._client = None
                self._db = None

    @property
    def db(self):
        if self._db is None:
            self._initialize()
        return self._db

mongo_client = _LazyMongoClient()

def store_zipped_export(job_id: str, zipped_bytes: bytes) -> str | None:
    """Stores the zipped binary data in MongoDB and returns the document ID."""
    db = mongo_client.db
    if db is None:
        return None
        
    collection = db.exports_storage
    result = collection.insert_one({
        "job_id": job_id,
        "file_data": zipped_bytes,
        "content_type": "application/zip",
    })
    return str(result.inserted_id)

def get_zipped_export(doc_id: str) -> bytes | None:
    """Retrieves the zipped binary data from MongoDB using the document ID."""
    from bson.objectid import ObjectId
    db = mongo_client.db
    if db is None:
        return None
        
    try:
        doc = db.exports_storage.find_one({"_id": ObjectId(doc_id)})
        if doc and "file_data" in doc:
            return doc["file_data"]
    except Exception:
        pass
    return None
