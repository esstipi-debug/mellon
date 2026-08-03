"""H10 — la superficie de lectura para el cliente.

El jefe de operaciones del CD es el consumidor mas importante del canal
DECIDIDA, y **no tiene acceso al repo, no sabe que es un diff, y su herramienta
es Teams o SharePoint**. Un registro que solo el FDE puede leer es una libreta
personal con mas ceremonia.

Lo que cierra el hueco no es una aplicacion: es un archivo. Una pagina HTML por
scope, sin autenticacion nueva, sin herramienta nueva, sin red — se adjunta, se
sube a SharePoint o se imprime, y se acabo.

Dos reglas que la pagina hereda de otros huecos y que aca son mas duras, porque
esto SALE del equipo:

  - **agrupado por decision, nunca por persona** (H15). Una pagina con un
    ranking de vencidos por dueno es un tablero de desempeno individual, y el
    dia que se lee asi la gente deja de declarar compromisos.
  - **solo se nombra al dueno** (H14). El tercero mencionado en un rationale es
    un dato personal de alguien que no consintio, y esta pagina termina en el
    SharePoint del cliente.
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
from fdekit.decide.render import render_html, write_html

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=date(2026, 3, 2), roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"), scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=date(2026, 3, 2),
        criteria="distancia media bajo 35 m antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1", scope="pudahuel",
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
    return st


# ------------------------------------------------------- que sea legible


def test_la_pagina_no_pide_nada_de_afuera(store):
    """Cero autenticacion nueva, cero herramienta nueva — y cero red. Un `<img
    src="http...">` o una hoja de estilo remota convierten el archivo en algo
    que no funciona detras del proxy del cliente, que es donde va a vivir."""
    h = render_html(store, "pudahuel", today=HOY)
    for fuera in ("http://", "https://", "<script", "src=", "@import"):
        assert fuera not in h.lower()


def test_la_pagina_se_escribe_sola_en_un_archivo(store, tmp_path):
    p = write_html(store, "pudahuel", tmp_path / "registro.html", today=HOY)
    assert p.exists()
    assert p.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_lo_decidido_aparece_con_su_criterio_y_su_porque(store):
    h = render_html(store, "pudahuel", today=HOY)
    assert "Reslotear la clase A" in h
    assert "distancia media bajo 35 m" in h
    assert "69%" in h


def test_lo_revertido_no_aparece(store):
    d = store.get("D-001")
    d.status = "REVERTIDA"
    store.save(d)
    h = render_html(store, "pudahuel", today=HOY)
    assert "Reslotear la clase A" not in h


def test_el_scope_acota(store):
    d = store.get("D-001")
    d.scope = "quilicura"
    store.save(d)
    assert "Reslotear la clase A" not in render_html(store, "pudahuel", today=HOY)


# ---------------------------------------- las dos reglas de lo que sale


def test_los_vencidos_van_agrupados_por_decision_y_no_por_persona(store):
    """H15. Una pagina que rankea vencidos por dueno es un tablero de desempeno
    individual. El dia que el registro se lee asi, la gente deja de declarar
    compromisos y el sistema muere en dos semanas **sin ninguna senal
    tecnica**."""
    store.add_commitment(Commitment(
        id="", decision_id="D-001", what="reetiquetar las ubicaciones movidas",
        owner="Rodrigo Munoz", due=date(2026, 6, 15),
        evidence_of_done="foto del pasillo", meeting_id="m1", status="VENCIDO",
    ))
    store.add_decision(Decision(
        id="", statement="Consolidar el picking en dos olas diarias",
        owner="Marcela Perez", date_decided=date(2026, 4, 6),
        criteria="2 olas a mas tardar el 30-09", rationale="habia cuatro y se pisaban",
        meeting_id="m1", scope="pudahuel",
    ))
    store.add_commitment(Commitment(
        id="", decision_id="D-002", what="reprogramar las olas en el WMS",
        owner="Rodrigo Munoz", due=date(2026, 6, 20),
        evidence_of_done="captura del WMS", meeting_id="m1", status="VENCIDO",
    ))
    h = render_html(store, "pudahuel", today=HOY)

    # Estructural, no por conteo de strings: cada compromiso vive DENTRO del
    # bloque de su decision. Agrupado por persona, los tres de Rodrigo Munoz
    # caerian juntos en un solo bloque y este reparto se rompe.
    bloques = h.split('<div class="decision')
    de_d1 = next(b for b in bloques if "D-001" in b)
    de_d2 = next(b for b in bloques if "D-002" in b)
    assert "C-001" in de_d1 and "C-002" in de_d1
    assert "C-003" in de_d2
    assert "C-003" not in de_d1


def test_la_pagina_declara_que_no_es_un_tablero_de_desempeno(store):
    """La norma no sirve si vive en un documento aparte que nadie abre: viaja en
    el artefacto que se lee."""
    h = render_html(store, "pudahuel", today=HOY)
    assert "desempeno" in h.lower()
    assert "por decision" in h.lower()


def test_la_pagina_no_nombra_terceros(store):
    """H14. Esto termina en el SharePoint del cliente y sobrevive al proyecto."""
    d = store.get("D-001")
    d.rationale = "el 69% son clase A y Fabian Soto no da abasto en el turno noche"
    store.save(d)
    h = render_html(store, "pudahuel", today=HOY)
    assert "Fabian Soto" not in h
    assert "Rodrigo Munoz" in h   # el dueno si: su nombre es la obligacion


def test_la_pagina_escapa_el_html_del_registro(store):
    """Un enunciado con `<` no puede romper la pagina ni inyectar marcado: el
    texto lo escribe gente, no el sistema."""
    d = store.get("D-001")
    d.statement = "Bajar el corte a <14:00 & avisar al 100% de los <clientes>"
    store.save(d)
    h = render_html(store, "pudahuel", today=HOY)
    assert "&lt;14:00" in h and "&amp;" in h
    assert "<clientes>" not in h


# -------------------------------------------------------- lo que declara


def test_la_pagina_declara_lo_que_no_muestra(store):
    h = render_html(store, "pudahuel", today=HOY)
    assert "no es" in h.lower()
    assert HOY.isoformat() in h   # cuando se genero: una pagina sin fecha miente sola


def test_lo_no_auditable_se_marca_en_la_cara_del_cliente(store):
    """El cliente es justo el que no puede saber por contexto que una fila se
    declaro de memoria en el kickoff."""
    store.add_decision(Decision(
        id="", statement="El corte de pedidos del CD Pudahuel es a las 14:00",
        owner="Marcela Perez", date_decided=date(2026, 3, 1),
        criteria="100% cortados antes de las 14:00", rationale="el transporte sale 15:00",
        meeting_id="m1", scope="pudahuel", origen="SIEMBRA",
    ))
    h = render_html(store, "pudahuel", today=HOY)
    assert "declarada" in h.lower() or "no auditable" in h.lower()


def test_el_supuesto_caido_se_ve_porque_es_lo_que_pone_en_riesgo(store):
    h = render_html(store, "pudahuel", today=HOY)
    assert "el layout no cambia" in h
    assert "VENCIDO" in h


# -------------------------------------------------------------- idioma


def test_el_enunciado_en_ingles_se_usa_si_esta(store):
    """El registro se escribe en espanol y el reporte a la matriz suele ser en
    ingles. Traducido una vez al promover: barato ahora, imposible de
    retrofitear a las 200 decisiones."""
    d = store.get("D-001")
    d.enunciado_en = "Reslot class A into the golden zone of the Pudahuel DC"
    store.save(d)
    h = render_html(store, "pudahuel", today=HOY, idioma="en")
    assert "Reslot class A" in h


def test_sin_traduccion_se_muestra_el_original_y_se_dice(store):
    """Callarlo dejaria una pagina en ingles con filas en espanol y ninguna
    explicacion; inventar la traduccion seria peor."""
    h = render_html(store, "pudahuel", today=HOY, idioma="en")
    assert "Reslotear la clase A" in h
    assert "sin traducir" in h.lower()
