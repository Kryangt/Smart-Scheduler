import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv("backend/.env")

DATABASE_URL = os.getenv("DATABASE_URL")

#engine creates a direct connection to the database so the sql queries are able to sent to db
engine = create_engine(
    DATABASE_URL,
    echo = True #echo = true enables us to see the printed SQL statement
) 

#SessionLocal creats session object, a session can track ORM objects (maps between a row in a table in db and an object of a class in Python)
#also a session can general SQL
#use engine internally to transmit commands
SessionLocal = sessionmaker (
    bind = engine,
    autoflush= False,
    autocommit = False
)
def get_connection():
    return psycopg2.connect(DATABASE_URL)
