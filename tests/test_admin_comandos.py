"""Pruebas de los comandos administrativos ejecutados de punta a punta.

Cada comando se invoca a través de su callback real con una interacción falsa,
así que estas pruebas recorren el mismo camino que Discord.
"""

import pytest

from tests.harness import (
    Choice,
    GuildFalso,
    InteraccionFalsa,
    UsuarioFalso,
    construir_cog,
)

GUILD = 1
ADMIN = 1
USUARIO = 42

ARBOL_ESPERADO = {
    "admin|Group",
    "admin box|Group",
    "admin box cancelar|Command",
    "admin box canticos|Command",
    "admin box cerrar_combate|Command",
    "admin box curar|Command",
    "admin box dar_dinero|Command",
    "admin box dar_exp|Command",
    "admin box dar_sponsor|Command",
    "admin box finalizar|Command",
    "admin box historial|Command",
    "admin box info|Command",
    "admin box lesionados|Command",
    "admin box probabilidad|Command",
    "admin box procesar|Command",
    "admin box quitar_sponsor|Command",
    "admin box reset|Command",
    "admin box sponsors|Command",
    "admin box stats|Command",
    "admin box top|Command",
    "admin fileexecute|Command",
    "admin info|Command",
    "admin test|Command",
    "admin madrugue|Group",
    "admin madrugue manualadd|Command",
    "admin madrugue resetdia|Command",
    "admin madrugue resettotal|Command",
    "admin madrugue resetusuario|Command",
    "admin madrugue stats|Command",
    "admin madrugue top|Command",
    "admin madrugue ver|Command",
    "admin manualadd|Command",
    "admin resetdia|Command",
    "admin resettotal|Command",
    "admin resetusuario|Command",
    "admin stats|Command",
    "admin top|Command",
    "admin ver|Command",
    "admin 420|Group",
    "admin 420 importar|Command",
    "admin 420 manualadd|Command",
    "admin 420 resetdia|Command",
    "admin 420 ver|Command",
    "admin 420 resetusuario|Command",
    "admin 420 resettotal|Command",
    "admin 420 stats|Command",
    "admin ssf|Group",
    "admin ssf agregar|Command",
    "admin ssf cerrar|Command",
    "admin ssf desafio|Command",
    "admin ssf eliminar|Command",
    "admin ssf estado|Command",
    "admin ssf iniciar|Command",
    "admin ssf participantes|Command",
    "admin ssf quitar|Command",
    "admin ssf ranking|Command",
    "admin ssf recalcular|Command",
    "admin ssf revivir|Command",
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
async def cog_en_arbol(base_datos_limpia, admin_ids):
    """Cog registrado en un árbol real (lo necesita fileexecute)."""

    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.admin")

    await cargar()

    return bot.get_cog("Admin")





async def llamar(cog, nombre_metodo, interaccion, *args):
    metodo = getattr(type(cog), nombre_metodo).callback
    return await metodo(cog, interaccion, *args)


class AdjuntoFalso:
    """Doble mínimo de ``discord.Attachment`` para fileexecute."""

    def __init__(self, contenido="", nombre="comandos.txt"):
        self.filename = nombre
        self._contenido = (
            contenido.encode("utf-8")
            if isinstance(contenido, str)
            else contenido
        )
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

async def test_extension_registra_el_arbol_completo(base_datos_limpia):
    import discord
    from discord.ext import commands

    bot = commands.Bot(
        command_prefix="$!",
        intents=discord.Intents.default(),
    )

    async def cargar():
        await bot.load_extension("commands.admin")

    await cargar()

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
    ("box_top", ()),
    ("box_stats", ()),
    ("box_historial", (None,)),
    ("box_lesionados", ()),
    ("box_finalizar", (None,)),
    ("box_procesar", ()),
    ("fileexecute", (None,)),
    ("info", ()),
    ("test", ()),
    ("madrugue_stats", ()),
    ("madrugue_top", ()),
    ("madrugue_ver", (None,)),
    ("madrugue_resetdia", (None, "2026-09-01")),
    ("madrugue_resetusuario", (None,)),
    ("madrugue_resettotal", (Choice("SI"),)),
    ("madrugue_manualadd", (None, "2026-09-01", "05:45")),
    ("stats", ()),
    ("top", ()),
    ("ver", (None,)),
    ("resetdia", (None, "2026-09-01")),
    ("resetusuario", (None,)),
    ("resettotal", (Choice("SI"),)),
    ("manualadd", (None, "2026-09-01", "05:45")),
    ("ssf_revivir", (None, "2026-09-01")),
    ("ssf_iniciar", (None,)),
    ("ssf_agregar", (None, "2026-09-04")),
    ("ssf_quitar", (None, "2026-09-05")),
    ("ssf_recalcular", (None,)),
    ("ssf_estado", (None,)),
    ("ssf_desafio", ()),
    ("ssf_participantes", ()),
    ("ssf_eliminar", (None, "2026-09-01")),
    ("ssf_cerrar", (Choice("SI"),)),
    ("ssf_ranking", ()),
]


