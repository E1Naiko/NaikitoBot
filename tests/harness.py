"""Dobles de prueba para ``discord.Interaction``.

Permiten ejecutar los comandos de Box de punta a punta sin conectar a Discord:
registran cada respuesta enviada para poder afirmar sobre ellas.
"""

from dataclasses import dataclass, field

from discord.utils import MISSING


class RespuestaFalsa:
    """Doble de ``interaction.response``."""

    def __init__(self, registro):
        self._registro = registro
        self.done = False

    def is_done(self):
        """Igual que en discord.py: True una vez respondida o diferida."""

        return self.done

    @staticmethod
    def _validar_view(kwargs):
        """Reproduce el contrato de ``view`` de discord.py.

        ``send_message``/``followup.send`` distinguen "sin vista" con el
        centinela ``MISSING``; si reciben ``view=None`` la librería llama a
        ``view.is_finished()`` sobre ``None`` y revienta con
        ``AttributeError``. Validar esto aquí hace que las pruebas detecten
        ese error de integración (``edit_message`` sí admite ``None``).
        """

        view = kwargs.get("view", MISSING)
        if view is not MISSING:
            view.is_finished()

    async def send_message(self, content=None, **kwargs):
        self._validar_view(kwargs)
        mensaje = _Mensaje(content, kwargs)
        self._registro.append(mensaje)
        self.done = True
        return mensaje

    async def send(self, content=None, **kwargs):
        """Equivalente de ``followup.send`` sobre el mismo registro."""

        self._validar_view(kwargs)
        mensaje = _Mensaje(content, kwargs)
        self._registro.append(mensaje)
        return mensaje

    async def edit_message(self, content=None, **kwargs):
        # discord.py revienta con ``InteractionResponded`` si la interacción
        # ya fue respondida (por ejemplo, después de un ``defer``): se
        # reproduce para detectar ese error de integración.
        if self.done:
            raise RuntimeError(
                "la interacción ya fue respondida (InteractionResponded)"
            )
        self._registro.append(_Mensaje(content, kwargs))

    async def defer(self, **kwargs):
        self._registro.append(_Mensaje(None, kwargs))
        self.done = True

    async def edit_original_response(self, content=None, **kwargs):
        self._registro.append(_Mensaje(content, kwargs))


class MensajeFalso:
    def __init__(self):
        self.id = 1

    async def edit(self, *args, **kwargs):
        return None


class _Respuesta404:
    """Respuesta HTTP mínima para construir ``discord.NotFound``.

    ``discord.py`` lee ``response.status`` al armar la excepción, así que
    ``None`` no sirve: reventaría con ``AttributeError`` en vez de
    ``NotFound`` y la prueba no ejercitaría la rama que quiere ejercitar.
    """

    status = 404
    reason = "Not Found"


def _no_encontrado(mensaje="Not Found"):
    import discord

    return discord.NotFound(_Respuesta404(), mensaje)


def prohibido(mensaje="Missing Permissions"):
    """``discord.Forbidden`` lista para hacer fallar un ``send`` de prueba."""

    import discord

    return discord.Forbidden(_RespuestaProhibida(), mensaje)


class CanalFalso:
    """Canal del servidor: lo que se publica fuera de la interacción.

    Las respuestas de una interacción viajan atadas a quien la ejecutó (y si
    el comando difirió efímero, solo las ve esa persona). Lo que tiene que
    llegar a todo el canal —la tarjeta de un desafío, por ejemplo— sale por
    acá.
    """

    def __init__(self, canal_id=77):
        self.id = canal_id
        self.mensajes: list = []

    async def send(self, content=None, **kwargs):
        # ``abc.Messageable.send`` distingue "sin vista" con el centinela
        # MISSING: pasar ``view=None`` revienta con TypeError en discord.py.
        if kwargs.get("view", MISSING) is None:
            raise TypeError("view must not be None")

        mensaje = _Mensaje(content, kwargs, id=len(self.mensajes) + 1)
        self.mensajes.append(mensaje)
        return mensaje

    async def fetch_message(self, mensaje_id):
        for mensaje in self.mensajes:
            if mensaje.id == mensaje_id:
                return mensaje

        raise _no_encontrado()

    @property
    def ultimo(self):
        return self.mensajes[-1] if self.mensajes else None


