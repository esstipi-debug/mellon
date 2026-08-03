"""Fase 1 de fdekit.decide.

Los tests no verifican que el codigo corra: verifican las reglas que hacen que
el registro no mienta. Si alguna afloja, el sistema pasa a ser una minuta con
mas ceremonia.
"""

from datetime import date, timedelta

import pytest

from fdekit.decide import (
    Assumption,
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
    OpenQuestion,
    PromotionBudgetExceeded,
    agenda,
    implementations,
    parse_date,
    referencing,
    safe_close,
    supersede,
    tick,
    why,
)
from fdekit.decide.frontmatter import FrontMatterError, dumps, loads
from fdekit.decide.store import ValidationError

HOY = date(2026, 8, 1)
ROSTER = ("Marcela", "Fabian", "Rodrigo")


def consent() -> Consent:
    return Consent(granted=True, granted_by="Marcela", basis="interes_legitimo")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(
        Meeting(
            id="2026-08-01-comite",
            date=HOY,
            roster=ROSTER,
            consent=consent(),
            facilitator="Marcela",
        )
    )
    return st


def mk_decision(**kw) -> Decision:
    base = dict(
        id="",
        statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela",
        date_decided=HOY,
        criteria="distancia media ponderada bajo 35 m antes del 30-09",
        rationale="el 69% de las visitas son clase A y solo el 14% esta en zona dorada",
        meeting_id="2026-08-01-comite",
    )
    base.update(kw)
    return Decision(**base)


# ------------------------------------------------------------- front-matter


def test_frontmatter_ida_y_vuelta():
    data = {"id": "D-001", "n": 3, "ok": True, "nada": None, "lista": ["a", "b"], "d": {"x": 1}}
    got, body = loads(dumps(data, "cuerpo"))
    assert got == data
    assert body == "cuerpo"


def test_frontmatter_soporta_acentos_y_saltos():
    data = {"t": "decisión con\nsalto y ñ"}
    assert loads(dumps(data))[0] == data


def test_frontmatter_claves_ordenadas_para_diffs_estables():
    txt = dumps({"z": 1, "a": 2, "m": 3})
    assert txt.index("a:") < txt.index("m:") < txt.index("z:")


def test_frontmatter_falla_fuerte_ante_edicion_a_mano_invalida():
    """Estos archivos se editan a mano a proposito. Un parseo silencioso que
    devuelve datos equivocados es peor que un error."""
    with pytest.raises(FrontMatterError, match="no es JSON valido"):
        loads("---\nnombre: Marcela\n---\n")  # falta comillas
    with pytest.raises(FrontMatterError, match="sin cierre"):
        loads("---\na: 1\n")
    with pytest.raises(FrontMatterError, match="no empieza"):
        loads("a: 1\n")
    with pytest.raises(FrontMatterError, match="clave repetida"):
        loads('---\na: 1\na: 2\n---\n')
    with pytest.raises(FrontMatterError, match="indentacion"):
        loads('---\na:\n  b: 1\n---\n')


# ----------------------------------------------------------- validaciones


def test_decision_valida_no_tiene_problemas():
    assert mk_decision().validate(ROSTER) == []


def test_rechaza_intencion_de_decidir_disfrazada_de_decision():
    """'evaluar si conviene X' no es una decision: es la intencion de decidir
    mas adelante. Es como el registro empieza a mentir."""
    d = mk_decision(statement="evaluar si conviene reslotear la clase A")
    assert any("intencion de decidir" in i for i in d.validate(ROSTER))


def test_rechaza_criterio_sin_numero_ni_predicado():
    d = mk_decision(criteria="que funcione mejor que ahora")
    assert any("no contiene un numero" in i for i in d.validate(ROSTER))


def test_acepta_criterio_con_predicado_verificable_sin_numero():
    d = mk_decision(criteria="sin excepciones de ubicacion en el turno de manana")
    assert not any("no contiene un numero" in i for i in d.validate(ROSTER))


def test_rechaza_dueno_fuera_del_roster():
    """El roster es el scope lexico: es lo que hace deterministica la
    resolucion de duenos, y es la unica pieza que Serena obtiene del compilador
    y aca hay que declarar."""
    d = mk_decision(owner="Alguien")
    assert any("no esta en el roster" in i for i in d.validate(ROSTER))


def test_rechaza_decision_sin_rationale():
    assert any("sin rationale" in i for i in mk_decision(rationale="").validate(ROSTER))


def test_rechaza_pregunta_como_decision():
    d = mk_decision(statement="conviene reslotear la clase A este trimestre?")
    assert any("es una pregunta" in i for i in d.validate(ROSTER))


def test_compromiso_huerfano_es_una_tarea_no_un_compromiso():
    c = Commitment(id="C-001", decision_id="", what="medir la linea base", owner="Fabian",
                   due=HOY, evidence_of_done="planilla en el repo")
    assert any("huerfano" in i for i in c.validate(ROSTER))


def test_compromiso_sin_evidencia_se_rechaza():
    c = Commitment(id="C-001", decision_id="D-001", what="medir la linea base",
                   owner="Fabian", due=HOY)
    assert any("evidencia" in i for i in c.validate(ROSTER))