@pytest.mark.parametrize(
    "comando, argumentos",
    COMANDOS_CON_ARGUMENTO_FALSO,
)
async def test_comandos_rechazan_a_no_administradores(cog, comando, argumentos):
    interaccion = InteraccionFalsa(GUILD, USUARIO)

    await llamar(cog, comando, interaccion, *argumentos)

    assert interaccion.cantidad_respuestas == 1
    assert "No tienes permisos" in interaccion.texto


@pytest.mark.parametrize(
    "comando, argumentos",
    [
        ("box_info", (None,)),
        ("test", ()),
        ("madrugue_stats", ()),
        ("madrugue_manualadd", (None, "2026-09-01", "05:45")),
        ("stats", ()),
        ("manualadd", (None, "2026-09-01", "05:45")),
        ("ssf_revivir", (None, "2026-09-01")),
        ("ssf_quitar", (None, "2026-09-05")),
        ("ssf_estado", (None,)),
        ("box_historial", (None,)),
    ],
)
async def test_comandos_rechazan_mensajes_directos(cog, comando, argumentos):
    interaccion = interaccion_admin(en_servidor=False)

    await llamar(cog, comando, interaccion, *argumentos)

    assert "dentro de un servidor" in interaccion.texto


async def test_info_funciona_por_mensaje_directo(cog):
    interaccion = interaccion_admin(en_servidor=False)

    await llamar(cog, "info", interaccion)

    assert interaccion.cantidad_respuestas == 1
    assert (
        interaccion.respuestas[-1].kwargs["embed"].title
        == "⚙️ Información de Naikito Bot"
    )


# ============================================================
# /admin box cancelar
# ============================================================

async def test_box_cancelar_con_accion_activa_responde_sin_view_none(cog):
    """Regresión: la cancelación reventaba en producción.

    ``responder_texto`` llegaba a ``send_message`` con ``view=None`` y
    discord.py levantaba ``AttributeError: 'NoneType' object has no
    attribute 'is_finished'``. El doble del harness revive ese contrato,
    así que basta con que el comando responda sin excepción.
    """
    from datetime import datetime, timedelta, timezone

    from modules.box.database import iniciar_accion
    from tests.harness import UsuarioFalso

    ahora = datetime.now(timezone.utc)
    assert await iniciar_accion(
        GUILD,
        USUARIO,
        "ENTRENANDO",
        ahora,
        ahora + timedelta(hours=1),
        recompensa=50,
        dinero_recompensa=10,
    )

    interaccion = interaccion_admin()

    await llamar(cog, "box_cancelar", interaccion, UsuarioFalso(USUARIO, "Peleador"))

    assert "Acción cancelada correctamente" in interaccion.texto
    # Sin vista se debe enviar el centinela MISSING, nunca None.
    assert interaccion.respuestas[-1].kwargs.get("view", "ausente") is not None


async def test_box_cancelar_sin_accion_activa_informa(cog):
    from tests.harness import UsuarioFalso

    interaccion = interaccion_admin()

    await llamar(cog, "box_cancelar", interaccion, UsuarioFalso(USUARIO, "Peleador"))

    assert "no tiene ninguna acción activa" in interaccion.texto
    assert interaccion.respuestas[-1].kwargs.get("view", "ausente") is not None


# ============================================================
# /admin manualadd
# ============================================================

