"""`supersede` — el analogo de `rename`, y el unico donde la analogia se rompe.

En codigo, renombrar arregla las referencias. Aca, cambiar el alcance de una
decision **no arregla los compromisos: los invalida**. Lo maximo honesto que
puede hacer es enumerarlos y forzar triage humano; prometer propagacion
automatica se descubre la primera vez que se usa y quema la confianza en todo
el sistema.

Estos tests fijan las cuatro reglas duras del diseno:

  1. escribe punteros en ambos sentidos y no borra nada
  2. NO propaga: lista para triage
  3. NO escribe un alias con el statement viejo (fabricaria colisiones)
  4. la cadena se puede seguir hasta la decision que rige hoy
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
    head_of,
    safe_close,
    supersede,
    tick,
    why,
)
from fdekit.decide.eventlog import build_event_log
from fdekit.decide.parse import extract_slots
from fdekit.decide.metrics import orphans_and_zombies
from fdekit.decide.resolve import AliasStore, confirm
from fdekit.decide.schema import hist_line
from fdekit.decide.store import ValidationError

HOY = date(2026, 8, 1)
ROSTER = ("Marcela", "Fabian", "Rodrigo")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator="Marcela",
        consent=Consent(granted=True, granted_by="Marcela", basis="interes_legitimo"),
        scope="pudahuel",
    ))
    return st


def dec(store, statement):
    criteria = "distancia media ponderada bajo 35 m antes del 30-09"
    return store.add_decision(Decision(
        id="", statement=statement, owner="Marcela", date_decided=HOY,
        criteria=criteria,
        rationale="el 69% de las visitas son clase A", meeting_id="m1", scope="pudahuel",
        # Poblados como los puebla la siembra. Sin slots el simbolo no se puede
        # aliasear, y este archivo tiene un test que lo aliasea.
        slots=extract_slots(statement + " " + criteria),
    ))


VIEJA = "Reslotear la clase A a la zona dorada del CD Pudahuel"
NUEVA = "Reslotear clase A y B a la zona dorada, con cambio de racks"
TERCERA = "Reslotear por rotacion medida y no por clase ABC fija"


# ------------------------------------------------------- punteros y estado


def test_escribe_punteros_en_ambos_sentidos(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    r = supersede(store, a.id, b.id, reason="entraron racks nuevos", apply=True, today=HOY)

    assert r["applied"] is True
    assert store.get(a.id).status == "SUPERADA"
    assert store.get(a.id).superseded_by == b.id
    assert a.id in store.get(b.id).supersedes


def test_sin_apply_es_solo_el_reporte_de_triage(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    r = supersede(store, a.id, b.id, reason="x")
    assert r["applied"] is False
    assert store.get(a.id).status == "VIGENTE"
    assert "no se toco nada" in r["nota"]


def test_con_apply_exige_motivo(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    with pytest.raises(ValueError, match="exige un motivo"):
        supersede(store, a.id, b.id, apply=True)


def test_no_borra_nada(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    vieja = store.get(a.id)
    assert vieja.statement == VIEJA
    assert vieja.rationale
    assert vieja.criteria


# ----------------------------------------------------------- no propaga


def test_no_propaga_enumera_para_triage(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    store.add_commitment(Commitment(
        id="", decision_id=a.id, what="ejecutar el reslotting de pasillos 1 a 6",
        owner="Rodrigo", due=date(2026, 9, 1), evidence_of_done="reporte del WMS",
    ))
    store.add_assumption(Assumption(
        id="", decision_id=a.id, statement="el layout no cambia hasta septiembre",
        check_by=date(2026, 9, 1), source="jefe de operaciones",
    ))

    r = supersede(store, a.id, b.id, reason="entraron racks", apply=True, today=HOY)

    assert {"compromiso", "supuesto"} <= {t["tipo"] for t in r["triage"]}
    assert r["referencias_a_resolver"] >= 2
    assert any("lo invalida" in t["accion"] for t in r["triage"])
    # Lo importante: el compromiso sigue colgando de la vieja. No se reasigno.
    assert store.get("C-001").decision_id == a.id


def test_enumera_tambien_dependientes_y_preguntas(store):
    from fdekit.decide import OpenQuestion

    a, b = dec(store, VIEJA), dec(store, NUEVA)
    store.add_decision(Decision(
        id="", statement="Comprar racks para la zona dorada ampliada", owner="Marcela",
        date_decided=HOY, criteria="antes del 30-09", rationale="hace falta espacio",
        meeting_id="m1", depends_on=[a.id],
    ))
    store.add_question(OpenQuestion(
        id="", question="ampliamos la zona dorada?", resolver="Marcela",
        resolve_by=date(2026, 9, 1), blocks=[a.id], meeting_id="m1",
    ))
    r = supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    assert {"decision_dependiente", "pregunta"} <= {t["tipo"] for t in r["triage"]}


def test_declara_explicitamente_que_no_propaga(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    r = supersede(store, a.id, b.id, reason="racks")
    assert "no reasigna nada" in r["nota_no_propaga"]


# -------------------------------------------------- no fabrica alias


def test_no_escribe_un_alias_con_el_statement_viejo(store):
    """Fabricaria colisiones a proposito. El statement viejo va a
    `historial_statements`: consultable, pero NO indice de resolucion."""
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    supersede(store, a.id, b.id, reason="entraron racks", apply=True, today=HOY)

    assert AliasStore(store.root).load() == []
    hist = " ".join(store.get(a.id).historial_statements)
    # El puntero a la nueva y el statement viejo quedan los dos en el historial.
    # Se afirma el contenido, no el formato exacto de la linea: el formato es un
    # contrato con `eventlog` y lo fija `test_la_supersesion_entra_al_event_log`.
    assert b.id in hist
    assert "zona dorada del CD Pudahuel" in hist


def test_lista_los_alias_vigentes_pero_no_los_toca(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    astore = AliasStore(store.root)
    confirm(astore, "lo del slotting", a, "pudahuel", "Marcela", HOY)

    r = supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    assert any(t["tipo"] == "alias" for t in r["triage"])
    assert astore.load()[0].estado == "VIGENTE"


# ------------------------------------------------------------- la cadena


def test_la_cadena_lleva_a_la_que_rige_hoy(store):
    """La friccion que nombra el diseno: 'las dos personas citando versiones
    distintas'. Con la cadena escrita deja de ser discusion y pasa a consulta."""
    a, b, c = dec(store, VIEJA), dec(store, NUEVA), dec(store, TERCERA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    supersede(store, b.id, c.id, reason="la rotacion mide mejor", apply=True, today=HOY)

    h = head_of(store, a.id)
    assert h["head"] == c.id
    assert h["cadena"] == [a.id, b.id, c.id]
    assert h["saltos"] == 2
    assert h["statement_vigente"] == TERCERA


def test_la_cabeza_de_una_vigente_es_ella_misma(store):
    a = dec(store, VIEJA)
    h = head_of(store, a.id)
    assert h["head"] == a.id and h["saltos"] == 0 and h["vigente"] is False


def test_why_de_una_superada_dice_cual_rige_hoy(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)

    r = why(store, a.id)
    assert r["status"] == "SUPERADA"
    assert r["superseded_by"] == b.id
    assert r["vigente_hoy"] == b.id
    assert why(store, b.id)["superseded_by"] is None


# ------------------------------------------------------------- guardias


def test_no_se_puede_superar_una_ya_superada(store):
    """Hay que superar la que rige, no una version vieja de la cadena."""
    a, b, c = dec(store, VIEJA), dec(store, NUEVA), dec(store, TERCERA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    with pytest.raises(ValueError, match=f"La que rige hoy es {b.id}"):
        supersede(store, a.id, c.id, reason="otra cosa", apply=True)


def test_no_se_puede_superar_con_una_decision_muerta(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    safe_close(store, b.id, apply=True, reason="se cayo el proyecto", today=HOY)
    with pytest.raises(ValueError, match="no puede reemplazar a nadie"):
        supersede(store, a.id, b.id, reason="x", apply=True)


def test_dar_marcha_atras_choca_con_la_guardia_de_decision_muerta(store):
    """Intentar b -> a despues de a -> b no llega al chequeo de ciclo: lo frena
    antes la guardia de 'a esta SUPERADA'. Es el mejor de los dos errores."""
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    with pytest.raises(ValueError, match="no puede reemplazar a nadie"):
        supersede(store, b.id, a.id, reason="volver atras", apply=True)


def test_rechaza_el_ciclo_que_deja_una_edicion_a_mano(store):
    """El ciclo real solo llega por un archivo editado a mano — escenario
    legitimo, porque el diseno hace los archivos editables a proposito. Un
    puntero escrito sin su contraparte deja `head_of` girando en redondo."""
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    b.superseded_by = a.id  # puntero a mano, sin marcar a como SUPERADA
    store.save(b)

    with pytest.raises(ValueError, match="ciclo"):
        supersede(store, a.id, b.id, reason="racks", apply=True)


def test_head_of_no_gira_en_redondo_ante_un_ciclo(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    a.superseded_by, b.superseded_by = b.id, a.id
    store.save(a)
    store.save(b)

    h = head_of(store, a.id)
    assert h["head"] is None
    assert "ciclo" in h["error"]


def test_una_decision_no_se_supera_a_si_misma(store):
    a = dec(store, VIEJA)
    with pytest.raises(ValueError, match="a si misma"):
        supersede(store, a.id, a.id, reason="x")


def test_una_decision_inexistente_falla(store):
    a = dec(store, VIEJA)
    with pytest.raises(KeyError):
        supersede(store, a.id, "D-999", reason="x")


# ------------------------------------------- interaccion con el resto


def test_tick_marca_zombi_lo_que_nadie_retrio(store):
    """`supersede` pregunta, `tick` denuncia. Si el triage no se hizo, el
    compromiso abierto colgando de una SUPERADA es gente ejecutando algo que ya
    no rige — un bug real y hoy estructuralmente invisible."""
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    store.add_commitment(Commitment(
        id="", decision_id=a.id, what="ejecutar el reslotting de pasillos 1 a 6",
        owner="Rodrigo", due=date(2026, 12, 1), evidence_of_done="reporte del WMS",
    ))
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)

    r = tick(store, HOY)
    assert r["zombis"] == ["C-001"]
    assert store.get("C-001").status == "ZOMBI"


def test_safe_close_sigue_bloqueando_una_superada_con_cosas_vivas(store):
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    store.add_assumption(Assumption(
        id="", decision_id=a.id, statement="el layout no cambia hasta septiembre",
        check_by=date(2026, 9, 1), source="jefe",
    ))
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)
    assert safe_close(store, a.id)["closed"] is False


# ------------------------------- lo que el registro le cuenta a la medicion
#
# Los tres tests de abajo fijan reglas que el sistema violaba en silencio. Los
# tres bugs eran de la misma familia: la misma regla escrita dos veces, en dos
# archivos, sostenida por una convencion — y la convencion se rompio sin que
# nada fallara.


@pytest.mark.parametrize(
    "operacion, actividad",
    [("supersede", "SUPERADA"), ("safe_close", "REVERTIDA")],
)
def test_toda_transicion_de_estado_entra_al_event_log(store, operacion, actividad):
    """El event log es la unica fuente de la fecha en que una decision cambio.

    `supersede` escribia `"SUPERADA por D-002: motivo"` —el ID metido entre el
    estado y los dos puntos— y `eventlog._RE_HIST` no la reconocia. Ninguna
    supersesion aparecia en `variants`, `rework_summary`, `touches_to_decide` ni
    `lifecycle_rework`. No fallaba: el log salia corto y perfectamente creible,
    y `supersede` es la operacion central del diseno.

    Parametrizado a proposito: la regla no es "supersede funciona", es que
    **toda** operacion que cambia el estado de una decision queda visible. El
    proximo estado que se agregue tiene que sumarse aca.
    """
    a = dec(store, VIEJA)
    if operacion == "supersede":
        b = dec(store, NUEVA)
        supersede(store, a.id, b.id, reason="entraron racks nuevos", apply=True, today=HOY)
    else:
        safe_close(store, a.id, apply=True, reason="se revirtio en comite", today=HOY)

    log = build_event_log(store)
    assert store.get(a.id).status == actividad
    assert actividad in set(log.df["activity"])
    fila = log.df[(log.df["case_id"] == a.id) & (log.df["activity"] == actividad)]
    assert len(fila) == 1
    assert fila.iloc[0]["timestamp"].date() == HOY


def test_la_anotacion_en_minusculas_no_genera_un_evento(store):
    """`supersede` guarda tambien el statement viejo. Es texto para humanos y no
    debe volverse una actividad del ciclo de vida: si lo fuera, cada supersesion
    inventaria un evento con nombre arbitrario en las variantes."""
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    supersede(store, a.id, b.id, reason="racks", apply=True, today=HOY)

    hist = store.get(a.id).historial_statements
    assert any(l.startswith(f"{HOY.isoformat()} statement al momento") for l in hist)
    assert set(build_event_log(store).df["activity"]) <= {"DECIDIDA", "SUPERADA"}


def test_hist_line_rechaza_un_estado_que_el_lector_no_veria(store):
    """El guardia del formato. Sin el, el proximo escritor repite el bug."""
    assert hist_line("2026-08-01", "SUPERADA", "por D-002") == "2026-08-01 SUPERADA: por D-002"
    with pytest.raises(ValueError, match="historial invalida"):
        hist_line("2026-08-01", "SUPERADA por D-002", "motivo")
    with pytest.raises(ValueError, match="historial invalida"):
        hist_line("01-08-2026", "SUPERADA", "motivo")


def test_tick_y_el_tablero_coinciden_sobre_que_es_un_zombi(store):
    """La regla estaba implementada dos veces y ya divergia.

    `tick` solo promovia ABIERTO -> ZOMBI; `orphans_and_zombies` contaba tambien
    los VENCIDO. Un compromiso que vencio **antes** de que su decision fuera
    superada quedaba VENCIDO para siempre en el registro mientras el tablero lo
    reportaba zombi: dos numeros para la misma pregunta.
    """
    a, b = dec(store, VIEJA), dec(store, NUEVA)
    c = store.add_commitment(Commitment(
        id="", decision_id=a.id, what="mover 200 ubicaciones", owner="Rodrigo",
        due=date(2026, 7, 1), evidence_of_done="reporte del WMS",
    ))
    tick(store, today=HOY, apply=True)
    assert store.get(c.id).status == "VENCIDO"   # vencio ANTES de la supersesion

    supersede(store, a.id, b.id, reason="racks nuevos", apply=True, today=HOY)
    tick(store, today=date(2026, 8, 2), apply=True)

    assert store.get(c.id).status == "ZOMBI"
    assert c.id in orphans_and_zombies(store)["zombis"]


def test_registrar_dos_veces_la_misma_reunion_no_pisa_el_roster(store):
    """El roster es el scope lexico: la unica pieza de determinismo del diseno.

    `add_meeting` usaba `save()`, que es `write_text` sin modo exclusivo. Volver
    a registrar el mismo id reemplazaba la reunion entera —roster incluido— sin
    aviso, y con eso la validacion de dueno de todo lo ya colgado pasaba a
    correr contra una lista de gente que no estuvo.
    """
    otra = Meeting(
        id="m1", date=HOY, roster=("Ajeno", "Distinto"), facilitator="Ajeno",
        consent=Consent(granted=True, granted_by="Ajeno", basis="contrato"),
    )
    with pytest.raises(ValidationError, match="ya esta registrada"):
        store.add_meeting(otra)
    assert store.get_meeting("m1").roster == ROSTER

    # Corregir un roster mal tipeado es un caso real, pero es explicito.
    store.add_meeting(otra, overwrite=True)
    assert store.get_meeting("m1").roster == ("Ajeno", "Distinto")
