"""Modelos ORM del módulo Madrugue."""

from datetime import date

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RegistroMadrugue(Base):
    """Un registro de "madrugue" por usuario, guild y fecha."""

    __tablename__ = "registros"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora: Mapped[str] = mapped_column(String, nullable=False)
    puntos_base: Mapped[int] = mapped_column(Integer, nullable=False)
    multiplicador: Mapped[float] = mapped_column(Float, nullable=False)
    puntos_finales: Mapped[float] = mapped_column(Float, nullable=False)
