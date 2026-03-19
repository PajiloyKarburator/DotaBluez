from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.cfg import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)