def test_fecha_relativa_se_rechaza_con_mensaje_util():
    with pytest.raises(ValueError, match="no absoluta"):
        parse_date("el viernes")


def test_reapertura_sin_dato_nuevo_se_rechaza():
    """Para reabrir hay que traer un numero, no una opinion."""
    q = OpenQuestion(id="Q-001", question="reabrimos el slotting?", resolver="Marcela",
                     resolve_by=HOY, reopen_of="D-001", new_evidence="creo que no funciono")
    assert any("dato nuevo" in i for i in q.validate(ROSTER))

    q.new_evidence = "la distancia media subio a 52 m en julio"
    assert not any("dato nuevo" in i for i in q.validate(ROSTER))


def test_meeting_exige_consentimiento_en_el_constructor():
    """Es la unica pieza de cumplimiento que no se puede retrofitear."""
    with pytest.raises(ValueError, match="requiere `consent`"):
        Meeting(id="x", date=HOY, roster=ROSTER, consent=None)


def test_meeting_exige_roster():
    with pytest.raises(ValueError, match="sin roster"):
        Meeting(id="x", date=HOY, roster=(), consent=consent())


def test_grabar_sin_politica_de_retencion_se_marca():
    c = Consent(granted=True, granted_by="M", basis="interes_legitimo", recording_allowed=True)
    assert any("retencion" in i for i in c.validate())


def test_audio_sin_permiso_de_grabar_se_marca():
    m = Meeting(id="x", date=HOY, roster=ROSTER, consent=consent(),
                facilitator="Marcela", audio_ref="a.m4a")
    assert any("no permite grabar" in i for i in m.validate())


# ------------------------------------------------------------------ store


def test_el_store_se_niega_a_persistir_algo_invalido(store):
    with pytest.raises(ValidationError, match="Decision invalido"):
        store.add_decision(mk_decision(criteria="que quede mejor"))
    assert store.decisions() == []


def test_force_permite_persistir_igual(store):
    store.add_decision(mk_decision(criteria="que quede mejor"), force=True)
    assert len(store.decisions()) == 1


def test_ids_monotonos_y_persistencia_ida_y_vuelta(store):
    a = store.add_decision(mk_decision())
    b = store.add_decision(mk_decision(statement="Nivelar la liberacion de olas contra la dotacion"))
    assert (a.id, b.id) == ("D-001", "D-002")

    leida = store.get("D-001")
    assert leida.statement == a.statement
    assert leida.date_decided == HOY
    assert leida.owner == "Marcela"


def test_presupuesto_de_siete_promociones_por_reunion(store):
    for i in range(7):
        store.add_decision(mk_decision(statement=f"Decision numero {i} sobre el slotting del CD"))
    with pytest.raises(PromotionBudgetExceeded, match="minuta hibrida"):
        store.add_decision(mk_decision(statement="La octava decision de esta misma reunion"))


def test_el_presupuesto_es_por_reunion_no_global(store):
    store.add_meeting(Meeting(id="2026-08-08-comite", date=date(2026, 8, 8), roster=ROSTER,
                              consent=consent(), facilitator="Marcela"))
    for i in range(7):
        store.add_decision(mk_decision(statement=f"Decision {i} del comite de agosto uno"))
    otra = store.add_decision(
        mk_decision(statement="Decision de la reunion siguiente", meeting_id="2026-08-08-comite")
    )
    assert otra.id == "D-008"


def test_compromiso_contra_decision_inexistente_falla(store):
    with pytest.raises(KeyError):
        store.add_commitment(Commitment(id="", decision_id="D-999", what="algo que hacer",
                                        owner="Fabian", due=HOY, evidence_of_done="x"))


def test_campo_desconocido_en_el_archivo_falla_al_leer(store, tmp_path):
    store.add_decision(mk_decision())
    p = tmp_path / "decide" / "decisions" / "D-001.md"
    p.write_text(p.read_text(encoding="utf-8").replace("---\n", '---\ninventado: 1\n', 1), encoding="utf-8")
    with pytest.raises(ValidationError, match="campos desconocidos"):
        store.decisions()


def test_indice_es_derivado_y_regenerable(store):
    store.add_decision(mk_decision())
    idx = store.rebuild_index()
    assert idx["decisions"][0]["id"] == "D-001"
    (store.root / "index.json").unlink()
    assert len(store.decisions()) == 1  # ninguna lectura depende del indice


def test_git_commit_no_levanta_fuera_de_un_repo(store):
    assert isinstance(store.git_commit("prueba"), str)


# ----------------------------------------------------------------- agenda


def test_agenda_vacia_propone_cancelar(store):
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert ag.is_empty
    assert ag.verdict == "proponer cancelar"
    assert "No hay nada que decidir" in ag.to_markdown()


