"""Fase 4: process mining del ciclo de vida, metricas y export.

La regla que atraviesa todos estos tests: **nada de esto dice algo antes de ~50
decisiones y ~15 reuniones**, y el codigo tiene que decirlo en vez de publicar
un numero bonito. Bajo ese volumen las metricas re-descubren los titulos de la
agenda — el consenso mas fuerte del estudio de diseno, al que los cuatro
enfoques llegaron por separado.
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
)
from fdekit.decide.eventlog import (
    REWORK_ACTIVITIES,
    touches_excluidas,
    build_event_log,
    lifecycle_rework,
    touches_to_decide,
)
from fdekit.decide.export import to_graphify, to_mermaid, write_graphify
from fdekit.decide.schema import PROFILES
from fdekit.decide.metrics import (
    capture_state,
    capture_summary,
    freeze_baseline,
    MIN_DECISIONS,
    QueryLog,
    circular_minutes,
    decider_executor_presence,
    index_quality,
    orphans_and_zombies,
    read_metrics,
    reopening_split,
    report,
    touches_xmr,
    volume_gate,
)
from fdekit.decide.resolve import AliasStore, confirm
from fdekit.decide.store import ValidationError
from fdekit.processmining import rework_summary, variants
from fdekit.stats import risk_ratio_2x2

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


def consent(graba: bool = True):
    """Con permiso de grabar por default: estos tests ejercen el canal HABLADA,
    y `TranscriptStore.write` ahora se niega sin consentimiento. Declararlo en
    el test es mas honesto que el estado anterior, donde el habla textual se
    escribia sin que nadie hubiera dicho que si."""
    return Consent(True, "Marcela Perez", "interes_legitimo",
                   recording_allowed=graba, retention_days=90 if graba else None)


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "d")
    for i in range(3):
        st.add_meeting(Meeting(
            id=f"m{i+1}", date=HOY + timedelta(days=7 * i), roster=ROSTER,
            facilitator="Marcela Perez", consent=consent(), scope="pudahuel/slotting",
        ))
    return st


def mk_decision(store, mid="m3", when=None, force=False, **kw):
    base = dict(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=when or (HOY + timedelta(days=14)),
        criteria="a mas tardar 2026-09-30", rationale="el 69% de las visitas son clase A",
        meeting_id=mid, scope="pudahuel/slotting", slots={"proceso": "slotting"},
    )
    base.update(kw)
    return store.add_decision(Decision(**base), force=force)


# ------------------------------------------------------------- stats 2x2


def test_el_2x2_extraido_conserva_el_comportamiento():
    r = risk_ratio_2x2(a=30, b=70, c=10, d=90)
    assert r["risk_ratio"] == 3.0
    assert r["tasa_expuestos_pct"] == 30.0
    assert 0 < r["population_attributable_fraction_pct"] < 100
    assert r["muestra_suficiente"] is True


def test_el_2x2_avisa_cuando_la_muestra_es_chica():
    """Un p-valor sobre doce observaciones es decoracion, y decirlo importa mas
    que el numero."""
    assert risk_ratio_2x2(2, 3, 1, 4)["muestra_suficiente"] is False


def test_el_2x2_no_revienta_con_celdas_vacias():
    r = risk_ratio_2x2(0, 0, 5, 5)
    assert r["chi2"] is None
    assert r["expuestos"] == 0


# ---------------------------------------------------- compuerta de volumen


def test_la_compuerta_bloquea_bajo_el_minimo(store):
    mk_decision(store)
    g = volume_gate(store)
    assert g["ok"] is False
    assert "volumen insuficiente" in g["veredicto"]
    assert "tabla ordenada por dueno y fecha" in g["veredicto"]


def test_el_export_respeta_la_compuerta(store, tmp_path):
    mk_decision(store)
    r = write_graphify(store, tmp_path / "g.json")
    assert r["escrito"] is False
    assert not (tmp_path / "g.json").exists()


def test_el_export_forzado_avisa_que_se_forzo(store, tmp_path):
    mk_decision(store)
    r = write_graphify(store, tmp_path / "g.json", force=True)
    assert r["escrito"] is True
    assert "bajo el minimo" in r["aviso"]


def test_la_hoja_encabeza_con_la_advertencia_de_volumen(store):
    mk_decision(store)
    assert "Volumen insuficiente" in report(store)


# ------------------------------------------------------------- event log


def test_el_ciclo_de_vida_se_vuelve_un_event_log(store):
    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="reslotamos la clase A?", resolver="Marcela Perez",
        resolve_by=HOY, blocks=[d.id], meeting_id="m1",
    ))
    log = build_event_log(store)
    acts = set(log.df["activity"])
    assert {"DISCUTIDA", "DECIDIDA"} <= acts
    assert log.n_cases == 1


def test_toques_para_decidir_cuenta_las_vueltas(store):
    """Un tema que necesito tres vueltas no es un tema dificil: casi siempre le
    faltaba un dato que nadie fue a buscar."""
    d = mk_decision(store)
    for mid in ("m1", "m2"):
        store.add_question(OpenQuestion(
            id="", question="reslotamos la clase A?", resolver="Marcela Perez",
            resolve_by=HOY, blocks=[d.id], meeting_id=mid,
        ))
    t = touches_to_decide(store)
    assert t.loc[0, "toques"] == 3  # dos discusiones previas + la decision
    assert t.loc[0, "dias_hasta_decidir"] == 14


def test_la_decision_sin_discusion_previa_tiene_un_toque(store):
    mk_decision(store)
    assert touches_to_decide(store).loc[0, "toques"] == 1


def test_la_reapertura_aparece_como_reproceso(store):
    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="reabrimos el slotting?", resolver="Marcela Perez",
        resolve_by=HOY + timedelta(days=30), reopen_of=d.id, meeting_id="m3",
        new_evidence="la distancia media subio a 52 m",
    ))
    r = lifecycle_rework(store)
    assert "REABIERTA" in r["por_actividad"]
    assert r["reuniones_extra"] == 1


def test_el_reproceso_se_mide_en_reuniones_no_en_horas_de_turno(store):
    """`rework_summary` generico multiplica por 250 turnos al ano porque asume
    que la ventana observada es un turno. En un registro de decisiones la
    ventana son meses, y el resultado son millones de horas perdidas — un numero
    absurdo que igual se ve serio en una tabla."""
    from fdekit.decide.transcript import TranscriptStore

    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="lo vemos otra vez?", resolver="Marcela Perez",
        resolve_by=HOY, blocks=[d.id], meeting_id="m1",
    ))
    TranscriptStore(store.root, "m1").ingest_segments(
        [{"start": 0.0, "end": 1200.0, "text": "otra vuelta sobre el mismo tema"}]
    )
    r = lifecycle_rework(store)
    assert r["reuniones_extra"] == 1
    assert r["minutos_persona"] == pytest.approx(20 * 3, abs=0.5)
    assert "reuniones extra, no en horas de turno" in r["nota"]
    assert "annual_hours_lost" not in r


def test_el_reproceso_declara_los_eventos_sin_audio(store):
    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="lo vemos otra vez?", resolver="Marcela Perez",
        resolve_by=HOY, blocks=[d.id], meeting_id="m1",
    ))
    r = lifecycle_rework(store)
    assert r["eventos_sin_tiempo"] == 1
    assert r["minutos_persona"] == 0.0


def test_el_historial_de_estados_entra_al_log(store):
    d = mk_decision(store)
    d.historial_statements.append("2026-09-01 REVERTIDA: cambio el layout")
    store.save(d)
    log = build_event_log(store)
    assert "REVERTIDA" in set(log.df["activity"])


def test_las_variantes_del_ciclo_de_vida_son_analizables(store):
    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="reslotamos?", resolver="Marcela Perez", resolve_by=HOY,
        blocks=[d.id], meeting_id="m1",
    ))
    v = variants(build_event_log(store), collapse_repeats=False)
    assert v.loc[0, "variant"] == "DISCUTIDA -> DECIDIDA"


def test_registro_vacio_no_revienta(store):
    assert len(build_event_log(store)) == 0
    assert touches_to_decide(store).empty


# -------------------------------------------------------- lectura (H2)


def test_sin_consultas_el_registro_es_un_pasivo(store):
    r = read_metrics(store)
    assert r["consultas"] == 0
    assert "modo de falla dominante" in r["veredicto"]


def test_un_solo_lector_es_una_libreta_personal_cara(store):
    q = QueryLog(store.root)
    q.log("why", "Marcela Perez", "D-001")
    q.log("refs", "Marcela Perez", "D-001")
    r = read_metrics(store)
    assert r["lectores_unicos"] == 1
    assert "libreta personal cara" in r["veredicto"]


def test_la_tasa_de_consulta_fallida_es_la_senal_temprana(store):
    q = QueryLog(store.root)
    q.log("why", "A", "D-001", hit=True, in_room=True)
    q.log("why", "B", "D-999", hit=False)
    r = read_metrics(store)
    assert r["tasa_consulta_fallida_pct"] == 50.0
    assert r["consultas_fuera_de_sala_pct"] == 50.0
    assert r["lectores_unicos"] == 2


# ---------------------------------------------------------- friccion


def test_la_reapertura_sin_consulta_previa_es_por_ignorancia(store):
    """Separa desperdicio puro de aprendizaje legitimo. Ninguna herramienta
    actual distingue las dos."""
    d = mk_decision(store)
    store.add_question(OpenQuestion(
        id="", question="volvemos a ver el slotting?", resolver="Marcela Perez",
        resolve_by=HOY + timedelta(days=30), reopen_of=d.id,
        new_evidence="la distancia media subio a 52 m", meeting_id="m3",
    ))
    r = reopening_split(store)
    assert r["por_ignorancia"] == 1
    assert r["pct_por_ignorancia"] == 100.0


def test_si_alguien_consulto_antes_la_reapertura_es_legitima(store):
    d = mk_decision(store)
    QueryLog(store.root).log("why", "Rodrigo Munoz", d.id)
    store.add_question(OpenQuestion(
        id="", question="volvemos a ver el slotting?", resolver="Marcela Perez",
        resolve_by=HOY + timedelta(days=30), reopen_of=d.id,
        new_evidence="la distancia media subio a 52 m", meeting_id="m3",
    ))
    assert reopening_split(store)["por_ignorancia"] == 0


def test_los_zombis_se_cuentan_aparte_de_los_huerfanos(store):
    d = mk_decision(store)
    store.add_commitment(Commitment(
        id="", decision_id=d.id, what="comprar los racks nuevos", owner="Rodrigo Munoz",
        due=HOY + timedelta(days=60), evidence_of_done="orden de compra", meeting_id="m3",
    ))
    d.status = "REVERTIDA"
    store.save(d)
    oz = orphans_and_zombies(store)
    assert oz["zombis"] == ["C-001"]
    assert oz["ok"] is False


def test_los_minutos_circulares_solo_cuentan_reuniones_con_timestamps(store):
    from fdekit.decide.transcript import TranscriptStore

    TranscriptStore(store.root, "m1").ingest_segments(
        [{"start": 0.0, "end": 1800.0, "text": "estuvimos media hora dando vueltas"}]
    )
    TranscriptStore(store.root, "m2").ingest_text("una reunion sin timestamps")
    mk_decision(store, mid="m3")

    c = circular_minutes(store)
    assert c["minutos_persona_circulares"] == pytest.approx(30 * 3, abs=0.5)
    assert c["sin_timestamps"] == ["m2"]
    assert "no se estima" in c["nota"]


def test_la_presencia_del_dueno_se_mide_con_el_mismo_2x2(store):
    d = mk_decision(store)
    for i in range(6):
        store.add_commitment(Commitment(
            id="", decision_id=d.id, what=f"tarea numero {i} del reslotting",
            owner="Rodrigo Munoz", due=HOY, evidence_of_done="reporte",
            status="VENCIDO" if i < 4 else "CUMPLIDO",
            owner_presente_al_decidir=i >= 4, meeting_id="m3",
        ), force=True)
    r = decider_executor_presence(store)
    assert r["expuestos"] == 4
    assert r["tasa_expuestos_pct"] == 100.0


# ------------------------------------------------------ calidad del indice


def test_el_indice_reporta_resolucion_automatica_y_correccion(store):
    d = mk_decision(store)
    astore = AliasStore(store.root)
    confirm(astore, "lo del slotting", d, "pudahuel/slotting", "Marcela Perez", HOY)
    idx = index_quality(store)
    assert idx["menciones"] == 1
    assert idx["alias_vigentes"] == 1
    assert "tasa_correccion_pct" in idx


def test_muchos_alias_retirados_delatan_un_criterio_laxo(store):
    from fdekit.decide.resolve import unalias

    d = mk_decision(store)
    astore = AliasStore(store.root)
    confirm(astore, "lo del slotting", d, "pudahuel/slotting", "Marcela Perez", HOY)
    unalias(astore, "lo del slotting", "estaba mal", HOY)
    assert "demasiado laxo" in index_quality(store)["veredicto"]


# ------------------------------------------------------------------ XmR


def test_el_xmr_se_niega_sin_linea_base(store):
    mk_decision(store)
    r = touches_xmr(store)
    assert r["ok"] is False
    assert "ruido con apariencia de control estadistico" in r["veredicto"]


def test_el_xmr_corre_con_suficientes_puntos(store):
    for i in range(20):
        d = mk_decision(store, when=HOY + timedelta(days=i),
                        statement=f"Decision numero {i} sobre el slotting del CD", force=True)
        if i >= 15:  # las ultimas necesitan mas vueltas: el proceso se degrada
            store.add_question(OpenQuestion(
                id="", question="lo vemos?", resolver="Marcela Perez", resolve_by=HOY,
                blocks=[d.id], meeting_id="m1",
            ))
    r = touches_xmr(store, baseline=12)
    assert r["ok"] is True
    assert r["limites"]["n_baseline"] == 12


# --------------------------------------------------------------- export


def test_el_export_solo_lleva_aristas_confirmadas(store):
    d1 = mk_decision(store)
    d2 = mk_decision(store, statement="Comprar racks para la zona ampliada",
                     depends_on=[d1.id])
    store.add_commitment(Commitment(
        id="", decision_id=d1.id, what="ejecutar el reslotting", owner="Rodrigo Munoz",
        due=HOY, evidence_of_done="reporte del WMS", meeting_id="m3",
    ))
    g = to_graphify(store)
    assert all(e["confidence"] == "EXTRACTED" for e in g["edges"])
    assert {"DEPENDE_DE", "IMPLEMENTA"} <= {e["relation"] for e in g["edges"]}
    assert d2.id in {n["id"] for n in g["nodes"]}


def test_el_export_declara_que_no_es_exhaustivo(store):
    mk_decision(store)
    assert "no tratar como exhaustivo" in to_graphify(store)["meta"]["cobertura"]
    assert "el original vive en git" in to_graphify(store)["meta"]["regla"]


def test_los_alias_confirmados_son_aristas_con_procedencia(store):
    d = mk_decision(store)
    confirm(AliasStore(store.root), "lo del slotting", d, "pudahuel/slotting",
            "Marcela Perez", HOY)
    e = next(x for x in to_graphify(store)["edges"] if x["relation"] == "REFIERE_A")
    assert e["confidence"] == "EXTRACTED"
    assert "confirmado por Marcela Perez" in e["evidence"]


def test_el_supuesto_y_la_pregunta_tambien_exportan(store):
    d = mk_decision(store)
    store.add_assumption(Assumption(
        id="", decision_id=d.id, statement="el layout no cambia hasta septiembre",
        check_by=HOY + timedelta(days=30), source="jefe de operaciones", meeting_id="m3",
    ))
    store.add_question(OpenQuestion(
        id="", question="ampliamos la zona dorada?", resolver="Marcela Perez",
        resolve_by=HOY + timedelta(days=30), blocks=[d.id], meeting_id="m3",
    ))
    rels = {e["relation"] for e in to_graphify(store)["edges"]}
    assert {"SOSTIENE", "BLOQUEA"} <= rels


def test_el_mermaid_se_corta_y_lo_dice(store):
    for i in range(5):
        mk_decision(store, statement=f"Decision numero {i} sobre el slotting del CD")
    m = to_mermaid(store, max_nodes=2)
    assert m.startswith("flowchart TD")
    assert "cortado: 3 nodos mas" in m


# ------------------------------- la regla 6: los limites TIENEN que congelarse
#
# "Congelado" era una palabra del docstring y no un hecho: `touches_xmr`
# recalculaba `serie[:baseline]` desde el store en cada llamada, ordenando por
# fecha de decision. Una sola decision registrada hoy pero fechada antes de la
# ventana entraba a la linea base y corria los limites — medido, center 2,83 ->
# 2,58 y sigma 1,69 -> 1,85. Es exactamente el modo de falla que la regla 6
# existe para impedir: un CD que se degrada de a poco ensancha sus propios
# limites, y el grafico dice "en control" mientras el proceso empeora.

# Doce de linea base mas seis de monitoreo. El margen sobre el minimo
# (`baseline + 4`) es deliberado: sin el, borrar un caso tira la serie por la
# rama de "volumen insuficiente" y el test mediria otra cosa.
_TOQUES_BASE = [3, 2, 4, 1, 3, 2, 5, 2, 3, 1, 4, 4, 3, 2, 4, 3, 2, 4]
_R = ("Marcela", "Fabian", "Rodrigo")


def _consent():
    return Consent(granted=True, granted_by="Marcela", basis="interes_legitimo")


def _serie(st, filas):
    """Fabrica decisiones con N toques: N-1 preguntas previas que la bloquean."""
    for i, (f, n) in enumerate(filas):
        mid = f"m{i:02d}"
        st.add_meeting(Meeting(id=mid, date=f, roster=_R, facilitator="Marcela",
                               consent=_consent()))
        d = st.add_decision(Decision(
            id="", statement=f"Consolidar la ola {i} del picking de Pudahuel",
            owner="Marcela", date_decided=f, criteria="100% de los SKU clase A antes del 30-09",
            rationale="cambio el mix de pedidos", meeting_id=mid))
        for j in range(n - 1):
            pm = f"p{i:02d}x{j}"
            st.add_meeting(Meeting(id=pm, date=f - timedelta(days=7 * (j + 1)), roster=_R,
                                   facilitator="Marcela", consent=_consent()))
            st.add_question(OpenQuestion(
                id="", question=f"consolidamos la ola {i}?", resolver="Marcela",
                resolve_by=f, blocks=[d.id], meeting_id=pm))
    return st


@pytest.fixture
def serie_xmr(tmp_path):
    st = DecideStore(tmp_path / "decide")
    return _serie(st, [(date(2026, 3, 1) + timedelta(days=7 * i), n)
                       for i, n in enumerate(_TOQUES_BASE)])


def test_sin_congelar_los_limites_se_declaran_provisorios(serie_xmr):
    """Regla 3. Un grafico de control cuyos limites se mueven solos no es un
    grafico de control, y presentarlo como tal es peor que no tenerlo."""
    r = touches_xmr(serie_xmr)
    assert r["congelada"] is False
    assert "PROVISORIOS" in r["veredicto"]
    assert any("NO congelada" in a for a in r["avisos"])


def test_los_limites_no_se_mueven_con_una_decision_fechada_hacia_atras(serie_xmr):
    """El bug, en su forma exacta: una decision registrada hoy y fechada seis
    meses antes entraba a la linea base porque la base eran 'los primeros 12 por
    fecha'. La base es un PERIODO DECLARADO, no un ranking que se reordena."""
    freeze_baseline(serie_xmr, date(2026, 8, 2))
    antes = touches_xmr(serie_xmr)["limites"]

    f = date(2026, 1, 5)  # anterior a toda la ventana de linea base
    serie_xmr.add_meeting(Meeting(id="tarde", date=f, roster=_R, facilitator="Marcela",
                                  consent=_consent()))
    serie_xmr.add_decision(Decision(
        id="", statement="Consolidar una ola vieja del picking", owner="Marcela",
        date_decided=f, criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id="tarde"))

    despues = touches_xmr(serie_xmr)
    assert despues["limites"] == antes
    assert despues["congelada"] is True
    # ...y no se calla que el pasado del registro cambio.
    assert any("fechada(s) dentro de la ventana" in a for a in despues["avisos"])


