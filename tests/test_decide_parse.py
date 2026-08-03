"""Fase 2 de fdekit.decide: parser de habla espanola y cola de revision.

Es el unico trabajo genuinamente nuevo del sistema, y por lo tanto donde vive
el riesgo. Los tests apuntan a los tres modos de falla que importan:

  - inventar una fecha donde habia una expresion ambigua
  - inventar un dueno donde solo habia un tercero mencionado
  - dejar que un mismo texto alimente dos campos
"""

from datetime import date, datetime, timedelta

import pytest

from fdekit.decide import (
    Consent,
    DecideStore,
    DraftStore,
    Meeting,
    classify_marker,
    draft_decisions,
    expire,
    extract_rationale,
    extract_slots,
    parse_due_date,
    resolve_owner,
    review_queue,
    to_entity,
)
from fdekit.decide.parse import split_statement

# Sabado 1 de agosto de 2026.
REUNION = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


# ------------------------------------------------------------------ fechas


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("para el 2026-09-30", date(2026, 9, 30)),
        ("para el 30 de septiembre", date(2026, 9, 30)),
        ("para el 30 de septiembre de 2027", date(2027, 9, 30)),
        ("antes del 15/09", date(2026, 9, 15)),
        ("para manana", date(2026, 8, 2)),
        ("para pasado manana", date(2026, 8, 3)),
        ("para el lunes", date(2026, 8, 3)),
        ("para el viernes", date(2026, 8, 7)),
        ("plazo fin de mes", date(2026, 8, 31)),
        ("para fin de septiembre", date(2026, 9, 30)),
        ("para antes del 15", date(2026, 8, 15)),
        ("con fecha en dos semanas", date(2026, 8, 15)),
        ("plazo en 10 dias", date(2026, 8, 11)),
        ("para en un mes", date(2026, 9, 1)),
    ],
)
def test_parseo_de_plazos_en_habla_espanola(texto, esperado):
    hit = parse_due_date(texto, REUNION)
    assert hit.value == esperado, hit
    assert hit.role == "due"


def test_el_dia_suelto_que_ya_paso_cae_en_el_mes_siguiente():
    """'antes del 15' un dia 20 significa el 15 del mes que viene. Es la lectura
    que hace cualquier persona."""
    assert parse_due_date("antes del 15", date(2026, 8, 20)).value == date(2026, 9, 15)


def test_el_dia_de_semana_nunca_devuelve_hoy():
    """Un sabado, 'para el sabado' es el sabado que viene, no hoy."""
    assert parse_due_date("para el sabado", REUNION).value == date(2026, 8, 8)


@pytest.mark.parametrize(
    "texto",
    ["lo vemos la proxima semana", "la otra semana", "mas adelante", "cuando se pueda",
     "en unos dias", "el proximo mes"],
)
def test_las_expresiones_ambiguas_no_producen_fecha(texto):
    """Preferimos un hueco explicito a una fecha inventada: el hueco cuesta
    cinco segundos de pregunta, la fecha inventada cuesta un compromiso que
    nadie puede decir que esta atrasado."""
    hit = parse_due_date(texto, REUNION)
    assert hit.value is None
    assert hit.note, "toda ambiguedad tiene que decir por que no se resolvio"


def test_la_fecha_de_revision_no_se_usa_como_plazo():
    """La leccion de `_RE_CADA`: el mismo texto no puede alimentar dos campos.
    'Lo vemos en dos semanas' es revision; usarla como vencimiento produce
    compromisos con plazo inventado."""
    hit = parse_due_date("lo vemos en dos semanas", REUNION)
    assert hit.value is None
    assert hit.role == "review"
    assert "no plazo" in hit.note


def test_plazo_y_revision_en_la_misma_frase_gana_el_plazo():
    hit = parse_due_date("para el 30 de septiembre, y lo revisamos en dos semanas", REUNION)
    assert hit.value == date(2026, 9, 30)
    assert hit.role == "due"


def test_una_fecha_sin_preposicion_baja_la_confianza():
    hit = parse_due_date("cerramos el 30 de septiembre", REUNION)
    assert hit.value == date(2026, 9, 30)
    assert hit.role == "unknown"
    assert hit.confidence < 0.7


def test_fecha_imposible_no_revienta():
    assert parse_due_date("para el 31 de febrero", REUNION).value is None


# ------------------------------------------------------------------ duenos


def test_resuelve_por_nombre_completo():
    hit = resolve_owner("dueno Marcela Perez", ROSTER)
    assert hit.value == "Marcela Perez"
    assert hit.confidence == 1.0


