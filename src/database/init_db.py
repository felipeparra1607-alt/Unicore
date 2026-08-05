from src.database.connection import Base, engine
from src.database import models


def create_database() -> None:
    Base.metadata.create_all(bind=engine)
    print("Base de datos de UniCore creada correctamente")


if __name__ == "__main__":
    create_database()