"""H5 — CONFLICTO y NO_DECISION.

Las dos piezas que impiden que el canal asincronico **corrompa** el canal
decidido en vez de alimentarlo. Sin la regla de precedencia, un mensaje de
WhatsApp a las 22:00 da vuelta una decision de comite sin que nadie la mire.
"""

from datetime import date, timedelta

import pytest

from fdekit.decide import Consent, DecideStore, Decision, Meeting, OpenQuestion, agenda, supersede
from fdekit.decide.query import (
    ConflictoAbierto,
    close_meeting,
    declare_conflict,
    resolve_conflicto,
)
from fdekit.decide.store import ValidationError

HOY = date(2026, 8, 1)
R = ("Marcela", "Fabian", "Rodrigo")


def _consent():
    return Consent(granted=True, granted_by="Marcela", basis="interes_legitimo")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(id="comite", date=HOY, roster=R, facilitator="Marcela",
                           consent=_consent()))
    st.add_meeting(Meeting(id="wa-35", date=HOY, roster=R, consent=_consent(),
                           canal="ASINCRONICO"))
    return st


def _dec(st, mid, enunciado, **kw):
    return st.add_decision(Decision(
        id="", statement=enunciado, owner="Marcela", date_decided=HOY,
        criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id=mid, **kw), force=True)


@pytest.fixture
def par(store):
    """Una decision de sala y una de chat que la contradice."""
    sala = _dec(store, "comite", "Consolidar el picking de Pudahuel en una sola ola")
    chat = _dec(store, "wa-35", "Mantener el picking en dos olas por el peak", origen="CHAT")
    return store, sala, chat


# ------------------------------------------------- declarar


def test_la_externa_queda_EN_CONFLICTO_y_la_de_sala_sigue_rigiendo(par):
    """El punto entero de la regla de precedencia: la evidencia mas reciente NO
    gana sola. Hasta que alguien resuelva, lo que rige es lo de la sala."""
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="contradice el corte de olas",
                         today=HOY, apply=True)

    assert r["applied"] is True
    assert st.get(chat.id).status == "EN_CONFLICTO"
    assert st.get(chat.id).en_conflicto_con == sala.id
    assert st.get(sala.id).status == "VIGENTE"      # la de sala no se toca


def test_sin_apply_no_toca_nada(par):
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="x")
    assert r["applied"] is False
    assert st.get(chat.id).status == "VIGENTE"


def test_declarar_exige_motivo(par):
    st, sala, chat = par
    with pytest.raises(ValueError, match="exige un motivo"):
        declare_conflict(st, chat.id, sala.id, today=HOY, apply=True)


def test_el_resolver_sale_del_REGISTRO_y_no_se_inventa(par):
    """Es el dueno de la decision disputada: el unico actor que el sistema puede
    nombrar sin inventar. Un conflicto sin dueno seria el limbo que la regla 1
    prohibe."""
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="contradice", today=HOY, apply=True)
    assert r["resolver"] == st.get(sala.id).owner
    assert st.get(r["question"]).resolver == st.get(sala.id).owner


def test_el_conflicto_NO_mata_los_compromisos_los_enumera(par):
    """`EN_CONFLICTO` es suspension, no muerte. Cancelar los compromisos seria
    decidir el conflicto a favor de la externa por la puerta de atras."""
    from fdekit.decide import Commitment

    st, sala, chat = par
    c = st.add_commitment(Commitment(
        id="", decision_id=sala.id, what="mover 200 ubicaciones", owner="Rodrigo",
        due=HOY + timedelta(days=30), meeting_id="comite",
        evidence_of_done="reporte del WMS"))

    r = declare_conflict(st, chat.id, sala.id, reason="contradice", today=HOY, apply=True)
    assert any(t["id"] == c.id for t in r["triage"])
    assert st.get(c.id).status == "ABIERTO"          # sigue corriendo


def test_una_decision_en_conflicto_no_es_un_padre_muerto(par):
    """No entra a DEAD_DECISION_STATUS: sus compromisos NO son zombis. Un zombi
    es gente ejecutando algo ya revertido; aca nadie revirtio nada."""
    from fdekit.decide.schema import DEAD_DECISION_STATUS, es_zombi
    from fdekit.decide import Commitment

    st, sala, chat = par
    declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    assert "EN_CONFLICTO" not in DEAD_DECISION_STATUS

    c = Commitment(id="C-9", decision_id=chat.id, what="algo", owner="Rodrigo",
                   due=HOY, evidence_of_done="reporte")
    assert es_zombi(c, st.get(chat.id)) is False


def test_no_se_apilan_conflictos_sobre_la_misma_decision(par):
    """Tres enunciados en disputa son DOS conflictos, y hay que verlos por
    separado porque resolver uno cambia el otro."""
    st, sala, chat = par
    otra = _dec(st, "wa-35", "Volver a tres olas los lunes", origen="CHAT")
    declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    with pytest.raises(ConflictoAbierto, match="ya hay un conflicto abierto"):
        declare_conflict(st, otra.id, chat.id, reason="y", today=HOY, apply=True)


# ------------------------------------------------- la agenda


