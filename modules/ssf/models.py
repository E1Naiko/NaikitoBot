"""Modelos ORM del módulo SeptSinFP."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, FECHA_HORA


class SsfDesafio(Base):
    """Un desafío SeptSinFP (puede haber varios históricos por guild)."""

    __tablename__ = "ssf_desafios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    canal_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Se mantiene como entero 0/1 (como en el esquema original) para que
    # las comparaciones existentes sigan funcionando igual en ambos motores.
    activo: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class SsfParticipante(Base):
    """Un usuario inscripto en un desafío SSF."""

    __tablename__ = "ssf_participantes"
    __table_args__ = (
        UniqueConstraint("desafio_id", "user_id"),
    )

    desafio_id: Mapped[int] = mapped_column(
        ForeignKey("ssf_desafios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(
        FECHA_HORA,
        nullable=False,
    )
    eliminado: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Guarda solo la fecha (como en el esquema original, que almacenaba
    # el ISO de la fecha del día perdido).
    fecha_eliminacion: Mapped[date | None] = mapped_column(Date)
    racha_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mejor_racha: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class SsfRegistro(Base):
    """Supervivencia diaria de un participante."""

    __tablename__ = "ssf_registros"
    __table_args__ = (
        UniqueConstraint("desafio_id", "user_id", "fecha"),
    )

    desafio_id: Mapped[int] = mapped_column(
        ForeignKey("ssf_desafios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    hora: Mapped[str] = mapped_column(String, nullable=False)


class SsfRevision(Base):
    """Última fecha procesada por la revisión automática de cada desafío."""

    __tablename__ = "ssf_revisiones"

    desafio_id: Mapped[int] = mapped_column(
        ForeignKey("ssf_desafios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ultima_fecha: Mapped[date] = mapped_column(Date, nullable=False)
