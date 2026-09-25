"""Modelos ORM del módulo laHora (canal 420)."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import FECHA_HORA, Base


class RegistroLaHora(Base):
    """Un "420" dicho a tiempo: uno por usuario, guild, fecha y ventana.

    A diferencia de Madrugue, hay varias ventanas por día (04:20 y 16:20
    por defecto), así que la unicidad incluye la ``ventana``.
    """

    __tablename__ = "lahora_registros"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", "fecha", "ventana"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    # Hora de apertura de la ventana, en texto HH:MM ("04:20", "16:20").
    ventana: Mapped[str] = mapped_column(String, nullable=False)
    # Momento exacto del mensaje, con zona horaria.
    momento: Mapped[datetime] = mapped_column(FECHA_HORA, nullable=False)
    # Segundos transcurridos desde que abrió la ventana.
    segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    # Orden de llegada dentro de la ventana (1 = el primero).
    posicion: Mapped[int] = mapped_column(Integer, nullable=False)
    puntos_base: Mapped[int] = mapped_column(Integer, nullable=False)
    multiplicador: Mapped[float] = mapped_column(Float, nullable=False)
    bonus_posicion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    puntos_finales: Mapped[float] = mapped_column(Float, nullable=False)
    mensaje_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
