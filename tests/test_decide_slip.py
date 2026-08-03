"""H11 — el compromiso renegociado en privado.

Lo que pasa en la realidad: dueno y solicitante acuerdan por chat una fecha
nueva. El registro sigue mostrando VENCIDO. A la tercera vez el dueno concluye
que el registro esta mal, deja de mirarlo, y desde ahi el tablero de vencidos es
ruido que todos ignoran.

**Es la muerte mas comun de estos sistemas.** No se cierra con una validacion
mas: se cierra haciendo que renegociar sea literalmente mas barato que incumplir
en silencio. Una linea, desde el telefono, sin pedir permiso.

Y con un limite, porque la valvula tiene su propio modo de falla: un compromiso
al que se le corre la fecha tres veces no es un atraso, es una decision que no
se tomo. Correrla una cuarta vez es como el registro deja de significar nada
sin que ningun numero se vea mal.
"""

from datetime import date

import pytest

from fdekit.decide import (
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
    agenda,
    tick,
)
from fdekit.decide.query import MAX_SLIPS, slip

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"), scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=HOY, criteria="antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1",
    ))
    st.add_commitment(Commitment(
        id="", decision_id="D-001", what="mover 200 ubicaciones del pasillo 3",
        owner="Rodrigo Munoz", due=date(2026, 8, 15),
        evidence_of_done="reporte del WMS", meeting_id="m1",
    ))
    return st


# ------------------------------------------------------- la fecha se corre


def test_correr_la_fecha_conserva_la_anterior(store):
    """Nunca edita la fecha original: crea version y deja la anterior al lado.
    Sin eso, el registro no puede distinguir 'se cumplio' de 'se corrio hasta
    que se cumplio', que es justo lo que hay que poder ver."""
    r = slip(store, "C-001", date(2026, 9, 5), motivo="el proveedor movio la entrega",
             por="Rodrigo Munoz", today=HOY)
    assert r["applied"] is True

    c = store.get("C-001")
    assert c.due == date(2026, 9, 5)
    assert len(c.slips) == 1
    assert c.slips[0]["de"] == "2026-08-15"
    assert c.slips[0]["a"] == "2026-09-05"
    assert "proveedor" in c.slips[0]["motivo"]
    assert c.slips[0]["por"] == "Rodrigo Munoz"


def test_correr_la_fecha_exige_motivo(store):
    """Mismo contrato que `supersede --apply`: sin motivo, en seis semanas nadie
    sabe por que se movio y la unica lectura posible es 'no se hizo'."""
    with pytest.raises(ValueError, match="motivo"):
        slip(store, "C-001", date(2026, 9, 5), motivo="", por="Rodrigo Munoz", today=HOY)
    assert store.get("C-001").slips == []


def test_un_vencido_vuelve_a_ABIERTO_al_renegociar(store):
    """El punto entero del hueco. Si renegociar deja el compromiso en VENCIDO,
    el tablero sigue mintiendo y el dueno deja de mirarlo."""
    tick(store, date(2026, 8, 20))
    assert store.get("C-001").status == "VENCIDO"

    slip(store, "C-001", date(2026, 9, 5), motivo="el proveedor movio la entrega",
         por="Rodrigo Munoz", today=date(2026, 8, 20))
    assert store.get("C-001").status == "ABIERTO"
    # Y el tick siguiente no lo vuelve a vencer: la fecha nueva rige.
    tick(store, date(2026, 8, 21))
    assert store.get("C-001").status == "ABIERTO"


def test_no_se_puede_correr_la_fecha_hacia_atras_del_dia_de_hoy(store):
    """Poner una fecha ya pasada no es renegociar: es dejar el compromiso
    vencido de nacimiento y con un motivo escrito que lo hace ver atendido."""
    with pytest.raises(ValueError, match="pasado"):
        slip(store, "C-001", date(2026, 7, 1), motivo="x que sea largo",
             por="Rodrigo Munoz", today=HOY)


