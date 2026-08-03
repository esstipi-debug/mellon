"""H12 — code-switching espanol/ingles, y las otras fallas tecnicas del tier 2.

En supply chain el code-switching es la norma, no la excepcion: "hay que hacer
el *cutover* el viernes", "el *slotting* del *picking* de *fast movers*". El
lexico de decision y los slots estaban escritos **solo en espanol**, asi que
media conversacion real no producia ni un slot — y sin slots no hay
desambiguacion de fase 3, no hay alias disputables y no hay `_l2`.

La forma correcta de cerrarlo no es una lista en ingles al lado de la lista en
espanol: es **bilingue POR TERMINO**. Si "reslotear" y "slotting" produjeran
valores canonicos distintos, dos menciones del mismo proceso no se reconocerian
como el mismo slot, y la desambiguacion fallaria justo en los casos que existe
para resolver.
"""

from datetime import date

import pytest

from fdekit.decide import Consent, DecideStore, Decision, Meeting
from fdekit.decide.draft import draft_decisions
from fdekit.decide.parse import classify_marker, extract_slots

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


# ------------------------------------------------- el mismo slot canonico


@pytest.mark.parametrize(
    "frase, canonico",
    [
        ("hay que reslotear la clase A", "slotting"),
        ("el slotting de la zona dorada", "slotting"),
        ("hay que reubicar la clase A", "slotting"),
        ("el picking de la ola 2", "picking"),
        ("la preparacion de pedidos de la ola 2", "picking"),
        ("el packing de los pedidos", "packing"),
        ("el embalaje de los pedidos", "packing"),
        ("la reposicion del pasillo 3", "reposicion"),
        ("el replenishment del pasillo 3", "reposicion"),
        ("el conteo ciclico de la clase A", "inventario"),
        ("el cycle count de la clase A", "inventario"),
    ],
)
def test_las_dos_lenguas_dan_el_mismo_slot(frase, canonico):
    """El punto entero. Dos superficies del mismo proceso tienen que colapsar en
    un canonico, o la resolucion de fase 3 los trata como cosas distintas."""
    assert extract_slots(frase).get("proceso") == canonico


def test_la_frase_mixta_real_produce_slots():
    """"El slotting del picking de fast movers" es como se habla de verdad en un
    CD chileno. Antes producia cero slots utiles."""
    slots = extract_slots("hay que revisar el slotting del picking en el CD de Pudahuel")
    assert slots["proceso"] in ("slotting", "picking")
    assert slots["sitio"] == "pudahuel"


def test_el_cutover_y_el_go_live_son_el_mismo_hito():
    """Los dos terminos que mas aparecen en un despliegue y que nadie traduce."""
    assert extract_slots("el cutover es el viernes")["hito"] == "cutover"
    assert extract_slots("el go live es el viernes")["hito"] == "cutover"
    assert extract_slots("la salida a produccion es el viernes")["hito"] == "cutover"


# --------------------------------------------------- marcadores en ingles


@pytest.mark.parametrize(
    "frase",
    [
        "queda decidido: bajamos el corte a las 14:00",
        "it is decided: we move the cutoff to 14:00",
        "we agreed that we move the cutoff to 14:00",
    ],
)
def test_el_marcador_de_decision_funciona_en_las_dos_lenguas(frase):
    """El equipo global tiene la reunion en ingles y el CD la tiene en espanol.
    Un lexico monolingue captura la mitad del proyecto."""
    assert classify_marker(frase).kind == "decision"


def test_el_marcador_en_ingles_llega_hasta_el_borrador():
    """Que el clasificador reconozca la forma no sirve si el borrador no sale."""
    drafts = draft_decisions(
        "It is decided: move the cutoff to 14:00, owner Marcela Perez.",
        ROSTER, HOY, meeting_id="m1",
    )
    assert [d.kind for d in drafts] == ["decision"]


def test_el_compromiso_en_ingles_tambien():
    drafts = draft_decisions(
        "Rodrigo Munoz commits to moving 200 locations by 2026-09-30.",
        ROSTER, HOY, meeting_id="m1",
    )
    assert [d.kind for d in drafts] == ["commitment"]