def test_avisa_si_un_caso_de_la_linea_base_ya_no_esta(serie_xmr, tmp_path):
    """Los limites siguen siendo los congelados —esa es la regla— pero la base
    deja de ser reproducible desde los datos de hoy, y eso se dice."""
    freeze_baseline(serie_xmr, date(2026, 8, 2))
    congelados = touches_xmr(serie_xmr)["limites"]
    (serie_xmr.root / "decisions" / "D-001.md").unlink()

    r = touches_xmr(serie_xmr)
    assert r["limites"] == congelados
    assert any("ya no estan en el registro" in a for a in r["avisos"])


def test_no_se_puede_congelar_ruido(tmp_path):
    """Congelar con pocos puntos fija ruido con apariencia de control."""
    st = _serie(DecideStore(tmp_path / "decide"),
                [(date(2026, 3, 1) + timedelta(days=7 * i), n)
                 for i, n in enumerate([3, 2, 4])])
    with pytest.raises(ValueError, match="linea base"):
        freeze_baseline(st, date(2026, 8, 2))


# ------------------------------------- el corpus: la pregunta transversal
#
# Cada hueco queria su propio filtro en `volume_gate`, `circular_minutes` y
# `touches_to_decide`: tres reglas para una sola pregunta, escritas en cinco
# lugares. El corpus la contesta una vez, y **publica lo que dejo afuera**.


