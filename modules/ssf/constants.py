"""Catálogos y textos estáticos de SeptSinFP.

Nada de este módulo depende de la base de datos ni de discord.py: son datos
planos que comparten los comandos y la lógica.
"""

RANGOS = (
    (0, "Soldado 🪖"),
    (3, "Cabo 🎗️"),
    (5, "Tercer Sargento 🥉"),
    (7, "Segundo Sargento 🥈"),
    (9, "Primer Sargento 🥇"),
    (11, "Subteniente 🛡️"),
    (13, "APS ⚔️"),
    (15, "Segundo Teniente 🎖️"),
    (17, "Primer Teniente 🎖️⭐"),
    (19, "Capitán 🎖️⭐ 🎖️⭐"),
    (21, "Mayor 🎖️⭐ 🎖️⭐ 🎖️⭐"),
    (23, "Coronel ⭐"),
    (25, "General 🌟"),
    (27, "Rey 👑"),
    (29, "Monje ♾️"),
)


TEXTO_AYUDA = (
    "🎯 **Ayuda de SeptSinFP**\n\n"
    "`/ssf registrar` — Anótate en el desafío. Registrarse cuenta como haber sobrevivido el día.\n"
    "`/ssf sobrevivi` — Registra que sobreviviste el día. Hay que hacerlo todos los días.\n"
    "`/ssf estado` — Muestra tu estado, tus rachas y tu rango.\n"
    "`/ssf participantes` — Muestra los participantes, activos y eliminados.\n\n"
    "Si un día no registras tu supervivencia, quedas eliminado del desafío. "
    "Tu mejor racha se conserva aunque quedes eliminado."
)
