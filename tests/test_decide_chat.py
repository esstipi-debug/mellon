"""H5 — ingesta del canal asincronico.

Los formatos de estos tests NO son inventados: salen de inspeccionar exports
reales byte a byte (seis archivos, 11.005 lineas) mas CLDR como fuente de los
formatos por locale. Un ejemplo inventado que no matchea el export real produce
un parser que descarta todo en silencio, que es el modo de falla que este modulo
existe para impedir.
"""

from datetime import date

import pytest

from fdekit.decide import Consent, DecideStore
from fdekit.decide.chat import ingest_chat, parse_chat
from fdekit.decide.draft import DraftStore

# es-CL con Android <=14 (24h) y 15+ (12h con U+202F antes del meridiano),
# conviviendo en el MISMO grupo — CLDR cambio es-CL entre 43 y 44 (abr-2024).
#
# Con marcador verbal: `draft_decisions` solo produce donde hay uno, y eso es
# deliberado — el silencio del sistema mide la disciplina de quien escribe.
LINEA_24H = "25-08-26, 14:31 - Jefe de Turno CD: queda decidido que bajamos el pick a 2 turnos"
LINEA_12H = "25-08-26, 2:35 p. m. - Marcela Perez: dale"
# iOS: LRM invisible al inicio, corchetes, segundos.
LINEA_IOS = "‎[25-08-26, 14:40:12] Fabian Soto: confirmado"


def test_las_tres_familias_conviven_en_un_export():
    """El mismo grupo produce formatos distintos segun el telefono de cada uno.
    Un parser que solo cubre uno descarta a los demas sin fallar."""
    log = parse_chat("\n".join([LINEA_24H, LINEA_12H, LINEA_IOS]))
    assert len(log.mensajes) == 3
    assert log.autores == ("Jefe de Turno CD", "Marcela Perez", "Fabian Soto")


def test_la_aritmetica_cierra_siempre():
    """Toda linea contada. El modo de falla que importa no es que el parser
    reviente: es que diga "148 mensajes" cuando habia 190."""
    c = parse_chat("\n".join([LINEA_24H, LINEA_12H, LINEA_IOS])).cobertura()
    assert c["cuadra"] is True
    assert (
        c["mensajes"] + c["continuaciones"] + c["sistema_o_adjunto"] + c["sin_parsear"]
        == c["lineas_totales"]
    )


def test_la_continuacion_multilinea_se_pega_al_mensaje():
    """Son el 15,9% de las lineas de un export iOS real (347 de 2.189): no es un
    caso borde. Se definen por NEGACION del unico detector de cabecera."""
    log = parse_chat(f"{LINEA_IOS}\nsegunda linea del mismo mensaje\n")
    assert len(log.mensajes) == 1
    assert log.mensajes[0].texto == "confirmado\nsegunda linea del mismo mensaje"
    assert log.cobertura()["continuaciones"] == 1


def test_un_formato_no_cubierto_se_REPORTA_en_vez_de_pegarse():
    """El agujero de la negacion sola: una linea que INTENTA ser cabecera en un
    formato que no cubrimos se pegaba al mensaje anterior, y la cobertura decia
    que todo cuadraba. Se la comia entera sin un aviso."""
    log = parse_chat(f"{LINEA_24H}\n02/08/2026 14:35 B: sin coma y sin guion\n")
    assert len(log.mensajes) == 1
    assert len(log.lineas_sin_parsear) == 1
    assert "02/08/2026" in log.lineas_sin_parsear[0][1]


def test_la_notificacion_de_cifrado_no_es_un_mensaje_de_nadie():
    """En iOS 1:1 viene ATRIBUIDA a una persona real, con "Autor: " delante. Sin
    descartarla, cada conteo por autor le suma un mensaje que nunca escribio."""
    log = parse_chat(
        "25-08-26, 09:00 - Marcela Perez: Los mensajes y las llamadas estan cifrados "
        "de extremo a extremo.\n" + LINEA_24H
    )
    assert len(log.mensajes) == 1
    assert "Marcela Perez" not in log.autores


def test_el_adjunto_sin_texto_propio_no_es_un_mensaje():
    log = parse_chat(
        "25-08-26, 14:41 - Fabian Soto: ‎IMG-20260825-WA0001.jpg (archivo adjunto)\n"
        + LINEA_24H
    )
    assert len(log.mensajes) == 1


def test_los_invisibles_de_ios_no_rompen_el_match():
    """LRM, BOM y los envoltorios de direccion son la causa numero uno de que una
    regex correcta no matchee nada y el parser devuelva cero sin un solo error."""
    log = parse_chat("﻿‎[25-08-26, 14:40:12] ‪Fabian Soto‬: hola\n")
    assert len(log.mensajes) == 1
    assert log.mensajes[0].autor == "Fabian Soto"