def test_agenda_lista_compromisos_vencidos_por_atraso(store):
    store.add_decision(mk_decision())
    store.add_commitment(Commitment(id="", decision_id="D-001", what="medir la linea base",
                                    owner="Fabian", due=date(2026, 7, 1),
                                    evidence_of_done="planilla en el repo"))
    store.add_commitment(Commitment(id="", decision_id="D-001", what="auditar el maestro",
                                    owner="Rodrigo", due=date(2026, 7, 25),
                                    evidence_of_done="csv de auditoria"))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert not ag.is_empty
    assert [c.id for c, _ in ag.overdue_commitments] == ["C-001", "C-002"]  # mas atrasado primero
    assert ag.overdue_commitments[0][1] == 31


def test_gate_rechaza_pregunta_sin_resolver_en_el_roster(store):
    store.add_question(OpenQuestion(id="", question="aprobamos el presupuesto?",
                                    resolver="Externo", resolve_by=HOY))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert ag.open_questions == []
    assert "no esta en el roster" in ag.gate_rejections[0]["reason"]


def test_gate_rechaza_pregunta_no_cerrable(store):
    """'como lo hacemos?' es una charla con signo de interrogacion."""
    store.add_question(OpenQuestion(id="", question="como mejoramos el picking?",
                                    resolver="Marcela", resolve_by=HOY))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert ag.open_questions == []
    assert "no admite cierre" in ag.gate_rejections[0]["reason"]


def test_gate_agenda_el_dato_bloqueante_no_el_tema(store):
    """Si falta el dato que bloquea, no se agenda el tema: se agenda obtener el
    dato. El bucle no se mide despues — no se produce."""
    store.add_question(OpenQuestion(id="", question="cerramos el turno de noche?",
                                    resolver="Marcela", resolve_by=HOY, blocks=[]))
    store.add_question(OpenQuestion(id="", question="cual fue el volumen real de julio?",
                                    resolver="Rodrigo", resolve_by=HOY, blocks=["Q-001"]))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    ids = [q.id for q in ag.open_questions]
    assert "Q-001" not in ids
    rej = next(r for r in ag.gate_rejections if r["id"] == "Q-001")
    assert "bloqueada por Q-002" in rej["reason"]
    assert "agendar la obtencion del dato" in rej["action"]


def test_gate_deja_pasar_una_pregunta_cerrable_con_dueno(store):
    store.add_question(OpenQuestion(id="", question="aprobamos el reslotting de la zona B?",
                                    resolver="Marcela", resolve_by=date(2026, 8, 15)))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert [q.id for q in ag.open_questions] == ["Q-001"]
    assert ag.verdict == "reunion justificada"


def test_la_pregunta_que_vencio_sin_respuesta_no_desaparece(store):
    """El bucle hecho visible. Si al expirar saliera de la agenda, el sistema
    recomendaria cancelar una reunion que justamente tenia algo que resolver, y
    el bucle seguiria corriendo invisible — que es el problema entero."""
    store.add_question(OpenQuestion(id="", question="cerramos el turno de noche?",
                                    resolver="Marcela", resolve_by=date(2026, 7, 20)))
    futuro = date(2026, 8, 25)
    tick(store, futuro)
    assert store.get("Q-001").status == "EXPIRADA"

    ag = agenda(store, "2026-08-01-comite", today=futuro)
    assert not ag.is_empty
    assert ag.verdict == "reunion justificada"
    q, dias = ag.expired_questions[0]
    assert q.id == "Q-001" and dias == 36
    assert "vencieron sin respuesta" in ag.to_markdown()


def test_solicitud_de_reapertura_va_a_su_propio_bloque(store):
    store.add_decision(mk_decision())
    store.add_question(OpenQuestion(id="", question="reabrimos D-001?", resolver="Marcela",
                                    resolve_by=date(2026, 8, 15), reopen_of="D-001",
                                    new_evidence="la distancia media subio a 52 m"))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert [q.id for q in ag.reopen_requests] == ["Q-001"]


def test_supuesto_sin_fuente_aparece_como_aviso_no_bloquea(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001",
                                    statement="el volumen se mantiene en 800 pedidos",
                                    check_by=date(2026, 9, 1)))
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert any("sin fuente" in a for a in ag.advisories)


# ------------------------------------------------------------------- tick


def test_tick_vence_compromisos_y_supuestos(store):
    store.add_decision(mk_decision())
    store.add_commitment(Commitment(id="", decision_id="D-001", what="medir la linea base",
                                    owner="Fabian", due=date(2026, 7, 1),
                                    evidence_of_done="planilla"))
    store.add_assumption(Assumption(id="", decision_id="D-001",
                                    statement="el layout no cambia hasta septiembre",
                                    check_by=date(2026, 7, 15), source="jefe de operaciones"))

    r = tick(store, HOY)
    assert r["commitments_vencidos"] == ["C-001"]
    assert r["supuestos_vencidos"] == ["A-001"]
    assert r["decisiones_en_riesgo"] == ["D-001"]
    assert store.get("D-001").status == "EN_RIESGO"


def test_tick_es_idempotente(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 7, 15), source="jefe"))
    tick(store, HOY)
    segundo = tick(store, HOY)
    assert segundo["sin_cambios"] is True