def test_resuelve_por_nombre_de_pila_con_pista_de_dueno():
    for frase in ("dueno Marcela", "lo resuelve Marcela", "queda con Marcela",
                  "Marcela se encarga", "responsable Marcela"):
        assert resolve_owner(frase, ROSTER).value == "Marcela Perez", frase


def test_el_acento_no_importa():
    assert resolve_owner("dueño Fabián", ROSTER).value == "Fabian Soto"


def test_un_tercero_mencionado_no_se_vuelve_dueno():
    """'reasignar la ruta de Fabian, dueno Marcela' — Fabian no es el dueno. Es
    simultaneamente un error de datos y el agujero de privacidad mas grande del
    sistema: un tercero convertido en obligado."""
    hit = resolve_owner("reasignar la ruta de Fabian, dueno Marcela", ROSTER)
    assert hit.value == "Marcela Perez"


@pytest.mark.parametrize("roster", [ROSTER, ("Fabian Soto", "Marcela Perez", "Rodrigo Munoz")])
def test_el_nombre_completo_tampoco_saltea_las_pistas(roster):
    """El match de nombre completo NO puede cortocircuitar la direccion de la
    pista. Si lo hace, el tercero mencionado vuelve a ganar — y con confianza
    1,0, que es peor que perderlo. El roster invertido es el caso que lo
    destapa: sin la regla, gana quien aparece primero en la lista."""
    hit = resolve_owner("reasignar la ruta de Fabian Soto, dueno Marcela Perez", roster)
    assert hit.value == "Marcela Perez"
    assert hit.confidence == 1.0


def test_el_nombre_completo_sin_pista_cerca_no_resuelve():
    hit = resolve_owner("el problema es que Fabian Soto no da abasto de noche", ROSTER)
    assert hit.value is None
    assert hit.candidates == ("Fabian Soto",)
    assert "tercero mencionado" in hit.note


def test_nombre_sin_pista_de_dueno_no_resuelve_pero_deja_candidato():
    hit = resolve_owner("el problema es que Fabian no da abasto en el turno noche", ROSTER)
    assert hit.value is None
    assert hit.candidates == ("Fabian Soto",)
    assert "tercero mencionado" in hit.note


def test_dos_nombres_sin_pista_no_resuelve():
    hit = resolve_owner("lo conversaron Marcela y Rodrigo", ROSTER)
    assert hit.value is None
    assert len(hit.candidates) == 2


def test_nadie_del_roster_nombrado():
    hit = resolve_owner("que lo vea el jefe de bodega", ROSTER)
    assert hit.value is None
    assert "nadie del roster" in hit.note


def test_desambiguacion_por_apellido():
    roster = ("Marcela Perez", "Marcela Soto")
    assert resolve_owner("dueno Marcela Soto", roster).value == "Marcela Soto"
    ambiguo = resolve_owner("dueno Marcela", roster)
    assert ambiguo.value is None
    assert len(ambiguo.candidates) == 2


def test_sin_roster_no_hay_contra_que_resolver():
    assert resolve_owner("dueno Marcela", ()).value is None


# -------------------------------------------------------------- marcadores


@pytest.mark.parametrize(
    "texto,kind",
    [
        ("Queda decidido: reslotear la clase A", "decision"),
        ("queda resuelto que se compra el rack", "decision"),
        ("Queda pendiente: definir el turno de noche", "question"),
        ("Asumimos que el layout no cambia", "assumption"),
        ("Rodrigo se compromete a auditar el maestro", "commitment"),
        ("queda a cargo de Marcela la revision", "commitment"),
    ],
)
def test_detecta_los_marcadores_del_lexico(texto, kind):
    assert classify_marker(texto).kind == kind


def test_una_frase_sin_marcador_no_produce_nada():
    """Recall bajo por construccion. El silencio del sistema mide la disciplina
    del facilitador, y esa es la metrica de supervivencia."""
    assert classify_marker("creo que deberiamos mirar el slotting").kind is None


def test_el_marcador_mas_especifico_gana():
    hit = classify_marker("asumimos que el volumen se mantiene")
    assert hit.marker == "asumimos que"


def test_el_resto_del_marcador_es_el_enunciado():
    hit = classify_marker("Queda decidido: reslotear la clase A a la zona dorada")
    assert hit.rest == "reslotear la clase A a la zona dorada"


def test_extrae_el_porque():
    assert extract_rationale("hacerlo porque el 69% de las visitas son clase A").startswith("el 69%")
    assert extract_rationale("sin razon declarada") == ""


def test_extrae_slots_tipados():
    slots = extract_slots("cambiar el slotting del CD Pudahuel en el turno noche")
    assert slots["proceso"] == "slotting"
    assert slots["sitio"] == "pudahuel"
    assert slots["turno"] == "noche"


