from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

import asyncio

async def init_db():
    retries = 5
    while retries > 0:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            print("Database initialized successfully.")
            return
        except Exception as e:
            retries -= 1
            print(f"Database connection failed. Retrying... ({retries} attempts left)")
            print(f"Error: {e}")
            await asyncio.sleep(2)
    
    raise Exception("Could not connect to the database after multiple attempts.")

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