async def test_manualadd_difiere_y_guarda_el_registro(cog):
    """Las consultas de base no deben consumir la ventana de Discord."""

    from datetime import date

    from modules.madrugue.database import obtener_registro_del_dia

    usuario = UsuarioFalso(USUARIO, "Madrugador")
    interaccion = interaccion_admin()
    interaccion.guild = GuildFalso(GUILD, {USUARIO: usuario})

    await llamar(
        cog,
        "manualadd",
        interaccion,
        usuario,
        "2026-09-01",
        "05:45",
    )

    assert interaccion.cantidad_respuestas == 2
    assert interaccion.respuestas[0].contenido is None
    assert interaccion.respuestas[0].efimero is True
    assert "REGISTRO MANUAL AGREGADO" in interaccion.texto

    registro = await obtener_registro_del_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 1),
    )
    assert registro is not None
    assert registro[0] == "05:45"


# ============================================================
# /admin fileexecute
# ============================================================

async def test_fileexecute_rechaza_otras_extensiones(cog):
    interaccion = interaccion_admin()

    await llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso("stats", nombre="comandos.csv"),
    )

    assert "extensión `.txt`" in interaccion.texto


async def test_fileexecute_rechaza_archivos_grandes(cog):
    interaccion = interaccion_admin()
    archivo = AdjuntoFalso("stats")
    archivo.size = 2 * 1024 * 1024

    await llamar(cog, "fileexecute", interaccion, archivo)

    assert "1 MiB" in interaccion.texto


async def test_fileexecute_rechaza_mas_de_50_lineas(cog):
    interaccion = interaccion_admin()
    lineas = "\n".join(["stats"] * 51)

    await llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso(lineas),
    )

    assert "50 comandos" in interaccion.texto


async def test_fileexecute_sin_arbol_informa(cog):
    """Sin el cog registrado, las líneas fallan con aviso, no revientan."""

    interaccion = interaccion_admin()

    await llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso("stats"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "grupo admin no está disponible" in interaccion.texto


async def test_fileexecute_con_comando_desconocido(cog_en_arbol):
    interaccion = interaccion_admin()

    await llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso("comando_inexistente"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "Comando admin desconocido" in interaccion.texto


async def test_fileexecute_con_miembro_inexistente(cog_en_arbol):
    interaccion = interaccion_admin()

    await llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso("box info @nadie"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "No se encontró el miembro" in interaccion.texto


async def test_fileexecute_ejecuta_manualadd_despues_del_defer(cog_en_arbol):
    """Un comando interno no debe intentar diferir la interacción otra vez."""

    from datetime import date

    from modules.madrugue.database import obtener_registro_del_dia

    usuario = UsuarioFalso(USUARIO, "Madrugador")
    interaccion = interaccion_admin()
    interaccion.guild = GuildFalso(GUILD, {USUARIO: usuario})

    await llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso("manualadd 42 2026-09-01 05:45"),
    )

    assert "Ejecución finalizada" in interaccion.texto
    assert "✅ Línea 1" in interaccion.texto
    assert any(
        "REGISTRO MANUAL AGREGADO" in respuesta.texto
        for respuesta in interaccion.respuestas
    )
    assert await obtener_registro_del_dia(
        GUILD,
        USUARIO,
        date(2026, 9, 1),
    ) is not None


async def test_fileexecute_rechaza_archivo_que_no_es_utf8(cog):
    interaccion = interaccion_admin()

    await llamar(
        cog,
        "fileexecute",
        interaccion,
        AdjuntoFalso(b"\xff\xfe\xfa"),
    )

    assert "texto UTF-8" in interaccion.texto


async def test_fileexecute_fragmenta_un_informe_mayor_a_2000_caracteres(
    cog_en_arbol,
):
    interaccion = interaccion_admin()
    comando_desconocido = "x" * 100
    contenido = "\n".join([comando_desconocido] * 50)

    await llamar(
        cog_en_arbol,
        "fileexecute",
        interaccion,
        AdjuntoFalso(contenido),
    )

    informes = [
        respuesta
        for respuesta in interaccion.respuestas
        if "Ejecución finalizada" in respuesta.texto
    ]
    assert len(informes) > 1
    assert all(len(informe.contenido) <= 2000 for informe in informes)