def test_las_variantes_producen_el_mismo_slot_canonico():
    """Si 'reslotear' y 'slotting' dieran valores distintos, dos menciones del
    mismo proceso no se reconocerian como la misma cosa y la desambiguacion de
    fase 3 fallaria justo donde tiene que servir."""
    a = extract_slots("hay que reslotear la clase A")
    b = extract_slots("revisar el slotting de la clase A")
    assert a["proceso"] == b["proceso"] == "slotting"


def test_la_variante_mas_larga_gana():
    assert extract_slots("mejorar el cross docking")["proceso"] == "cross_docking"


def test_el_enunciado_se_corta_antes_de_la_clausula_de_dueno():
    """Sin esto el statement se lleva la frase entera y deja de ser una oracion
    imperativa, que es lo que `Decision.validate` exige."""
    assert split_statement("reslotear la clase A. Dueno Marcela") == "reslotear la clase A"
    assert split_statement("auditar el maestro porque hay 25% de error") == "auditar el maestro"


# ---------------------------------------------------------------- borradores


TRANSCRIPTO = (
    "Buenos dias a todos, gracias por venir. "
    "Queda decidido: reslotear la clase A a la zona dorada, dueno Marcela, "
    "para el 30 de septiembre, porque el 69% de las visitas son clase A y solo el 14% "
    "esta en zona dorada. "
    "Rodrigo se compromete a auditar el maestro de SKU, para el 15 de septiembre. "
    "Asumimos que el layout del CD no cambia, lo verificamos antes del 20 de agosto. "
    "Queda pendiente: definir si cerramos el turno de noche, lo resuelve Fabian, "
    "antes del 12 de agosto. "
    "Y bueno, despues vemos lo del transporte."
)


def test_el_parser_captura_los_cuatro_tipos():
    drafts = draft_decisions(TRANSCRIPTO, ROSTER, REUNION, meeting_id="m1")
    assert {d.kind for d in drafts} == {"decision", "commitment", "assumption", "question"}


def test_la_decision_sale_completa_y_lista():
    d = next(x for x in draft_decisions(TRANSCRIPTO, ROSTER, REUNION) if x.kind == "decision")
    assert d.ready
    assert d.fields["owner"] == "Marcela Perez"
    assert d.fields["criteria"] == "a mas tardar 2026-09-30"
    assert "69%" in d.fields["rationale"]
    assert d.fields["slots"]["proceso"] == "slotting"


def test_el_compromiso_nunca_sale_listo():
    """Ni la evidencia de cumplimiento ni la decision padre se infieren: sin la
    primera 'hecho' es una opinion, y sin la segunda es una tarea."""
    c = next(x for x in draft_decisions(TRANSCRIPTO, ROSTER, REUNION) if x.kind == "commitment")
    assert not c.ready
    assert set(c.missing) >= {"evidence_of_done", "decision_id"}
    assert c.fields["owner"] == "Rodrigo Munoz"
    assert c.fields["due"] == "2026-09-15"


def test_el_saludo_y_la_charla_no_generan_nada():
    assert draft_decisions("Buenos dias. Y bueno, despues vemos lo del transporte.",
                           ROSTER, REUNION) == []


def test_la_cola_se_ordena_por_lo_que_falta():
    cola = review_queue(draft_decisions(TRANSCRIPTO, ROSTER, REUNION))
    assert cola
    assert [len(d.missing) for d in cola] == sorted(len(d.missing) for d in cola)


def test_una_decision_sin_dueno_va_a_la_cola_con_la_nota():
    drafts = draft_decisions(
        "Queda decidido: reslotear la clase A, para el 30 de septiembre, porque conviene.",
        ROSTER, REUNION,
    )
    d = drafts[0]
    assert not d.ready
    assert "owner" in d.missing


def test_acepta_segmentos_con_timestamp():
    segs = [
        {"start": 12.5, "text": "Queda decidido: reslotear la clase A, dueno Marcela, "
                                "para el 30 de septiembre, porque conviene mucho"},
        {"start": 40.0, "text": "ok, seguimos"},
    ]
    drafts = draft_decisions(segs, ROSTER, REUNION)
    assert len(drafts) == 1
    assert drafts[0].start_s == 12.5


# ------------------------------------------------------- expiracion y store


def test_los_borradores_expiran_a_las_24_horas():
    """Lo no revisado no existe. Nada de 'el sistema lo capturo igual'."""
    ahora = datetime(2026, 8, 1, 10, 0).astimezone()
    drafts = draft_decisions(TRANSCRIPTO, ROSTER, REUNION, now=ahora)
    vivos, muertos = expire(drafts, ahora + timedelta(hours=23))
    assert not muertos
    vivos, muertos = expire(drafts, ahora + timedelta(hours=25))
    assert not vivos and len(muertos) == len(drafts)


