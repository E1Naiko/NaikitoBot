"""Pruebas de los comandos administrativos ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

import pytest

from tests.harness import Choice, InteraccionFalsa, construir_cog

GUILD = 1
ADMIN = 1
USUARIO = 42

ARBOL_ESPERADO = {
    "admin|Group",
    "admin box|Group",
    "admin box cancelar|Command",
    "admin box curar|Command",
    "admin box dar_dinero|Command",
    "admin box dar_exp|Command",
    "admin box dar_sponsor|Command",
    "admin box info|Command",
    "admin box probabilidad|Command",
    "admin box quitar_sponsor|Command",
    "admin box reset|Command",
    "admin box sponsors|Command",
    "admin fileexecute|Command",
    "admin info|Command",
    "admin manualadd|Command",
    "admin resetdia|Command",
    "admin resettotal|Command",
    "admin resetusuario|Command",
    "admin ssf|Group",
    "admin ssf iniciar|Command",
    "admin ssf revivir|Command",
    "admin stats|Command",
    "admin top|Command",
}


@pytest.fixture
def admin_ids(monkeypatch):
    """Deja un único administrador determinístico, sin depender del .env."""

    monkeypatch.setattr(
        "core.permissions.ADMIN_USER_IDS",
        {ADMIN},
    )


@pytest.fixture
def cog(base_datos_limpia, admin_ids):
    from commands.admin.cog import Admin

    return construir_cog(Admin)


@pytest.fixture
def cog_en_arbol(base_datos_limpia, admin_ids):
    """Cog registrado en un árbol real (lo necesita fileexecute)."""

    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.admin")

    ejecutar(cargar())

    return bot.get_cog("Admin")


def ejecutar(coro):
    import asyncio

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        coro
    )


def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return ejecutar(metodo(cog, interaccion, *args))


class AdjuntoFalso:
    """Doble mínimo de ``discord.Attachment`` para fileexecute."""

    def __init__(self, contenido="", nombre="comandos.txt"):
        self.filename = nombre
        self._contenido = contenido.encode("utf-8")
        self.size = len(self._contenido)

    async def read(self):
        return self._contenido


def interaccion_admin(en_servidor=True):
    return InteraccionFalsa(
        GUILD,
        ADMIN,
        nombre="Admin",
        en_servidor=en_servidor,
    )


# ============================================================
# REGISTRO EN EL ÁRBOL
# ============================================================

def test_extension_registra_el_arbol_completo(base_datos_limpia):
    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.admin")

    ejecutar(cargar())

    nombres = {
        f"{comando.qualified_name}|{type(comando).__name__}"
        for comando in bot.tree.walk_commands()
    }

    assert nombres == ARBOL_ESPERADO


# ============================================================
# PERMISOS Y SERVIDOR
# ============================================================

COMANDOS_CON_ARGUMENTO_FALSO = [
    ("box_info", (None,)),
    ("box_dar_dinero", (None, 5)),
    ("box_sponsors", (None,)),
    ("box_dar_exp", (None, 5)),
    ("box_curar", (None,)),
    ("box_probabilidad", (None, 1.0)),
    ("box_cancelar", (None,)),
    ("box_dar_sponsor", (None, Choice("redes"))),
    ("box_quitar_sponsor", (None, 1)),
    ("box_reset", (None,)),
    ("fileexecute", (None,)),
    ("info", ()),
    ("stats", ()),
    ("top", ()),
    ("resetdia", (None, "2026-09-01")),
    ("resetusuario", (None,)),
    ("resettotal", (Choice("SI"),)),
    ("ssf_revivir", (None, "2026-09-01")),
    ("ssf_iniciar", (None,)),
    ("manualadd", (None, "2026-09-01", "05:45")),
]


@pytest.mark.parametrize(
    "comando, argumentos",
    COMANDOS_CON_ARGUMENTO_FALSO,
)
def test_comandos_rechazan_a_no_administradores(cog, comando, argumentos):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    llamar(cog, comando, interaccion, *argumentos)

    assert interaccion.cantidad_respuestas == 1
    assert "No tienes permisos" in interaccion.texto


@pytest.mark.parametrize(
    "comando, argumentos",
    [
        ("box_info", (None,)),
        ("stats", ()),
        ("ssf_revivir", (None, "2026-09-01")),
        ("manualadd", (None, "2026-09-01", "05:45")),
    ],
)
def test_comandos_rechazan_mensajes_directos(cog, comando, argumentos):
    interaccion = interaccion_admin(en_servidor=False)

    llamar(cog, comando, interaccion, *argumentos)

    assert "dentro de un servidor" in interaccion.texto


def test_info_funciona_por_mensaje_directo(cog):
    interaccion = interaccion_admin(en_servidor=False)

    llamar(cog, "info", interaccion)

    assert interaccion.cantidad_respuestas == 1
    assert (
        interaccion.respuestas[-1].kwargs["embed"].title
        == "⚙️ Información de Naikito Bot"
    )


# ============================================================
# /admin fileexecute
# ============================================================

def test_fileexecute_rechaza_otras_extensiones(cog):
    interaccion = interaccion_admin()

    llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso("stats", nombre="comandos.csv"),
    )

    assert "extensión `.txt`" in interaccion.texto


def test_fileexecute_rechaza_archivos_grandes(cog):
    interaccion = interaccion_admin()
    archivo = AdjuntoFalso("stats")
    archivo.size = 2 * 1024 * 1024

    llamar(cog, "fileexecute", interaccion, archivo)

    assert "1 MiB" in interaccion.texto


def test_fileexecute_rechaza_mas_de_50_lineas(cog):
    interaccion = interaccion_admin()
    lineas = "\n".join(["stats"] * 51)

    llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso(lineas),
    )

    assert "50 comandos" in interaccion.texto


def test_fileexecute_sin_arbol_informa(cog):
    """Sin el cog registrado, las líneas fallan con aviso, no revientan."""

    interaccion = interaccion_admin()

    llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso("stats"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "grupo admin no está disponible" in interaccion.texto


def test_fileexecute_con_comando_desconocido(cog_en_arbol):
    interaccion = interaccion_admin()

    llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso("comando_inexistente"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "Comando admin desconocido" in interaccion.texto


def test_fileexecute_con_miembro_inexistente(cog_en_arbol):
    interaccion = interaccion_admin()

    llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso("box info @nadie"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "No se encontró el miembro" in interaccion.texto