def test_tick_no_toca_lo_que_no_vencio(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 12, 1), source="jefe"))
    r = tick(store, HOY)
    assert r["sin_cambios"] is True
    assert store.get("D-001").status == "VIGENTE"


def test_tick_dry_run_no_escribe(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 7, 1), source="jefe"))
    tick(store, HOY, apply=False)
    assert store.get("A-001").status == "VIGENTE"


def test_tick_detecta_zombis(store):
    """Un compromiso abierto colgando de una decision revertida es gente
    ejecutando algo que ya se revirtio: un bug real, silencioso, y hoy
    estructuralmente invisible."""
    d = store.add_decision(mk_decision())
    store.add_commitment(Commitment(id="", decision_id="D-001", what="comprar los racks nuevos",
                                    owner="Rodrigo", due=date(2026, 12, 1),
                                    evidence_of_done="orden de compra"))
    d.status = "REVERTIDA"
    store.save(d)

    r = tick(store, HOY)
    assert r["zombis"] == ["C-001"]
    assert store.get("C-001").status == "ZOMBI"
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert any("zombi" in a for a in ag.advisories)


def test_el_lazo_se_cierra_solo_supuesto_vencido_llega_a_la_agenda(store):
    """Nadie tiene que acordarse de nada. Ese es el mecanismo."""
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001",
                                    statement="el volumen se mantiene bajo 900 pedidos",
                                    check_by=date(2026, 7, 20), source="planificacion"))
    assert agenda(store, "2026-08-01-comite", today=HOY).is_empty

    tick(store, HOY)
    ag = agenda(store, "2026-08-01-comite", today=HOY)
    assert not ag.is_empty
    assert ag.at_risk_decisions[0][0].id == "D-001"


# ------------------------------------------------------- navegacion y cierre


def test_why_devuelve_rationale_y_supuestos_y_declara_que_no_hay_cita(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 9, 1), source="jefe"))
    r = why(store, "D-001")
    assert "69%" in r["rationale"]
    assert r["assumptions"][0]["id"] == "A-001"
    assert r["cita"] is None
    assert "sin canal HABLADA" in r["nota_cita"]
    assert r["fuente"] == "sin ancla"


def test_referencing_declara_siempre_su_cobertura(store):
    """Serena puede prometer completitud porque abajo tiene un compilador.
    Nosotros no, y callarlo seria el error mas grave del diseno."""
    store.add_decision(mk_decision())
    r = referencing(store, "D-001")
    assert r["coverage_completa"] is False
    assert "SOLO enlaces puestos a mano" in r["coverage"]


def test_referencing_encuentra_todo_lo_que_cuelga(store):
    store.add_decision(mk_decision())
    store.add_decision(mk_decision(statement="Comprar racks para la zona dorada ampliada",
                                   depends_on=["D-001"]))
    store.add_commitment(Commitment(id="", decision_id="D-001", what="ejecutar el reslotting",
                                    owner="Rodrigo", due=date(2026, 9, 1),
                                    evidence_of_done="reporte del WMS"))
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 9, 1), source="jefe"))
    store.add_question(OpenQuestion(id="", question="ampliamos la zona dorada?",
                                    resolver="Marcela", resolve_by=date(2026, 9, 1),
                                    blocks=["D-001"]))
    r = referencing(store, "D-001")
    assert r["total_referencias"] == 4
    assert r["depends_on_this"][0]["id"] == "D-002"
    assert r["open_commitments"][0]["id"] == "C-001"
    assert r["blocked_questions"][0]["id"] == "Q-001"


def test_referencing_en_profundidad_dos(store):
    store.add_decision(mk_decision())
    store.add_decision(mk_decision(statement="Comprar racks para la zona ampliada",
                                   depends_on=["D-001"]))
    store.add_decision(mk_decision(statement="Contratar el montaje de los racks nuevos",
                                   depends_on=["D-002"]))
    assert len(referencing(store, "D-001", depth=1)["depends_on_this"]) == 1
    assert len(referencing(store, "D-001", depth=2)["depends_on_this"]) == 2


def test_safe_close_se_niega_y_lista_lo_que_cuelga(store):
    store.add_decision(mk_decision())
    store.add_commitment(Commitment(id="", decision_id="D-001", what="ejecutar el reslotting",
                                    owner="Rodrigo", due=date(2026, 9, 1),
                                    evidence_of_done="reporte del WMS"))
    r = safe_close(store, "D-001")
    assert r["closed"] is False
    assert "C-001" in r["blockers"][0]
    assert "empieza a mentir" in r["reason"]


def test_safe_close_cierra_cuando_no_cuelga_nada(store):
    store.add_decision(mk_decision())
    r = safe_close(store, "D-001")
    assert r["closed"] is True
    assert r["applied"] is False
    assert store.get("D-001").status == "VIGENTE"  # sin --apply no toca nada


def test_safe_close_con_apply_exige_motivo(store):
    """Una decision que cambia de estado sin motivo escrito no se puede
    explicar seis semanas despues, que es el problema que el registro existe
    para resolver."""
    store.add_decision(mk_decision())
    with pytest.raises(ValueError, match="exige un motivo"):
        safe_close(store, "D-001", apply=True)