def test_el_conflicto_entra_PRIMERO_en_la_agenda(par):
    """Mientras hay un conflicto abierto no se sabe cual decision rige, y
    cualquier otro punto se discute sobre arena."""
    st, sala, chat = par
    declare_conflict(st, chat.id, sala.id, reason="contradice el corte", today=HOY, apply=True)

    ag = agenda(st, "comite", today=HOY)
    assert len(ag.conflicts) == 1
    assert ag.is_empty is False
    md = ag.to_markdown()
    assert "CONFLICTO ABIERTO — primero esto" in md
    assert md.index("CONFLICTO ABIERTO") < md.index("Compromisos vencidos") if \
        "Compromisos vencidos" in md else True


# ------------------------------------------------- supersede

def test_no_se_puede_superar_algo_en_conflicto(par):
    """Superar mientras el conflicto esta abierto lo decide de costado, sin que
    nadie lo haya resuelto ni quede escrito por que."""
    st, sala, chat = par
    declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    with pytest.raises(ConflictoAbierto, match="EN_CONFLICTO"):
        supersede(st, sala.id, chat.id, reason="y", today=HOY, apply=True)


# ------------------------------------------------- resolver


def test_gana_sala_revierte_la_externa(par):
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    resolve_conflicto(st, r["question"], "GANA_SALA", reason="el peak ya paso",
                      today=HOY, apply=True)
    assert st.get(chat.id).status == "REVERTIDA"
    assert st.get(sala.id).status == "VIGENTE"
    assert st.get(r["question"]).status == "RESUELTA"


def test_gana_externa_pasa_por_supersede_con_su_triage(par):
    """Por la puerta de adelante: cambiar el estado a mano se saltearia la
    enumeracion de referencias que `supersede` existe para dar."""
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    out = resolve_conflicto(st, r["question"], "GANA_EXTERNA",
                            reason="el peak se extendio", today=HOY, apply=True)
    assert out["supersede"]["applied"] is True
    assert st.get(sala.id).status == "SUPERADA"
    assert st.get(chat.id).status == "VIGENTE"


def test_coexisten_porque_la_contradiccion_suele_ser_aparente(par):
    """Dos decisiones sobre sitios o turnos distintos que se leyeron como una.
    Sin esta salida la gente resuelve cualquier cosa con tal de destrabar."""
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    resolve_conflicto(st, r["question"], "COEXISTEN",
                      reason="una es Pudahuel y la otra el CD de Renca", today=HOY, apply=True)
    assert st.get(chat.id).status == "VIGENTE"
    assert st.get(sala.id).status == "VIGENTE"


def test_resolver_exige_motivo_y_resolucion_valida(par):
    st, sala, chat = par
    r = declare_conflict(st, chat.id, sala.id, reason="x", today=HOY, apply=True)
    with pytest.raises(ValueError, match="resolucion invalida"):
        resolve_conflicto(st, r["question"], "LO_QUE_SEA", reason="y", apply=True)
    with pytest.raises(ValueError, match="exige un motivo"):
        resolve_conflicto(st, r["question"], "GANA_SALA", today=HOY, apply=True)


# ------------------------------------------------- NO_DECISION


def _pregunta(st, mid="comite"):
    return st.add_question(OpenQuestion(
        id="", question="cortamos la ola de las 14:00?", resolver="Marcela",
        resolve_by=HOY + timedelta(days=30), meeting_id=mid), force=True)


def test_el_primer_aplazamiento_no_es_una_no_decision(store):
    q = _pregunta(store)
    r = close_meeting(store, "comite", today=HOY, apply=True)
    assert q.id in r["aplazadas"] and r["no_decision"] == []
    assert store.get(q.id).es_no_decision is False


def test_a_la_SEGUNDA_sesion_deja_de_ser_un_punto_pendiente(store):
    """La decision por inaccion: la mas frecuente en operaciones y la mas
    invisible. Nadie decide, el status quo sigue, y no queda objeto."""
    q = _pregunta(store)
    store.add_meeting(Meeting(id="comite-2", date=HOY + timedelta(days=7), roster=R,
                              facilitator="Marcela", consent=_consent()))
    close_meeting(store, "comite", today=HOY, apply=True)
    r = close_meeting(store, "comite-2", today=HOY + timedelta(days=7), apply=True)

    assert q.id in r["no_decision"]
    assert store.get(q.id).es_no_decision is True
    assert "la de no decidir" in r["nota"]


def test_cerrar_dos_veces_la_misma_sesion_no_cuenta_dos_veces(store):
    """"Segunda vez" es respecto de SESIONES DISTINTAS."""
    q = _pregunta(store)
    close_meeting(store, "comite", today=HOY, apply=True)
    r = close_meeting(store, "comite", today=HOY, apply=True)
    assert r["aplazadas"] == []
    assert store.get(q.id).es_no_decision is False


def test_una_no_decision_exige_el_costo_de_seguir_sin_decidir(store):
    """Es lo que convierte el silencio en un objeto: sin eso vuelve a ser un
    punto que se arrastra."""
    q = _pregunta(store)
    q.aplazada_en = ["comite", "comite-2"]
    with pytest.raises(ValidationError, match="costo de seguir sin decidir"):
        store.save(q)

    q.costo_de_no_decidir = "seguimos con 2 turnos de pick: 40 h-persona extra por semana"
    assert store.save(q) == []


def test_si_el_costo_no_se_puede_cuantificar_va_a_la_cola_con_dueno(store):
    """La valvula de la regla 1. Inventar un numero seria peor que el hueco, y
    dejar el hueco callado seria peor que las dos cosas."""
    q = _pregunta(store)
    q.aplazada_en = ["comite", "comite-2"]
    q.costo_en_cola = "Fabian lo estima con el log del WMS antes del 15-09"
    assert store.save(q) == []
