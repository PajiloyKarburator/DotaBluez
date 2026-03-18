# Минимально необходимое в repository.py
class Database:
    def __init__(self, dsn: str):
        ...
    async def connect(self):
        ...

class ProfileRepository:
    def __init__(self, db: Database):
        ...