def test_ninguna_forma_nueva_dispara_sobre_habla_comun():
    """El detector es de precision alta y recall bajo POR CONSTRUCCION. Ampliar
    el lexico es exactamente la operacion que puede romper esa propiedad, y
    romperla es peor que el hueco: un falso positivo entra al registro con cara
    de decision."""
    for frase in (
        "no se decide nada todavia",
        "we should probably move the cutoff",
        "quedamos de vernos la proxima semana",
        "i agree with that",
        "estamos de acuerdo en que hay que mirarlo",
    ):
        assert classify_marker(frase).kind is None, frase


# --------------------------------------- el vocabulario que ve el ASR


def test_el_prompt_de_whisper_lleva_los_terminos_en_ingles():
    """Whisper con `language='es'` degrada notoriamente en frases mixtas. La
    contramedida soportada es el prompt inicial, y solo sirve si ahi estan los
    terminos que el modelo va a tener que reconocer."""
    from fdekit.decide.lexicon import DECISION_VOCAB

    vocab = {v.lower() for v in DECISION_VOCAB}
    for termino in ("cutover", "go live", "slotting", "picking", "fast movers"):
        assert termino in vocab, termino


def test_el_vocabulario_no_tiene_duplicados():
    """Un prompt inicial con repeticiones gasta ventana de contexto del modelo
    en nada."""
    from fdekit.decide.lexicon import DECISION_VOCAB

    bajas = [v.lower() for v in DECISION_VOCAB]
    assert len(bajas) == len(set(bajas))


# ------------------------------- el numero que el ASR transcribio mal


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo",
                        recording_allowed=True, retention_days=90),
        scope="pudahuel",
    ))
    return st


def _con_cita(cita: str, criteria: str) -> Decision:
    from fdekit.decide.schema import Anchor

    return Decision(
        id="D-001", statement="Bajar el corte de pedidos del CD Pudahuel",
        owner="Marcela Perez", date_decided=HOY, criteria=criteria,
        rationale="el transporte sale antes", meeting_id="m1",
        anchor=Anchor(meeting_id="m1", cita_congelada=cita, transcript_sha256="x" * 64),
    )


def test_el_numero_del_criterio_que_no_esta_en_la_cita_se_avisa(store):
    """"El corte es 500" -> "5000" es un error silencioso, de alto costo, y cae
    justo en el campo donde el diseno exige que haya un numero.

    Es un AVISO y no un rechazo: la cita es del canal HABLADA, que es de peor
    calidad que el DECIDIDA por construccion, y bloquear por una diferencia con
    el transcripto le daria autoridad al canal equivocado."""
    d = _con_cita("queda decidido: el corte de pedidos baja a 500 lineas", "5000 lineas")
    avisos = " ".join(d.advisories())
    assert "5000" in avisos
    assert "no aparece" in avisos


def test_el_numero_que_si_esta_en_la_cita_no_avisa(store):
    d = _con_cita("queda decidido: el corte de pedidos baja a 500 lineas", "500 lineas")
    assert d.advisories() == []


def test_sin_cita_no_se_afirma_nada(store):
    """Sin canal HABLADA no hay contra que comparar, y un aviso ahi seria ruido
    permanente en todo el flujo sin audio, que es el flujo canonico."""
    d = _con_cita("", "5000 lineas")
    assert d.advisories() == []


def test_las_fechas_del_criterio_no_disparan_el_aviso(store):
    """El limite declarado de la regla. Un criterio con '2026-09-30' contra una
    cita que dice 'el 30 de septiembre' generaria dos avisos falsos por cada
    decision con plazo — y un aviso que casi siempre es falso es un aviso que
    nadie lee."""
    d = _con_cita(
        "queda decidido: bajamos el corte, a mas tardar el 30 de septiembre",
        "100% cortado antes del 2026-09-30",
    )
    avisos = " ".join(d.advisories())
    assert "2026" not in avisos
    assert "100" in avisos   # este si: es una magnitud que la cita no dice


def test_el_aviso_llega_a_why(store):
    """Un aviso que no se muestra en ningun lado es un campo muerto."""
    from fdekit.decide.query import why

    store.add_decision(_con_cita(
        "queda decidido: el corte de pedidos baja a 500 lineas", "5000 lineas"))
    r = why(store, "D-001")
    assert any("5000" in a for a in r["advertencias"])