def test_el_draft_store_persiste_y_recarga(tmp_path):
    ds = DraftStore(tmp_path, "m1")
    drafts = draft_decisions(TRANSCRIPTO, ROSTER, REUNION, meeting_id="m1")
    assert ds.append(drafts) == len(drafts)

    recargados = DraftStore(tmp_path, "m1").load()
    assert len(recargados) == len(drafts)
    assert recargados[0].fields == drafts[0].fields
    assert recargados[0].ready == drafts[0].ready


def test_el_borrador_listo_se_convierte_en_entidad_valida(tmp_path):
    st = DecideStore(tmp_path / "d")
    st.add_meeting(Meeting(id="m1", date=REUNION, roster=ROSTER, facilitator="Marcela Perez",
                           consent=Consent(True, "Marcela Perez", "interes_legitimo")))
    d = next(x for x in draft_decisions(TRANSCRIPTO, ROSTER, REUNION, meeting_id="m1")
             if x.kind == "decision")
    obj = st.add_decision(to_entity(d))
    assert obj.id == "D-001"
    assert st.get("D-001").owner == "Marcela Perez"


# ------------------------------ una fecha suelta NO es un plazo (H5, previo)
#
# Los dos salieron de refutar el diseno de H5, y los dos son anteriores a
# cualquier parser de chat: la ruta texto -> borrador ya producia numeros
# plausibles y falsos.


def test_una_fecha_sin_preposicion_de_plazo_no_llena_el_campo():
    """`parse_due_date` YA distinguia el rol —sin preposicion devuelve
    `role="unknown"`, confianza 0,55 y el motivo escrito— pero los cuatro
    constructores de `draft.py` usaban `fecha.value` sin mirarlo. Un campo lleno
    NO entra a `missing`, o sea que no entra a la cola de revision: la regla 1
    rota por un `if` que faltaba.

    "el 3/6 hablamos" es CUANDO hablaron, no un vencimiento.
    """
    from fdekit.decide.draft import draft_decisions

    d = draft_decisions(
        "el 3/6 hablamos y Rodrigo se compromete a mover 200 ubicaciones",
        roster=("Rodrigo",), meeting_date=date(2026, 8, 2))[0]
    assert d.fields["due"] == ""
    assert "due" in d.missing
    assert any("sin preposicion de plazo" in n for n in d.notes)


def test_con_preposicion_de_plazo_si_llena_el_campo():
    """El arreglo no puede romper el caso legitimo."""
    from fdekit.decide.draft import draft_decisions

    d = draft_decisions(
        "Rodrigo se compromete a mover 200 ubicaciones antes del 30/9",
        roster=("Rodrigo",), meeting_date=date(2026, 8, 2))[0]
    assert d.fields["due"] == "2026-09-30"
    assert "due" not in d.missing


def test_la_cabecera_de_chat_ya_no_se_vuelve_el_plazo():
    """El caso que motivo el arreglo. Un export de chat pone una fecha en CADA
    mensaje; el compromiso nacia con el timestamp del mensaje como plazo, en el
    pasado, y `tick` lo marcaba VENCIDO el dia uno."""
    from fdekit.decide.draft import draft_decisions

    d = draft_decisions(
        "03-06-26, 09:15 - Marcela: Rodrigo se compromete a mover 200 ubicaciones",
        roster=("Marcela", "Rodrigo"), meeting_date=date(2026, 8, 2))[0]
    assert d.fields["due"] == ""


def test_la_fecha_ambigua_lo_dice_y_no_sale_ready():
    """`3/6` es 3-jun o 6-mar segun de donde salga el texto, y no hay senal en
    el string para decidir: verificado contra exports reales de WhatsApp, el
    mismo grupo produce los dos ordenes segun la region de cada telefono.

    `13/6` en cambio es inequivoco. Los dos salian con confianza 0,95 y nota
    vacia — esa era la mentira.
    """
    inequivoca = parse_due_date("antes del 13/6", date(2026, 8, 2))
    assert inequivoca.confidence == 0.95 and inequivoca.note == ""

    ambigua = parse_due_date("antes del 3/6", date(2026, 8, 2))
    assert ambigua.confidence < 0.5      # debajo de MIN_CONFIDENCE: no sale ready
    assert "ambigua" in ambigua.note
    assert "mm/dd" in ambigua.note


def test_la_fecha_ambigua_manda_el_borrador_a_la_cola():
    from fdekit.decide.draft import draft_decisions

    d = draft_decisions(
        "Rodrigo se compromete a mover 200 ubicaciones antes del 3/6",
        roster=("Rodrigo",), meeting_date=date(2026, 8, 2))[0]
    assert d.ready is False
    assert any("ambigua" in n for n in d.notes)
