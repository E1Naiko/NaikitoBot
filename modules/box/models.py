"""Modelos ORM del módulo Box."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from config import (
    BOX_CANSANCIO_INICIAL,
    BOX_DANO_INICIAL,
    BOX_DANO_MAXIMO,
    BOX_DEFENSA_INICIAL,
    BOX_DEFENSA_MAXIMO,
    BOX_VIDA_INICIAL,
)
from core.database import Base, FECHA_HORA


class BoxUsuario(Base):
    """Progreso general de un boxeador (experiencia, dinero, lesiones)."""

    __tablename__ = "box_usuarios"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    experiencia: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    dinero: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    probabilidad_lesion: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default="0"
    )
    lesionado_hasta: Mapped[datetime | None] = mapped_column(
        FECHA_HORA
    )


class BoxAccion(Base):
    """Una acción temporizada de un boxeador (incluido el descanso)."""

    __tablename__ = "box_acciones"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    iniciado_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    finaliza_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    recompensa: Mapped[int] = mapped_column(Integer, nullable=False)
    dinero_recompensa: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class BoxDesafio(Base):
    """Un desafío pendiente entre dos boxeadores."""

    __tablename__ = "box_desafios"
    __table_args__ = (
        UniqueConstraint("guild_id", "retador_id", "contrincante_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retador_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contrincante_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expira_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    tipo: Mapped[str] = mapped_column(
        String, nullable=False, default="SPARRING", server_default="SPARRING"
    )
    canal_id: Mapped[int | None] = mapped_column(BigInteger)
    mensaje_id: Mapped[int | None] = mapped_column(BigInteger)


class BoxMejora(Base):
    """Nivel de una mejora comprada por un boxeador."""

    __tablename__ = "box_mejoras"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mejora: Mapped[str] = mapped_column(String, primary_key=True)
    nivel: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class BoxDesafioHistorial(Base):
    """Historial de desafíos ya resueltos."""

    __tablename__ = "box_desafios_historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    retador_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contrincante_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ganador_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )


class BoxEquipo(Base):
    """Estadísticas de combate y equipamiento de un boxeador."""

    __tablename__ = "box_equipo"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vida: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_VIDA_INICIAL, server_default=str(BOX_VIDA_INICIAL)
    )
    vida_maxima: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_VIDA_INICIAL, server_default=str(BOX_VIDA_INICIAL)
    )
    dano: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_DANO_INICIAL, server_default=str(BOX_DANO_INICIAL)
    )
    dano_maximo: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_DANO_MAXIMO, server_default=str(BOX_DANO_MAXIMO)
    )
    defensa: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_DEFENSA_INICIAL, server_default=str(BOX_DEFENSA_INICIAL)
    )
    defensa_maxima: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_DEFENSA_MAXIMO, server_default=str(BOX_DEFENSA_MAXIMO)
    )
    cansancio: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_CANSANCIO_INICIAL, server_default=str(BOX_CANSANCIO_INICIAL)
    )
    cansancio_maximo: Mapped[int] = mapped_column(
        Integer, nullable=False, default=BOX_CANSANCIO_INICIAL, server_default=str(BOX_CANSANCIO_INICIAL)
    )
    puntos_habilidad: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    casco: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    guantes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    protector_bucal: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    short: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    botas: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class BoxCombate(Base):
    """Un combate en vivo (narrado) o ya terminado."""

    __tablename__ = "box_combates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    canal_id: Mapped[int | None] = mapped_column(BigInteger)
    modo: Mapped[str] = mapped_column(String, nullable=False)
    retador_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contrincante_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    semilla: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    iniciado_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    latido_segundos: Mapped[int] = mapped_column(Integer, nullable=False)
    latidos_totales: Mapped[int] = mapped_column(Integer, nullable=False)
    fin_narracion_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    estado: Mapped[str] = mapped_column(
        String, nullable=False, default="VIVO", server_default="VIVO"
    )
    mensaje_id: Mapped[int | None] = mapped_column(BigInteger)
    resumen: Mapped[str | None] = mapped_column(Text)
    terminado_en: Mapped[datetime | None] = mapped_column(FECHA_HORA)


class BoxCombateAsalto(Base):
    """Asaltos ya publicados de un combate en vivo."""

    __tablename__ = "box_combates_asaltos"

    combate_id: Mapped[int] = mapped_column(
        ForeignKey("box_combates.id"),
        primary_key=True,
    )
    asalto: Mapped[int] = mapped_column(Integer, primary_key=True)
    mensaje_id: Mapped[int | None] = mapped_column(BigInteger)
    publicado_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )


class BoxConfigGuild(Base):
    """Ajustes de la velada que decide cada servidor."""

    __tablename__ = "box_config_guild"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # NULL = nadie decidió todavía; 0/1 = decisión explícita del servidor.
    canticos: Mapped[int | None] = mapped_column(Integer)
    actualizado_en: Mapped[datetime | None] = mapped_column(FECHA_HORA)
    actualizado_por: Mapped[int | None] = mapped_column(BigInteger)


class BoxSponsor(Base):
    """Un sponsor activo de un boxeador."""

    __tablename__ = "box_sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    obtenido_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(
        FECHA_HORA, nullable=False
    )
    ultimo_pago: Mapped[datetime | None] = mapped_column(FECHA_HORA)
    ultimo_tratamiento: Mapped[datetime | None] = mapped_column(
        FECHA_HORA
    )
