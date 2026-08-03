"""H16 — accesibilidad, y H12e — el hash que ya no verifica nada.

H16 es el hueco mas barato del estudio y el de mejor retorno politico: nadie
menciono al participante con discapacidad auditiva, ni al remoto con mal audio,
ni al no-hispanohablante del equipo global. Para los tres, el transcripto y el
pre-read son **la diferencia entre participar y asistir**.

Framear el canal HABLADA como accesibilidad en vez de como vigilancia cambia la
politica entera de la conversacion de consentimiento, y es probablemente el
argumento mas fuerte que tiene el proyecto para que le dejen grabar. Cuesta
cero tecnicamente — pero solo si el transcripto de verdad esta disponible para
los participantes, y si la pagina que se les manda de verdad se puede leer.

Ahi estaba el defecto: la pagina del cliente senalaba riesgo y vencimiento
**solo con color**. Para quien no distingue rojo de verde —y para quien la
imprime en blanco y negro, que es la mitad de los casos reales— esa pagina no
dice nada.
"""

from datetime import date

import pytest

from fdekit.decide import (
    Assumption,
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
)
from fdekit.decide.render import render_html
from fdekit.decide.transcript import TranscriptStore, transcripto_para_participantes

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")

SEGMENTOS = [
    {"start": 0.0, "end": 6.0, "text": "Buenos dias, gracias por venir."},
    {"start": 6.0, "end": 24.0, "text":
        "Queda decidido: reslotear la clase A a la zona dorada del CD Pudahuel."},
    {"start": 24.0, "end": 40.0, "text": "Rodrigo Munoz se compromete a mover 200 ubicaciones."},
]


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=date(2026, 3, 2), roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo",
                        recording_allowed=True, retention_days=90),
        scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=date(2026, 3, 2),
        criteria="distancia media bajo 35 m antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1", scope="pudahuel",
        status="EN_RIESGO",
    ))
    st.add_commitment(Commitment(
        id="", decision_id="D-001", what="mover 200 ubicaciones del pasillo 3",
        owner="Rodrigo Munoz", due=date(2026, 6, 1),
        evidence_of_done="reporte del WMS", meeting_id="m1", status="VENCIDO",
    ))
    st.add_assumption(Assumption(
        id="", decision_id="D-001", statement="el layout no cambia hasta septiembre",
        check_by=date(2026, 5, 1), source="jefe de operaciones", meeting_id="m1",
        status="VENCIDO",
    ))
    TranscriptStore(st.root, "m1").ingest_segments(SEGMENTOS)
    return st


# --------------------------------------- la pagina se lee sin ver colores


def test_el_riesgo_no_se_senala_solo_con_color(store):
    """La mitad de las veces esta pagina se imprime en blanco y negro, y ~8% de
    los hombres no distingue rojo de verde. Un borde de color es exactamente
    cero informacion para los dos casos."""
    h = render_html(store, "pudahuel", today=HOY)
    assert "EN RIESGO" in h.upper()


def test_el_vencido_no_se_senala_solo_con_color(store):
    h = render_html(store, "pudahuel", today=HOY)
    # El texto tiene que estar en la fila, no solo en la clase CSS.
    fila = next(l for l in h.splitlines() if "C-001" in l)
    assert "vencid" in fila.lower().replace('class="vencido"', "")


def test_la_pagina_declara_su_idioma(store):
    """Sin `lang`, un lector de pantalla lee el espanol con fonetica inglesa y
    el resultado es literalmente incomprensible."""
    assert '<html lang="es"' in render_html(store, "pudahuel", today=HOY)
    assert '<html lang="en"' in render_html(store, "pudahuel", today=HOY, idioma="en")


def test_los_encabezados_no_saltan_niveles(store):
    """Saltar de h1 a h3 rompe la navegacion por encabezados, que es como se
    recorre un documento largo con lector de pantalla."""
    import re

    niveles = [int(m) for m in re.findall(r"<h([1-6])", render_html(store, "pudahuel", today=HOY))]
    assert niveles[0] == 1
    for antes, despues in zip(niveles, niveles[1:]):
        assert despues <= antes + 1


def test_la_pagina_no_depende_de_un_esquema_de_color_impuesto(store):
    """`color-scheme: light` a secas fuerza fondo blanco aunque el sistema del
    lector este en alto contraste o en oscuro."""
    h = render_html(store, "pudahuel", today=HOY)
    assert "prefers-color-scheme" in h


# ------------------------------ el transcripto, para los participantes


def test_el_transcripto_sale_legible_para_quien_estuvo(store):
    """El artefacto de H16. Sin esto, "disponible para los participantes" es una
    frase del kickoff que nadie puede ejercer."""
    t = transcripto_para_participantes(store, "m1")
    assert "reslotear la clase A" in t
    assert "00:06" in t


def test_el_transcripto_dice_para_que_es_y_hasta_cuando(store):
    """Un transcripto sin su fecha de destruccion invita a guardarlo aparte, y
    una copia fuera del sistema es la politica de retencion rota en silencio."""
    t = transcripto_para_participantes(store, "m1")
    assert "accesibilidad" in t.lower()
    assert "90" in t   # los dias de retencion declarados


def test_el_transcripto_no_sale_si_nadie_consintio_grabar(store):
    """La accesibilidad no es una puerta trasera al consentimiento."""
    m = store.get_meeting("m1")
    m.consent = Consent(True, "Marcela Perez", "interes_legitimo", recording_allowed=False)
    store.save(m)
    with pytest.raises(ValueError, match="consent"):
        transcripto_para_participantes(store, "m1")


def test_el_transcripto_purgado_lo_dice_en_vez_de_devolver_vacio(store):
    """Un vacio parece un error del sistema; una lapida explica que la politica
    de retencion funciono."""
    TranscriptStore(store.root, "m1").purge(date(2026, 12, 1), 90, desde=date(2026, 3, 2))
    t = transcripto_para_participantes(store, "m1")
    assert "retencion" in t.lower()
    assert "destru" in t.lower()


# --------------------------- H12e: el hash despues del vencimiento


def test_el_hash_declara_que_ya_no_reaudita_nada(store):
    """El hash sirve para detectar **mutacion mientras la fuente vive**, no para
    reauditar despues del vencimiento. El diseno original congelaba el sha256 y
    despues borraba la fuente por TTL, quedandose con un hash que no verifica
    contra nada — y eso se lee como si verificara algo."""
    from fdekit.decide.anchor import freeze, verify

    ts = TranscriptStore(store.root, "m1")
    a = freeze(ts, 1)
    assert verify(a, ts)[0] is True

    ts.purge(date(2026, 12, 1), 90, desde=date(2026, 3, 2))
    ok, motivo = verify(a, ts)
    assert ok is False
    assert "retencion" in motivo
    # Y no se presenta como una falla del ancla: la cita sigue sirviendo.
    assert "sobrevive" in motivo