def test_safe_close_con_apply_revierte_y_deja_historial(store):
    store.add_decision(mk_decision())
    r = safe_close(store, "D-001", apply=True, reason="el CD cambia de layout en octubre",
                   today=HOY)
    assert r["applied"] is True
    d = store.get("D-001")
    assert d.status == "REVERTIDA"
    assert d.version == 2
    assert "2026-08-01 REVERTIDA: el CD cambia de layout" in d.historial_statements[0]


def test_safe_close_bloquea_por_supuesto_sin_verificar(store):
    store.add_decision(mk_decision())
    store.add_assumption(Assumption(id="", decision_id="D-001", statement="el layout no cambia",
                                    check_by=date(2026, 9, 1), source="jefe"))
    assert safe_close(store, "D-001")["closed"] is False

    a = store.get("A-001")
    a.status = "VERIFICADO"
    store.save(a)
    assert safe_close(store, "D-001")["closed"] is True


def test_implementations_es_una_relacion_real(store):
    store.add_decision(mk_decision())
    store.add_commitment(Commitment(id="", decision_id="D-001", what="ejecutar el reslotting",
                                    owner="Rodrigo", due=date(2026, 9, 1),
                                    evidence_of_done="reporte"))
    assert [c.id for c in implementations(store, "D-001")] == ["C-001"]


# ---------------------------------------------- regresiones de la auditoria


def test_el_acento_no_desactiva_la_validacion():
    """Habia dos `_norm` con el mismo nombre y semantica distinta: el de
    `decide/schema` colapsaba espacios pero NO quitaba acentos. El error era
    invisible y cortaba en las dos direcciones — 'quizas' se rechazaba y
    'quizás' pasaba; 'a mas tardar' valia como criterio y 'a más tardar' no.
    Ningun test lo veia porque todas sus cadenas estaban sin tildes."""
    def val(statement, criteria="a mas tardar el cierre"):
        return Decision(
            id="D-001", statement=statement, owner="Marcela", date_decided=HOY,
            criteria=criteria, rationale="porque los numeros lo piden",
        ).validate()

    con = val("quizás reslotear la clase A a la zona dorada")
    sin = val("quizas reslotear la clase A a la zona dorada")
    assert any("intencion de decidir" in i for i in con)
    assert any("intencion de decidir" in i for i in sin)

    ok = val("Reslotear la clase A a la zona dorada", "a más tardar el cierre")
    assert not any("numero" in i for i in ok)


def test_un_meeting_id_inexistente_falla_en_vez_de_apagar_la_validacion(store):
    """El roster es el scope lexico: la unica pieza de determinismo que el
    diseno fabrica. Un `--meeting` mal tipeado devolvia None en silencio y con
    eso desactivaba la validacion de dueno.

    Llega como `ValidationError` y no como `KeyError` suelto porque el roster
    ilegible pasa a ser un ISSUE: propagar la excepcion desde `_issues` mataba
    `tick()` entero — un solo .md de reunion ilegible y no se podia vencer ni un
    compromiso. Sigue bloqueando el alta, que es lo que este test fija: una
    entidad NUEVA entra sana o no entra.
    """
    with pytest.raises(ValidationError, match="no se pudo leer el roster"):
        store.add_decision(mk_decision(meeting_id="comite-mal-tipeado", owner="Pepe"))


def test_sin_meeting_id_la_decision_de_pasillo_sigue_entrando(store):
    """El caso legitimo no se rompe: `decide add` sin `--meeting` registra una
    decision de pasillo y no valida roster porque no hay ninguno declarado."""
    d = store.add_decision(mk_decision(meeting_id="", owner="Alguien de afuera"))
    assert d.id == "D-001"