def _meet(st, mid, clase="COMITE", canal="SINCRONICO"):
    st.add_meeting(Meeting(id=mid, date=date(2026, 8, 1), roster=_R, facilitator="Marcela",
                           consent=_consent(), clase=clase, canal=canal))


def _dec(st, mid, i, owner="Marcela", **kw):
    return st.add_decision(Decision(
        id="", statement=f"Consolidar el picking de Pudahuel en la ola {i}", owner=owner,
        date_decided=date(2026, 8, 1), criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id=mid, **kw))


def test_la_decision_de_pasillo_no_abre_la_compuerta(tmp_path):
    """El agujero medido: `decide add` sin `--meeting` es ruta legitima, pero
    por ahi no hay roster, no hay consentimiento, y el techo de 7 **ni se
    evalua** porque `add_decision` lo envuelve en `if decision.meeting_id:`.
    Doce llamadas con dueno fuera de todo roster se escribian las doce, y la
    compuerta de la regla 5 las contaba las doce."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "comite")
    for i in range(12):
        _dec(st, "", i, owner="NADIE QUE ESTE EN NINGUN ROSTER")
    _dec(st, "comite", 100)

    g = volume_gate(st)
    assert g["decisiones_en_disco"] == 13   # siguen en disco: no se borra nada
    assert g["decisiones"] == 1             # ...pero solo una es auditable
    assert "pasillo" in g["nota"]


def test_quince_cambios_de_turno_no_satisfacen_el_minimo_de_reuniones(tmp_path):
    """Un HANDOVER no decide: deja compromisos. Quince dailies en tres semanas
    abrian la compuerta sin que se hubiera decidido nada."""
    st = DecideStore(tmp_path / "decide")
    for i in range(15):
        _meet(st, f"daily-{i:02d}", clase="HANDOVER")
    g = volume_gate(st)
    assert g["reuniones_en_disco"] == 15
    assert g["reuniones"] == 0
    assert "HANDOVER" in g["nota"]


def test_el_techo_del_perfil_solo_puede_bajar_el_siete(tmp_path):
    """La regla dura 7 no se suspende ni para INCIDENTE, que es donde el
    documento de huecos pedia suspenderla. Un incidente con mas de siete
    decisiones fueron dos incidentes."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "daily", clase="HANDOVER")
    with pytest.raises(PromotionBudgetExceeded, match="techo es 0"):
        _dec(st, "daily", 1)

    _meet(st, "incidente", clase="INCIDENTE")
    for i in range(7):
        _dec(st, "incidente", i)
    with pytest.raises(PromotionBudgetExceeded):
        _dec(st, "incidente", 99)

    assert all(p.promotion_budget <= 7 for p in PROFILES.values())