# ------------------------------------------------- el orden dia/mes


def test_el_orden_se_infiere_del_archivo_entero():
    """Linea a linea es indecidible: `3/6` es 3-jun o 6-mar segun la region del
    telefono. Sobre el export completo casi siempre hay una fecha con un
    componente > 12 que lo resuelve."""
    cl = parse_chat("25-08-26, 14:31 - A: uno\n02-08-26, 14:32 - A: dos\n")
    assert cl.dia_primero is True and "inferido" in cl.orden_inferido_de

    us = parse_chat("8/25/26, 2:31 pm - A: uno\n8/02/26, 2:32 pm - A: dos\n")
    assert us.dia_primero is False and "inferido" in us.orden_inferido_de


def test_cuando_no_se_puede_inferir_lo_dice_en_vez_de_tener_suerte():
    log = parse_chat("02-08-26, 14:31 - A: uno\n03-06-26, 14:32 - A: dos\n")
    assert log.dia_primero is True  # se asume Chile
    assert "SUPUESTO, no inferido" in log.orden_inferido_de


def test_dos_exports_pegados_se_denuncian():
    """Pasa cuando se juntan exports de telefonos con regiones distintas."""
    log = parse_chat("25-08-26, 14:31 - A: uno\n8/25/26, 2:32 pm - A: dos\n")
    assert "CONTRADICTORIO" in log.orden_inferido_de


# ------------------------------------------------- ingesta al registro


@pytest.fixture
def store(tmp_path):
    return DecideStore(tmp_path / "decide")


def _consent():
    return Consent(granted=True, granted_by="Marcela Perez", basis="interes_legitimo")


def test_la_ingesta_alimenta_la_cola_y_NO_el_registro(store):
    """El canal asincronico alimenta la cola de revision, no el registro: una
    decision de chat no supersede a una de sala por ser mas reciente."""
    r = ingest_chat(store, f"{LINEA_24H}\n", "wa-35", _consent(), today=date(2026, 8, 26))
    assert r["borradores"] == 1
    assert store.decisions() == []
    assert all(not d.ready for d in DraftStore(store.root, "wa-35").load())


def test_se_alimenta_el_CUERPO_y_no_la_linea(store):
    """Con la linea cruda, `_find_date` toma la primera fecha del texto: el
    timestamp del mensaje eclipsaba el plazo real Y se convertia EN el plazo."""
    ingest_chat(
        store,
        "25-08-26, 2:35 p. m. - Marcela Perez: Rodrigo se compromete a auditar el "
        "maestro antes del 30/9\n",
        "wa-35",
        _consent(),
        today=date(2026, 8, 26),
    )
    d = DraftStore(store.root, "wa-35").load()[0]
    assert d.fields["due"] == "2026-09-30"  # el plazo real, no el timestamp


def test_el_autor_del_mensaje_no_es_el_dueno(store):
    """"Marcela: Rodrigo se compromete a..." tiene autor Marcela y dueno
    Rodrigo. Usar el autor como dueno seria un texto alimentando dos campos, en
    el campo que constituye la obligacion."""
    ingest_chat(
        store,
        "25-08-26, 14:31 - Marcela Perez: Rodrigo se compromete a auditar el maestro\n",
        "wa-35",
        _consent(),
        today=date(2026, 8, 26),
    )
    d = DraftStore(store.root, "wa-35").load()[0]
    assert d.fields["owner"] != "Marcela Perez"
    assert any("de chat: Marcela Perez" in n for n in d.notes)  # va como procedencia


def test_la_ventana_queda_fuera_del_corpus_de_control(store):
    """Una ventana de chat no es una serie de decision: no puede abrir la
    compuerta de la regla 5 ni mover la linea base del XmR."""
    ingest_chat(store, f"{LINEA_24H}\n", "wa-35", _consent(), today=date(2026, 8, 26))
    c = store.corpus()
    assert len(c.meetings) == 0
    assert "canal asincronico" in c.nota()


def test_el_roster_de_la_ventana_son_los_que_escribieron(store):
    """No hay lista de invitados en un grupo de WhatsApp. Derivarlo de los
    autores es lo unico que no inventa gente — y tiene la consecuencia correcta:
    un compromiso asignado a alguien que nunca escribio va a la cola pidiendo
    dueno, porque no esta en el scope lexico."""
    r = ingest_chat(
        store, f"{LINEA_24H}\n{LINEA_12H}\n", "wa-35", _consent(), today=date(2026, 8, 26)
    )
    assert set(r["autores"]) == {"Jefe de Turno CD", "Marcela Perez"}
    assert store.get_meeting("wa-35").roster == r["autores"]