def test_un_archivo_ilegible_dice_cual_es(tmp_path):
    """`_from_fm` levanta por campo desconocido a proposito —un .md escrito por
    una version mas nueva no se puede leer a medias— pero el mensaje no nombraba
    el archivo. Y como no hay try por archivo, uno solo tumba `decisions()`
    entero y con el `agenda()`, `tick()`, `volume_gate()` y `rebuild_index()`.
    Con trescientos archivos, "campos desconocidos: [...]" no alcanza.

    El nombre del campo es deliberadamente sintetico: la primera version de este
    test uso `clase`, y se rompio sola cuando `clase` paso a existir de verdad —
    que es exactamente la migracion que el test simula.

    Sigue fallando: un registro que se lee a medias es peor que uno que no se
    lee, porque el que se lee a medias imprime un numero.
    """
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator=ROSTER[0],
        consent=Consent(granted=True, granted_by=ROSTER[0], basis="interes_legitimo"),
    ))
    d = st.add_decision(Decision(
        id="", statement="Consolidar el picking de Pudahuel en una sola ola",
        owner=ROSTER[0], date_decided=HOY, criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id="m1",
    ))
    sano = (st.root / "decisions" / f"{d.id}.md").read_text(encoding="utf-8")
    (st.root / "decisions" / "D-099.md").write_text(
        sano.replace(f'id: "{d.id}"',
                     'id: "D-099"\ncampo_de_una_version_futura: "x"'), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as exc:
        st.decisions()
    assert "D-099.md" in str(exc.value)          # cual archivo
    assert "campo_de_una_version_futura" in str(exc.value)   # que campo
    assert "version mas nueva" in str(exc.value)  # que hacer


def test_un_campo_nuevo_en_anchor_o_consent_sobrevive_al_disco(tmp_path):
    """`_to_fm` aplanaba `Anchor` y `Consent` con tuplas de nombres escritas a
    mano. Estaban completas, pero eran una lista que hay que acordarse de
    actualizar: un campo nuevo se perdia al escribir y volvia a su default al
    leer, sin un solo error. El registro seguia cargando y el campo no existia.

    El test no fija los nombres de hoy —eso seria la misma lista otra vez— sino
    la invariante: lo que el dataclass declara es lo que llega al disco.
    """
    from dataclasses import fields as dc_fields

    from fdekit.decide.schema import Anchor
    from fdekit.decide.store import _to_fm

    st = DecideStore(tmp_path / "decide")
    consent = Consent(
        granted=True, granted_by=ROSTER[0], basis="interes_legitimo",
        recording_allowed=True, retention_days=30, note="piloto",
    )
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator=ROSTER[0], consent=consent,
    ))
    d = st.add_decision(Decision(
        id="", statement="Consolidar el picking de Pudahuel en una sola ola",
        owner=ROSTER[0], date_decided=HOY, criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id="m1",
        anchor=Anchor(meeting_id="m1", t_start=12.5, t_end=41.0,
                      cita_congelada="lo consolidamos en una ola", transcript_sha256="abc123"),
    ))

    # Todo campo declarado por el dataclass viaja al front-matter...
    fm_meeting = _to_fm(st.get_meeting("m1"))
    assert set(fm_meeting["consent"]) == {f.name for f in dc_fields(Consent)}
    fm_decision = _to_fm(st.get(d.id))
    assert set(fm_decision["anchor"]) == {f.name for f in dc_fields(Anchor)}

    # ...y vuelve del disco con su valor, no con su default.
    vuelta = st.get(d.id)
    assert vuelta.anchor.t_start == 12.5
    assert vuelta.anchor.cita_congelada == "lo consolidamos en una ola"
    assert st.get_meeting("m1").consent.retention_days == 30
    assert st.get_meeting("m1").consent.note == "piloto"


# ------------------------------- `save()` valida: una escritura no empeora
#
# `save()` era un `write_text` desnudo, y es lo que usan `supersede`,
# `safe_close` y `tick`. Toda regla escrita en un `validate()` era codigo muerto
# en los tres caminos que mas la necesitan: el unico que crea un estado nuevo
# era el unico que nunca pasaba por el validador.


def test_save_rechaza_un_issue_NUEVO(store):
    d = store.add_decision(mk_decision())
    d.owner = "ALGUIEN QUE NO ESTA EN EL ROSTER"
    with pytest.raises(ValidationError, match="roster"):
        store.save(d)
    assert store.get(d.id).owner == "Marcela"  # no se escribio


def test_save_tolera_lo_que_el_archivo_YA_tenia_y_lo_devuelve(store):
    """La semantica es 'no empeorar', no 'estar sano'.

    Validar contra el vacio haria imposible escribir sobre una entidad ya
    invalida — y son justamente esas sobre las que hay que poder anotar que algo
    fallo. Cada arreglo se volveria un bloqueo.
    """
    d = store.add_decision(mk_decision())
    d.owner = "ALGUIEN QUE NO ESTA EN EL ROSTER"
    store.save(d, force=True)          # queda invalido en disco, a proposito

    d2 = store.get(d.id)
    d2.rationale = "se corrige el porque sin tocar el dueno"
    heredados = store.save(d2)         # no bloquea: el issue ya estaba

    assert any("roster" in i for i in heredados)
    assert "se corrige el porque" in store.get(d.id).rationale


def test_tick_sobrevive_a_una_reunion_ilegible(store):
    """Antes: `_issues` -> `roster_of` -> `get_meeting` -> excepcion, y `tick()`
    moria entero. Un solo .md de reunion escrito por una version mas nueva y no
    se podia vencer ni un compromiso en todo el registro.

    El roster ilegible es un ISSUE, no una excepcion: se reporta y se sigue.
    """
    d = store.add_decision(mk_decision())
    c = store.add_commitment(Commitment(
        id="", decision_id=d.id, what="mover 200 ubicaciones a zona dorada",
        owner="Marcela", due=HOY - timedelta(days=10), meeting_id="2026-08-01-comite",
        evidence_of_done="reporte del WMS",
    ))
    # la reunion se vuelve ilegible: exactamente el escenario de forward-incompat
    p = store.root / "meetings" / "2026-08-01-comite.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        'id: "2026-08-01-comite"',
        'id: "2026-08-01-comite"\ncampo_de_una_version_futura: "x"'), encoding="utf-8")

    r = tick(store, today=HOY, apply=True)
    assert c.id in r["commitments_vencidos"]
    assert store.get(c.id).status == "VENCIDO"