def test_el_carril_declarado_es_paralelo_al_techo_de_la_sala(tmp_path):
    """El techo cuenta por `(meeting_id, origen)`, no por `meeting_id`.

    Sin esto, sembrar las 15-30 decisiones vigentes del kickoff contra el
    `meeting_id` de la sesion de siembra explota en la octava, y la unica salida
    que queda es borrar el `--meeting` — que es peor: por ahi no hay roster ni
    consentimiento. El carril declarado es PARALELO, no una excepcion al techo:
    las sembradas no consumen ni una de las 7 de la sala, y las 7 de la sala
    siguen siendo 7 despues de sembrar 30.
    """
    st = DecideStore(tmp_path / "decide")
    _meet(st, "kickoff", clase="KICKOFF")

    for i in range(30):
        _dec(st, "kickoff", i, origen="SIEMBRA")

    # ...y la sala conserva sus 7 intactas.
    for i in range(7):
        _dec(st, "kickoff", 100 + i)
    with pytest.raises(PromotionBudgetExceeded, match="REUNION"):
        _dec(st, "kickoff", 200)


def test_el_carril_declarado_tambien_tiene_techo(tmp_path):
    """Paralelo no es infinito. Treinta y una sembradas no son una siembra: son
    la minuta hibrida entrando por la puerta de atras."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "kickoff", clase="KICKOFF")
    for i in range(30):
        _dec(st, "kickoff", i, origen="SIEMBRA")
    with pytest.raises(PromotionBudgetExceeded, match="SIEMBRA"):
        _dec(st, "kickoff", 99, origen="SIEMBRA")


def test_el_techo_es_una_sola_funcion_y_el_siete_no_sube(tmp_path):
    """`promotion_ceiling` es el unico techo del sistema, y `_check_budget_ceiling`
    corre al importar: la regla 7 pasa de comentario a propiedad verificada."""
    from fdekit.decide.store import DECLARED_BUDGET, promotion_ceiling

    assert promotion_ceiling("COMITE", "REUNION") == 7
    assert promotion_ceiling("HANDOVER", "REUNION") == 0
    assert promotion_ceiling("KICKOFF", "SIEMBRA") == DECLARED_BUDGET["SIEMBRA"]
    # Un origen sin presupuesto declarado no hereda el carril ancho.
    assert promotion_ceiling("COMITE", "PASILLO") == 7
    # El techo del carril declarado no depende de la clase de la sesion.
    assert promotion_ceiling("HANDOVER", "SIEMBRA") == DECLARED_BUDGET["SIEMBRA"]


def test_una_decision_impecable_colgada_de_un_daily_queda_afuera(tmp_path):
    """Las dos condiciones, no una: auditable Y su sesion en el corpus."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "daily", clase="HANDOVER")
    # El techo de HANDOVER la bloquea por el camino normal, asi que se fuerza:
    # el caso que interesa es una decision *valida* colgada de una sesion que no
    # es serie de decision.
    st.add_decision(Decision(
        id="", statement="Consolidar el picking de Pudahuel en una ola", owner="Marcela",
        date_decided=date(2026, 8, 1), criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix", meeting_id="daily"), force=True)

    c = st.corpus()
    assert len(c.decisions) == 0
    assert "cuelga de una sesion fuera del corpus" in c.decisions_fuera


def test_la_nota_del_corpus_dice_de_que_universo_salio_el_numero(tmp_path):
    """Una exclusion silenciosa es la misma mentira que un hueco: el numero sale
    mas lindo y nadie sabe de que universo salio."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "comite")
    _dec(st, "comite", 1)
    assert "todas dentro del corpus" in st.corpus().nota()

    _meet(st, "wa-w32", canal="ASINCRONICO")
    assert "canal asincronico" in st.corpus().nota()


# ----------------------------- dos columnas de toques, no un filtro
#
# El diseno original filtraba y devolvia UNA columna, con este argumento: "un
# caso que pertenece tiene por construccion al menos su propia reunion (el +1),
# asi que ningun filtro puede deflacionarlo a 1". Es FALSO: el +1 es una
# constante, no la reunion propia.


def _tema_con_vueltas(st, mid_decision, vueltas_fuera=0, vueltas_dentro=0):
    """Una decision cerrada en `mid_decision`, con vueltas previas repartidas."""
    f = date(2026, 8, 1)
    d = st.add_decision(Decision(
        id="", statement="Consolidar el picking de Pudahuel en una sola ola", owner="Marcela",
        date_decided=f, criteria="100% de los SKU clase A antes del 30-09",
        rationale="cambio el mix de pedidos", meeting_id=mid_decision))
    for j in range(vueltas_fuera):
        _meet(st, f"daily-{j}", clase="HANDOVER")
        st.add_question(OpenQuestion(id="", question="consolidamos la ola?", resolver="Marcela",
                                     resolve_by=f, blocks=[d.id], meeting_id=f"daily-{j}"))
    for j in range(vueltas_dentro):
        _meet(st, f"comite-prev-{j}")
        st.add_question(OpenQuestion(id="", question="consolidamos la ola?", resolver="Marcela",
                                     resolve_by=f, blocks=[d.id], meeting_id=f"comite-prev-{j}"))
    return d


def test_un_tema_masticado_fuera_del_corpus_se_deflacta_al_piso(tmp_path):
    """Tres cambios de turno y un comite: 4 toques reales, 1 en serie. La
    diferencia no se esconde — se publica, porque el trabajo ocurrio."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "comite")
    _tema_con_vueltas(st, "comite", vueltas_fuera=3)

    t = touches_to_decide(st)
    assert t.loc[0, "toques"] == 4
    assert t.loc[0, "toques_en_serie"] == 1
    assert t.loc[0, "en_corpus"] is True or bool(t.loc[0, "en_corpus"])

    ex = touches_excluidas(st)
    assert ex["casos_deflacionados_al_piso"] == 1
    assert ex["toques_no_contados"] == 3
    assert "el trabajo ocurrio" in ex["nota"]


def test_las_dos_columnas_coinciden_si_todo_paso_en_el_corpus(tmp_path):
    st = DecideStore(tmp_path / "decide")
    _meet(st, "comite")
    _tema_con_vueltas(st, "comite", vueltas_dentro=2)

    t = touches_to_decide(st)
    assert t.loc[0, "toques"] == t.loc[0, "toques_en_serie"] == 3
    assert touches_excluidas(st)["casos_deflacionados_al_piso"] == 0


def test_el_event_log_gana_una_columna_pero_no_pierde_filas(tmp_path):
    """Si se le sacaran los eventos de sesiones fuera del corpus,
    `lifecycle_rework` sub-reportaria el reproceso: un daily donde el tema volvio
    OCURRIO. Un log de eventos al que se le sacan eventos es la mentira
    silenciosa que la regla 3 prohibe."""
    st = DecideStore(tmp_path / "decide")
    _meet(st, "comite")
    _tema_con_vueltas(st, "comite", vueltas_fuera=3)

    df = build_event_log(st).df
    assert (df["activity"] == "DISCUTIDA").sum() == 3      # las tres siguen ahi
    assert df[df["activity"] == "DISCUTIDA"]["en_serie"].sum() == 0
    assert lifecycle_rework(st)["reuniones_extra"] == 3    # el reproceso se ve entero


def test_la_linea_base_recuerda_con_que_columna_se_congelo(serie_xmr):
    """Cambiar la definicion de un punto bajo limites congelados corrompe el
    grafico igual que recalcular los limites. Medido sobre la misma data:
    center 3,33 -> 2,42 y ucl 7,20 -> 3,87."""
    freeze_baseline(serie_xmr, date(2026, 8, 2), columna="toques")
    assert touches_xmr(serie_xmr)["columna"] == "toques"
    assert touches_xmr(serie_xmr, columna="toques")["ok"] is True

    with pytest.raises(ValueError, match="se congelo con 'toques'"):
        touches_xmr(serie_xmr, columna="toques_en_serie")


def test_congelar_con_una_columna_invalida_falla_temprano(serie_xmr):
    with pytest.raises(ValueError, match="columna desconocida"):
        freeze_baseline(serie_xmr, date(2026, 8, 2), columna="toques_inventados")


# --------------------------------- H6: el silencio deja de verse como salud
#
# Cero decisiones registradas podia significar cinco cosas —no hubo nada que
# decidir, nadie dijo la frase, Whisper fallo, el audio era inutilizable, nadie
# reviso la cola— y las cinco producian el mismo output: nada.


def _sesion(st, mid, graba=False):
    st.add_meeting(Meeting(id=mid, date=HOY, roster=ROSTER, facilitator="Marcela Perez",
                           consent=consent(graba=graba)))


def test_la_sesion_que_promovio_algo_esta_capturada(tmp_path):
    st = DecideStore(tmp_path / "d")
    _sesion(st, "m1")
    mk_decision(st, mid="m1")
    r = capture_state(st, "m1")
    assert r["estado"] == "CAPTURADA" and r["ok"] is True


def test_hubo_habla_y_ningun_borrador_es_SIN_RITUAL(tmp_path):
    from fdekit.decide.transcript import TranscriptStore

    st = DecideStore(tmp_path / "d")
    _sesion(st, "m1", graba=True)
    TranscriptStore(st.root, "m1").ingest_text("estuvimos viendo el tema del slotting.")
    r = capture_state(st, "m1")
    assert r["estado"] == "SIN_RITUAL"
    assert "nadie dijo la frase-marcador" in r["motivo"]


def test_el_silencio_total_se_declara_INDISTINGUIBLE(tmp_path):
    """El caso que da nombre al hueco. El sistema NO puede separar "no hubo nada
    que decidir" de "nadie registro nada", y elegir uno seria exactamente la
    mentira que este estado existe para impedir."""
    st = DecideStore(tmp_path / "d")
    _sesion(st, "m1")
    r = capture_state(st, "m1")
    assert r["estado"] == "SIN_REGISTRO"
    assert "NO puede distinguir" in r["motivo"]


def test_la_falla_declarada_gana_porque_el_sistema_no_la_ve(tmp_path):
    """`ASR_DEGRADADO` no se deriva: **no existe confianza de ASR en ninguna capa
    del kit**. Derivarla del texto seria fabricar el numero plausible y falso que
    la regla 3 prohibe. La declara quien corrio el pipeline."""
    st = DecideStore(tmp_path / "d")
    _sesion(st, "m1")
    m = st.get_meeting("m1")
    m.falla_captura = "ASR_DEGRADADO"
    st.save(m)
    assert capture_state(st, "m1")["estado"] == "ASR_DEGRADADO"

    m.falla_captura = "SE_ME_OCURRIO"
    with pytest.raises(ValidationError, match="falla de captura desconocida"):
        st.save(m)


def test_capturada_y_cola_pendiente_no_son_excluyentes(tmp_path):
    """Son dos hechos, no dos estados. La precedencia original ponia
    COLA_NO_REVISADA por encima de CAPTURADA, y como los borradores dejan
    residuo por construccion, una sesion sana se reportaba como fallida."""
    from fdekit.decide.draft import DecisionDraft, DraftStore

    st = DecideStore(tmp_path / "d")
    _sesion(st, "m1")
    mk_decision(st, mid="m1")
    DraftStore(st.root, "m1").append([DecisionDraft(
        kind="commitment", fields={"what": "mover 200 ubicaciones"},
        utterance="Rodrigo se compromete a mover 200 ubicaciones",
        confidence=0.4, missing=("evidencia",), meeting_id="m1")])

    r = capture_state(st, "m1")
    assert r["estado"] == "CAPTURADA"      # lo que paso
    assert r["cola_pendiente"] == 1        # ...y lo que quedo colgando, al lado


def test_la_hoja_dice_de_que_muestra_salen_los_numeros(tmp_path):
    """Un tablero construido sobre las sesiones que SI capturaron es una muestra
    sesgada, y es la que se estaba publicando."""
    st = DecideStore(tmp_path / "d")
    _sesion(st, "sana")
    _sesion(st, "muda")
    mk_decision(st, mid="sana")

    hoja = report(st)
    assert "1 de 2 sesiones sin captura" in hoja
    assert "SIN_REGISTRO" in hoja


def test_el_xmr_usa_la_columna_de_CORPUS_y_no_la_descriptiva(tmp_path):
    """El XmR es la metrica de CONTROL, y las de control filtran — las
    descriptivas no. Usaba `toques` por default, que es la descriptiva.

    Medido: una pregunta abierta desde una ventana de WhatsApp contra una
    decision de sala le suma un toque (3 -> 4) en la columna descriptiva. La
    ventana no es una serie de decision y no puede aportar puntos a un grafico
    de control.

    (No pude reproducir que el veredicto se diera vuelta, que es lo que el
    refutador reporto: las preguntas de chat quedan fechadas despues de la
    decision y `touches_to_decide` solo cuenta las previas. El defecto
    estructural si es real y es el que se arregla aca.)
    """
    st = DecideStore(tmp_path / "d")
    _meet(st, "comite")
    d = _tema_con_vueltas(st, "comite", vueltas_dentro=2)

    # la ventana de chat bloqueando la misma decision, ANTES de que se decidiera
    _meet(st, "wa-35", canal="ASINCRONICO")
    st.add_question(OpenQuestion(
        id="", question="esto contradice lo del comite?", resolver="Marcela",
        resolve_by=date(2026, 8, 1), blocks=[d.id], meeting_id="wa-35"), force=True)

    t = touches_to_decide(st)
    assert t.loc[0, "toques"] == 4            # la descriptiva ve la vuelta de chat
    assert t.loc[0, "toques_en_serie"] == 3   # la de control, no

    # y la linea base se congela con la columna de control, no con la descriptiva
    import json
    freeze_baseline(st, date(2026, 8, 2), baseline=1)
    fija = json.loads((st.root / "xmr_baseline.json").read_text(encoding="utf-8"))
    assert fija["columna"] == "toques_en_serie"
    assert fija["toques"] == [3.0]          # el valor de control, no el 4 descriptivo