def test_un_compromiso_muerto_no_se_renegocia(store):
    """Correrle la fecha a algo CUMPLIDO o CANCELADO lo revive sin que nadie lo
    haya decidido."""
    c = store.get("C-001")
    c.status = "CUMPLIDO"
    store.save(c)
    with pytest.raises(ValueError, match="CUMPLIDO"):
        slip(store, "C-001", date(2026, 9, 5), motivo="el proveedor movio",
             por="Rodrigo Munoz", today=HOY)


# ----------------------------------------------- el limite de la valvula


def _correr(store, veces, desde=date(2026, 9, 5)):
    from datetime import timedelta

    out = []
    for i in range(veces):
        out.append(slip(store, "C-001", desde + timedelta(days=30 * i),
                        motivo=f"el proveedor movio la entrega, vuelta {i}",
                        por="Rodrigo Munoz", today=HOY))
    return out


def test_tres_corridas_dejan_de_ser_un_atraso(store):
    """Un compromiso con tres slips no es un atraso: es una decision que no se
    tomo. Seguir corriendo la fecha la deja invisible para siempre."""
    _correr(store, MAX_SLIPS)
    c = store.get("C-001")
    assert c.slips_hacia_adelante == MAX_SLIPS
    assert c.es_no_decision is True


def test_la_cuarta_corrida_no_se_rechaza_pero_escala(store):
    """Rechazarla mandaria al dueno al silencio, que es exactamente el modo de
    falla que el hueco describe: renegociar tiene que seguir siendo mas barato
    que incumplir callado. Lo que se hace es aplicarla Y abrir la pregunta."""
    _correr(store, MAX_SLIPS)
    r = slip(store, "C-001", date(2027, 1, 5), motivo="el proveedor movio otra vez",
             por="Rodrigo Munoz", today=HOY)

    assert r["applied"] is True
    assert r["escalado"] is not None
    q = store.get(r["escalado"])
    assert q.status == "ABIERTA"
    assert "C-001" in q.question
    assert q.resolver == "Marcela Perez"   # el dueno de la DECISION, no el del compromiso
    assert "D-001" in q.blocks


def test_la_escalada_se_abre_una_sola_vez(store):
    """Idempotente como `tick`: una pregunta nueva por cada slip a partir del
    tercero llenaria la agenda de la misma pregunta."""
    _correr(store, MAX_SLIPS + 3)
    preguntas = [q for q in store.questions() if "C-001" in q.question]
    assert len(preguntas) == 1


def test_la_pregunta_de_escalada_entra_a_la_agenda(store):
    """Si no aparece en la agenda, la escalada es un campo que nadie lee."""
    _correr(store, MAX_SLIPS + 1)
    ag = agenda(store, "m1", today=HOY)
    assert any("C-001" in q.question for q in ag.open_questions)
    assert ag.verdict == "reunion justificada"


def test_correr_la_fecha_hacia_adelante_es_lo_que_se_cuenta(store):
    """Adelantar un compromiso tambien es renegociar y se registra, pero no es
    lo que el limite persigue: el modo de falla es la fecha que se corre, no la
    que se acerca."""
    slip(store, "C-001", date(2026, 9, 5), motivo="el proveedor movio la entrega",
         por="Rodrigo Munoz", today=HOY)
    slip(store, "C-001", date(2026, 8, 20), motivo="se libero capacidad antes",
         por="Rodrigo Munoz", today=HOY)
    c = store.get("C-001")
    assert len(c.slips) == 2
    assert c.slips_hacia_adelante == 1
    assert c.es_no_decision is False


# ------------------------------------------------------------ visibilidad


def test_el_historial_de_corridas_sobrevive_a_la_relectura(store):
    """Si no cruza el front-matter, el registro pierde justo el dato que hace
    visible el patron."""
    _correr(store, 2)
    fresco = DecideStore(store.root)
    assert len(fresco.get("C-001").slips) == 2
    assert fresco.get("C-001").slips[0]["de"] == "2026-08-15"


def test_el_compromiso_corrido_no_se_ve_igual_que_uno_cumplido_a_tiempo(store):
    """La regla 3 sobre el dato que mas tienta a esconder."""
    _correr(store, 2)
    c = store.get("C-001")
    c.status = "CUMPLIDO"
    store.save(c)
    assert c.slips_hacia_adelante == 2