class GuildFalso:
    def __init__(
        self,
        guild_id=1,
        miembros=None,
        nombre="Servidor",
        canales=None,
    ):
        self.id = guild_id
        self.name = nombre
        self._miembros = miembros or {}
        self._canales = canales or {}

    def get_member(self, user_id):
        return self._miembros.get(user_id)

    def get_channel(self, canal_id):
        return self._canales.get(canal_id)

    @property
    def members(self):
        return list(self._miembros.values())

    async def query_members(self, query=None, limit=100):
        return []


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

    async def send(self, content=None, **kwargs):
        if not self.dm_abierto:
            import discord

            raise discord.Forbidden(
                _RespuestaProhibida(),
                "No puedo enviarte mensajes directos.",
            )
        embed = kwargs.get("embed")
        if embed is not None:
            partes = []
            if embed.title:
                partes.append(str(embed.title))
            if embed.description:
                partes.append(str(embed.description))
            partes.extend(
                f"{campo.name}: {campo.value}"
                for campo in embed.fields
            )
            self.mensajes_directos.append("\n".join(partes))
        else:
            self.mensajes_directos.append(content or "")
        return MensajeFalso()


@dataclass
class _Mensaje:
    contenido: str | None
    kwargs: dict = field(default_factory=dict)
    id: int = 1
    ediciones: int = 0

    @property
    def texto(self):
        """Texto plano equivalente a la respuesta, incluidos los embeds.

        El contenido y el embed se concatenan: un mensaje puede llevar las dos
        cosas (la tarjeta de un desafío menciona en el contenido, porque dentro
        de un embed la mención no notifica a nadie).
        """

        partes = []

        if self.contenido:
            partes.append(str(self.contenido))

        embed = self.kwargs.get("embed")
        if embed is not None:
            if embed.title:
                partes.append(str(embed.title))
            if embed.description:
                partes.append(str(embed.description))
            partes.extend(
                f"{campo.name}: {campo.value}"
                for campo in embed.fields
            )
            if embed.footer and embed.footer.text:
                partes.append(str(embed.footer.text))

        return "\n".join(partes)

    @property
    def efimero(self):
        return bool(self.kwargs.get("ephemeral"))

    @property
    def embed(self):
        return self.kwargs.get("embed")

    @property
    def view(self):
        return self.kwargs.get("view")

    async def edit(self, *args, **kwargs):
        """Edit mínimo que registra el cambio, para poder afirmar sobre él.

        A diferencia de ``send``, ``Message.edit`` sí admite ``view=None``:
        es cómo se quitan los botones de una tarjeta.
        """

        self.ediciones += 1

        if kwargs.get("embed") is not None:
            self.kwargs["embed"] = kwargs["embed"]
        if "view" in kwargs:
            self.kwargs["view"] = kwargs["view"]

        return self


class InteraccionFalsa:
    """Doble mínimo de ``discord.Interaction`` suficiente para Box."""

    def __init__(
        self,
        guild_id=1,
        user_id=42,
        nombre="Tester",
        en_servidor=True,
        canal=None,
        canal_obj=None,
    ):
        self.channel_id = canal if canal is not None else (guild_id if en_servidor else None)
        # El canal público va separado de las respuestas de la interacción:
        # es la diferencia entre "lo ve el desafiado" y "lo ve solo el que
        # ejecutó el comando". ``canal_obj`` permite que varias interacciones
        # (y el bot) compartan el mismo canal, como pasa en el servidor.
        if canal_obj is not None:
            self.channel = canal_obj
        else:
            self.channel = CanalFalso(self.channel_id) if en_servidor else None
        self.guild = (
            GuildFalso(guild_id, canales={self.channel_id: self.channel})
            if en_servidor
            else None
        )
        self.user = UsuarioFalso(user_id, nombre)
        self.respuestas = []
        self.response = RespuestaFalsa(self.respuestas)
        self.followup = RespuestaFalsa(self.respuestas)
        # El mensaje que dispara la interacción (componentes): las views lo
        # editan directo (``interaction.message.edit``) una vez diferida.
        self.message = MensajeFalso()

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
