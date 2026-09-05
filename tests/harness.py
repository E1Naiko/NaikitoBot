"""Dobles de prueba para ``discord.Interaction``.

Permiten ejecutar los comandos de Box de punta a punta sin conectar a Discord:
registran cada respuesta enviada para poder afirmar sobre ellas.
"""

from dataclasses import dataclass, field


class RespuestaFalsa:
    """Doble de ``interaction.response``."""

    def __init__(self, registro):
        self._registro = registro

    async def send_message(self, content=None, **kwargs):
        self._registro.append(_Mensaje(content, kwargs))

    async def edit_message(self, content=None, **kwargs):
        self._registro.append(_Mensaje(content, kwargs))

    async def defer(self, **kwargs):
        self._registro.append(_Mensaje(None, kwargs))

    async def edit_original_response(self, content=None, **kwargs):
        self._registro.append(_Mensaje(content, kwargs))


class MensajeFalso:
    def __init__(self):
        self.id = 1

    async def edit(self, *args, **kwargs):
        return None


class GuildFalso:
    def __init__(self, guild_id=1, miembros=None):
        self.id = guild_id
        self._miembros = miembros or {}

    def get_member(self, user_id):
        return self._miembros.get(user_id)


class _RespuestaProhibida:
    """Respuesta HTTP mínima para construir ``discord.Forbidden``.

    ``discord.py`` lee ``response.status`` al crear la excepción, así que
    ``None`` no sirve: revienta con ``AttributeError`` en vez de ``Forbidden``.
    """

    status = 403
    reason = "Forbidden"


class UsuarioFalso:
    def __init__(self, user_id=42, nombre="Tester"):
        self.id = user_id
        self.display_name = nombre
        self.mention = f"<@{user_id}>"
        self.dm_abierto = True
        self.mensajes_directos = []

    async def send(self, content):
        if not self.dm_abierto:
            import discord

            raise discord.Forbidden(
                _RespuestaProhibida(),
                "No puedo enviarte mensajes directos.",
            )
        self.mensajes_directos.append(content)
        return MensajeFalso()


@dataclass
class _Mensaje:
    contenido: str | None
    kwargs: dict = field(default_factory=dict)

    @property
    def texto(self):
        return self.contenido or ""

    @property
    def efimero(self):
        return bool(self.kwargs.get("ephemeral"))


class InteraccionFalsa:
    """Doble mínimo de ``discord.Interaction`` suficiente para Box."""

    def __init__(self, guild_id=1, user_id=42, nombre="Tester", en_servidor=True):
        self.guild = GuildFalso(guild_id) if en_servidor else None
        self.user = UsuarioFalso(user_id, nombre)
        self.respuestas = []
        self.response = RespuestaFalsa(self.respuestas)

    async def original_response(self):
        return MensajeFalso()

    @property
    def texto(self):
        """Texto de la última respuesta enviada."""

        return self.respuestas[-1].texto if self.respuestas else ""

    @property
    def cantidad_respuestas(self):
        return len(self.respuestas)


class Choice:
    """Doble de ``discord.app_commands.Choice``."""

    def __init__(self, value):
        self.value = value


def construir_cog(clase, bot=None):
    """Instancia un cog sin arrancar sus tareas periódicas."""

    import discord
    from discord.ext import commands

    if bot is None:
        bot = commands.Bot(
            command_prefix="$!",
            intents=discord.Intents.default(),
        )

    cog = clase.__new__(clase)
    cog.bot = bot
    return cog