def test_supersede_ya_no_puede_escribir_una_decision_invalida(store):
    """`supersede` escribe con `save()`. Antes eso no validaba nada, asi que
    cualquier regla nueva sobre estados era inalcanzable por el unico camino que
    los produce."""
    a = store.add_decision(mk_decision())
    b = store.add_decision(mk_decision(statement="Reslotear clase A y B con racks nuevos"))
    a_disco = store.get(a.id)
    a_disco.owner = "ALGUIEN QUE NO ESTA EN EL ROSTER"
    with pytest.raises(ValidationError):
        store.save(a_disco)
    # y la operacion legitima sigue funcionando
    assert supersede(store, a.id, b.id, reason="racks nuevos", apply=True, today=HOY)["applied"]


# ------------------------------- retencion del canal HABLADA (Ley 21.719)
#
# `TranscriptStore.purge()` tenia CERO llamadores en todo el paquete: una
# politica de retencion sin ejecutor es una declaracion, no una politica. Y
# aunque se hubiera llamado, no destruia nada: `hablada/` entraba a git por el
# `git add .` de `git_commit`, asi que el habla textual sobrevivia en la
# historia de cada clon.


def _con_hablada(tmp_path, retention_days, meeting_date=date(2025, 1, 10)):
    from fdekit.decide.transcript import TranscriptStore

    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=meeting_date, roster=ROSTER, facilitator="Marcela",
        # Sin `retention_days` no se puede declarar `recording_allowed`: el
        # propio `Consent.validate` lo rechaza, y con razon. El caso "hay habla
        # guardada y nadie declaro por cuanto tiempo" se llega igual, porque el
        # transcripto puede haber entrado por `--text` sin audio.
        consent=Consent(granted=True, granted_by="Marcela", basis="interes_legitimo",
                        recording_allowed=retention_days is not None,
                        retention_days=retention_days),
    ))
    ts = TranscriptStore(st.root, "m1")
    # `force` cuando no hay politica: simula el archivo legado, escrito antes de
    # que el guardia de consentimiento existiera. Es el unico modo de llegar hoy
    # a "hay habla guardada y nadie declaro por cuanto tiempo".
    ts.ingest_segments([{"start": 0.0, "end": 8.0,
                         "text": "el problema es que Fabian no da abasto en el turno noche"}],
                       force=retention_days is None)
    return st, ts


def test_tick_ejecuta_la_politica_de_retencion(tmp_path):
    st, ts = _con_hablada(tmp_path, retention_days=90)
    r = tick(st, today=date(2026, 8, 2), apply=True)
    assert r["hablada_purgada"] == ["m1"]
    assert not ts.path.exists()
    assert ts.lapida.exists()


def test_el_canal_hablada_no_se_versiona(tmp_path):
    """Si entra a git, `purge()` es teatro: `git show HEAD:hablada/m1.jsonl` lo
    devuelve entero, y con el los terceros mencionados que nunca consintieron.
    Reproducido antes del arreglo."""
    st, ts = _con_hablada(tmp_path, retention_days=90)
    patrones = (st.root / ".gitignore").read_text(encoding="utf-8")
    assert "hablada/*.jsonl" in patrones
    assert "!hablada/*.purgado.json" in patrones   # la constancia SI se versiona


def test_sin_politica_declarada_no_se_borra_pero_se_reporta(tmp_path):
    """Borrar por un default seria destruir evidencia que nadie autorizo
    destruir. Callarlo seria peor: la reunion queda con habla textual guardada
    para siempre y nadie se entera."""
    st, ts = _con_hablada(tmp_path, retention_days=None)
    r = tick(st, today=date(2026, 8, 2), apply=True)
    assert r["hablada_sin_politica"] == ["m1"]
    assert r["hablada_purgada"] == []
    assert ts.path.exists()


def test_purgar_marca_las_anclas_como_CADUCADA(tmp_path):
    """`CADUCADA` estaba declarado en el schema y no lo escribia NADIE: `why()`
    mostraba `estado_fuente: VIVA` sobre un transcripto que ya no existe."""
    from fdekit.decide.schema import Anchor

    st, ts = _con_hablada(tmp_path, retention_days=90)
    d = st.add_decision(mk_decision(
        meeting_id="m1",
        anchor=Anchor(meeting_id="m1", t_start=0.0, t_end=8.0,
                      cita_congelada="lo consolidamos en una ola",
                      transcript_sha256=ts.sha256())))
    assert st.get(d.id).anchor.estado_fuente == "VIVA"

    tick(st, today=date(2026, 8, 2), apply=True)
    assert st.get(d.id).anchor.estado_fuente == "CADUCADA"


def test_el_barrido_que_no_pudo_correr_lo_dice(tmp_path):
    """Una politica de retencion que no corrio y no avisa es peor que ninguna:
    queda documentada como si hubiera corrido."""
    st, ts = _con_hablada(tmp_path, retention_days=90)
    p = st.root / "meetings" / "m1.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        'id: "m1"', 'id: "m1"\ncampo_de_una_version_futura: "x"'), encoding="utf-8")

    r = tick(st, today=date(2026, 8, 2), apply=True)
    assert "hablada_no_barrida" in r
    assert "m1.md" in r["hablada_no_barrida"]
    assert ts.path.exists()   # no se toco nada


# ------------------------------------------- H7: el perfil gobierna de verdad
#
# Los campos `clase` y `canal` ya existian (paso 2, el Corpus). Lo que faltaba
# es que gobernaran algo mas que el techo de promociones.


def _meeting(st, mid, clase="COMITE", graba=False, retencion=None):
    st.add_meeting(Meeting(
        id=mid, date=HOY, roster=ROSTER, facilitator="Marcela", clase=clase,
        consent=Consent(granted=True, granted_by="Marcela", basis="interes_legitimo",
                        recording_allowed=graba, retention_days=retencion),
    ))


def test_el_1a1_no_puede_persistir_habla_ni_por_la_rama_de_texto(tmp_path):
    """El agujero medido: el chequeo de `recording_allowed` vivia en
    `cli.py:248`, DENTRO del `else` de `if a.text`. La rama `--text` y todo
    `cmd_draft` escribian habla textual sin preguntar nada. Reproducido con un
    1:1 de desempeno sobre un tercero, que es el peor caso posible: el perfil
    decia que no, el consentimiento decia que no, y se escribio igual."""
    from fdekit.decide.transcript import RecordingNotAllowed, TranscriptStore

    st = DecideStore(tmp_path / "decide")
    _meeting(st, "1a1-fabian", clase="UNO_A_UNO")
    ts = TranscriptStore(st.root, "1a1-fabian")

    with pytest.raises(RecordingNotAllowed, match="UNO_A_UNO"):
        ts.ingest_text("Fabian no esta rindiendo en el turno noche.")
    with pytest.raises(RecordingNotAllowed, match="UNO_A_UNO"):
        ts.ingest_segments([{"start": 0, "end": 3, "text": "Fabian no esta rindiendo"}])
    assert not ts.path.exists()


def test_sin_consentimiento_tampoco_escribe(tmp_path):
    from fdekit.decide.transcript import RecordingNotAllowed, TranscriptStore

    st = DecideStore(tmp_path / "decide")
    _meeting(st, "comite", clase="COMITE", graba=False)
    with pytest.raises(RecordingNotAllowed, match="no tiene consentimiento"):
        TranscriptStore(st.root, "comite").ingest_text("lo consolidamos en una ola.")


def test_sin_reunion_registrada_no_hay_contra_que_consentir(tmp_path):
    """El guardia lee la reunion del disco en vez de recibirla por parametro: un
    guardia que depende de que el llamador pase el dato se esquiva sin querer, y
    asi nacio el bug."""
    from fdekit.decide.transcript import RecordingNotAllowed, TranscriptStore

    st = DecideStore(tmp_path / "decide")
    with pytest.raises(RecordingNotAllowed, match="no hay reunion registrada"):
        TranscriptStore(st.root, "inventada").ingest_text("cualquier cosa.")


def test_el_comite_con_consentimiento_si_escribe(tmp_path):
    """El guardia no puede romper el caso legitimo."""
    from fdekit.decide.transcript import TranscriptStore

    st = DecideStore(tmp_path / "decide")
    _meeting(st, "comite", graba=True, retencion=90)
    utts = TranscriptStore(st.root, "comite").ingest_text("lo consolidamos en una ola.")
    assert len(utts) == 1


def test_el_perfil_apaga_el_gate_pero_lo_deja_anotado(tmp_path):
    """Apagar el gate sin dejar rastro seria la regla 3 rota: la agenda de un
    INCIDENTE quedaria identica a una donde el gate no rechazo nada. El perfil
    relaja el proceso, no la contabilidad."""
    # Dos stores y no dos reuniones: `agenda()` mira TODAS las preguntas
    # abiertas del registro, no solo las de esa reunion — es su diseno, porque
    # lo pendiente no deja de estarlo por haberse planteado en otra sesion.
    def _con_pregunta(sub, clase):
        st = DecideStore(tmp_path / sub)
        _meeting(st, "m", clase=clase)
        st.add_question(OpenQuestion(
            id="", question="cortamos la ola de las 14:00?", resolver="Ajeno",
            resolve_by=HOY + timedelta(days=3), meeting_id="m"), force=True)
        return st

    a_comite = agenda(_con_pregunta("comite", "COMITE"), "m", today=HOY)
    assert len(a_comite.gate_rejections) == 1 and not a_comite.gate_bypassed

    a_inc = agenda(_con_pregunta("incidente", "INCIDENTE"), "m", today=HOY)
    assert not a_inc.gate_rejections
    assert len(a_inc.gate_bypassed) == 1
    assert any("gate de agenda DESACTIVADO" in x for x in a_inc.advisories)
    assert "Entraron con el gate APAGADO" in a_inc.to_markdown()
