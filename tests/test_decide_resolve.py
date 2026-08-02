"""Fase 3: ancla, canal HABLADA y resolutor de tres capas.

Aca vive el riesgo del sistema entero. Serena resuelve simbolos de forma
determinista porque abajo tiene un compilador; nosotros no. Estos tests
verifican la unica garantia que se puede dar en su lugar:

    No prometemos resolver siempre. Prometemos no mentir nunca en silencio.

Y los tres modos de error del diseno: falso negativo (barato y visible), falso
positivo de una mencion (tres detectores), y alias envenenado (cuatro
contramedidas obligatorias).
"""

from datetime import date

import pytest

from fdekit.decide import Consent, DecideStore, Decision, Meeting
from fdekit.decide.anchor import MAX_CITA, cite, find_utterance, freeze, verify
from fdekit.decide.resolve import (
    AliasStore,
    confirm,
    mark_disputed,
    resolve,
    slot_coherence,
    unalias,
)
from fdekit.decide.query import tick, why
from fdekit.decide.schema import Alias
from fdekit.decide.transcript import TranscriptStore, Utterance, mmss

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")

SEGMENTS = [
    {"start": 0.0, "end": 6.0, "text": "Buenos dias, gracias por venir."},
    {"start": 6.0, "end": 24.0, "text":
        "Queda decidido: reslotear la clase A a la zona dorada del CD Pudahuel, "
        "dueno Marcela, para el 30 de septiembre."},
    {"start": 24.0, "end": 40.0, "text":
        "El problema es que Fabian no da abasto en el turno noche."},
    {"start": 95.0, "end": 130.0, "text": "Listo, nos vemos la proxima."},
]


@pytest.fixture
def env(tmp_path):
    st = DecideStore(tmp_path / "d")
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo", recording_allowed=True,
                        retention_days=90),
        scope="pudahuel/slotting",
    ))
    ts = TranscriptStore(st.root, "m1")
    ts.ingest_segments(SEGMENTS)
    return st, ts


def mk(store, statement, slots, scope="pudahuel/slotting", **kw):
    return store.add_decision(Decision(
        id="", statement=statement, owner="Marcela Perez", date_decided=HOY,
        criteria="a mas tardar 2026-09-30", rationale="porque los numeros lo piden",
        meeting_id="m1", scope=scope, slots=slots, **kw,
    ))


# ------------------------------------------------------- canal HABLADA


def test_el_transcripto_guarda_tiempos_y_hash(env):
    _, ts = env
    utts = ts.load()
    assert len(utts) == 4
    assert utts[1].t_start == 6.0
    assert len(ts.sha256()) == 64


def test_texto_plano_no_inventa_timestamps(tmp_path):
    ts = TranscriptStore(tmp_path, "m2")
    utts = ts.ingest_text("Primera frase. Segunda frase.")
    assert [u.t_start for u in utts] == [None, None]
    assert mmss(None) == "--:--"


def test_la_ventana_no_trae_el_transcripto_entero(env):
    _, ts = env
    assert len(ts.window(1, before=1, after=1)) == 3


def test_el_hash_cambia_si_cambia_la_fuente(env):
    _, ts = env
    antes = ts.sha256()
    ts.write(ts.load() + [Utterance(idx=4, text="algo mas")])
    assert ts.sha256() != antes


# ------------------------------------------------------------- el ancla


def test_congela_la_cita_con_minuto_y_hash(env):
    _, ts = env
    a = freeze(ts, 1)
    assert "reslotear la clase A" in a.cita_congelada
    assert a.t_start == 6.0
    assert len(a.transcript_sha256) == 64
    assert "00:06" in cite(a)


def test_la_cita_se_recorta_a_500_chars(tmp_path):
    ts = TranscriptStore(tmp_path, "largo")
    ts.ingest_segments([{"start": 0, "end": 1, "text": "palabra " * 200}])
    a = freeze(ts, 0)
    assert len(a.cita_congelada) <= MAX_CITA
    assert a.validate() == []


def test_el_tercero_mencionado_se_redacta(env):
    """No estuvo, no consintio, y su nombre quedaria en un registro versionado
    que sobrevive al proyecto."""
    _, ts = env
    a = freeze(ts, 2, anonymize=("Fabian",))
    assert "Fabian" not in a.cita_congelada
    assert "[NOMBRE]" in a.cita_congelada


def test_la_cita_sobrevive_a_que_la_fuente_se_borre(env):
    """La gracia de copiar en vez de enlazar. Un puntero a un recurso con
    politica de retencion es un puntero colgante por diseno."""
    _, ts = env
    a = freeze(ts, 1)
    ts.path.unlink()
    assert "reslotear" in a.cita_congelada
    ok, motivo = verify(a, ts)
    assert not ok and "retencion" in motivo


def test_verify_detecta_que_la_fuente_cambio(env):
    _, ts = env
    a = freeze(ts, 1)
    assert verify(a, ts)[0] is True
    ts.write(ts.load()[:2])
    ok, motivo = verify(a, ts)
    assert not ok and "cambio" in motivo


def test_find_utterance_no_devuelve_el_enunciado_equivocado(env):
    _, ts = env
    assert find_utterance(ts, "Queda decidido: reslotear la clase A") == 1
    assert find_utterance(ts, "esto no esta en el transcripto") == -1


def test_why_devuelve_la_cita_verbatim_con_minuto(env):
    """El diferencial real contra una minuta comun: '¿por que decidimos esto?'
    pasa de arqueologia social de 40 minutos a una cita en 40 segundos."""
    st, ts = env
    d = mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    d.anchor = freeze(ts, 1)
    st.save(d)

    r = why(st, d.id)
    assert "reslotear la clase A" in r["cita"]
    assert r["minuto"] == "00:06"
    assert r["fuente"] == "intacta"


# ------------------------------------------------------------- L0 y L1


def test_l0_resuelve_el_id_literal(env):
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    for surface in ("como quedo D-001", "lo de D001"):
        r = resolve(surface, st, st.get_meeting("m1"))
        assert (r.symbol_id, r.tier, r.layer) == ("D-001", "EXTRACTED", "L0"), surface


def test_l0_hereda_el_simbolo_del_punto_de_agenda(env):
    """El analogo del nombre totalmente calificado."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    r = resolve("volviendo a lo de antes", st, st.get_meeting("m1"), agenda_symbol="D-001")
    assert r.symbol_id == "D-001" and r.layer == "L0"


def test_l1_resuelve_por_alias_confirmado(env):
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)

    r = resolve("retomando lo del slotting", st, st.get_meeting("m1"))
    assert (r.symbol_id, r.tier, r.layer) == ("D-001", "EXTRACTED", "L1")
    assert "confirmado por Marcela Perez" in r.evidence


def test_el_alias_no_resuelve_fuera_de_su_scope(env):
    """Un alias de un CD no puede resolver en otro. Es la contramedida numero
    uno contra el envenenamiento."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "quilicura/slotting", "Marcela Perez", HOY)

    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert r.layer != "L1"


def test_el_alias_no_resuelve_fuera_de_su_vigencia(env):
    """'Lo del slotting' es D-034 en marzo y D-051 en junio porque el tema
    recurre. La colision en el tiempo es el caso normal, no el accidente."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    AliasStore(st.root).add(Alias(
        surface_norm="lo del slotting", symbol_id="D-001", scope="pudahuel/slotting",
        valido_desde=date(2026, 1, 1), valido_hasta=date(2026, 6, 30),
        confirmado_por="Marcela Perez",
    ))
    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert r.layer != "L1"


def test_la_cobertura_deja_de_decir_fase_1_cuando_hay_menciones(env):
    """Tenia la fase clavada en 1, asi que `refs` seguia diciendo 'no hay
    resolucion automatica' con el resolutor cableado y menciones confirmadas.
    El modulo cuya doctrina es no mentir en silencio subreportaba su propia
    cobertura — la misma falla, en la direccion opuesta."""
    from fdekit.decide.query import referencing

    st, _ = env
    d = mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    assert "fase 1" in referencing(st, d.id)["coverage"]

    confirm(AliasStore(st.root), "lo del slotting", d.id, "pudahuel/slotting",
            "Marcela Perez", HOY)
    cov = referencing(st, d.id)["coverage"]
    assert "fase 1" not in cov
    assert "menciones" in cov
    assert referencing(st, d.id)["coverage_completa"] is False  # nunca completa


def test_alias_sin_scope_se_rechaza_al_crear():
    a = Alias(surface_norm="lo del slotting", symbol_id="D-001", scope="",
              valido_desde=HOY, confirmado_por="M")
    assert any("sin scope" in i for i in a.validate())


def test_alias_demasiado_corto_se_rechaza():
    a = Alias(surface_norm="eso", symbol_id="D-001", scope="x", valido_desde=HOY,
              confirmado_por="M")
    assert any("demasiado corta" in i for i in a.validate())


# ---------------------------------------------------------------- L2


def test_l2_distingue_dos_decisiones_de_slotting_en_sitios_distintos(env):
    """El falso positivo mas caro y mas frecuente. Un embedding las confundiria;
    los slots no, porque `sitio` es parte de la firma."""
    st, _ = env
    mk(st, "Reslotear la clase A del CD Pudahuel", {"proceso": "slotting", "sitio": "pudahuel"})
    mk(st, "Reslotear la clase A del CD Quilicura",
       {"proceso": "slotting", "sitio": "quilicura"}, scope="quilicura/slotting")

    r = resolve("lo del slotting en Pudahuel", st, st.get_meeting("m1"))
    assert r.symbol_id == "D-001"
    assert r.tier == "INFERRED"


def test_l2_reporta_empate_en_vez_de_elegir(env):
    """Igual que un compilador ante una referencia ambigua. Un sistema que
    adivina en silencio contamina el indice y es peor que no tener sistema."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting", "sitio": "pudahuel"})
    mk(st, "Cambiar la secuencia de slotting del mismo CD",
       {"proceso": "slotting", "sitio": "pudahuel"})

    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert r.symbol_id is None
    assert r.tier == "AMBIGUOUS"
    assert set(r.candidates) == {"D-001", "D-002"}
    assert "no una eleccion" in r.note


def test_sin_slots_reconocibles_no_hay_con_que_discriminar(env):
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    r = resolve("lo que hablamos el otro dia", st, st.get_meeting("m1"))
    assert r.symbol_id is None
    assert "ningun slot reconocible" in r.note


def test_el_falso_negativo_es_el_modo_dominante(env):
    """Barato y visible: cae en la cola, cuesta cinco segundos de humano y
    produce un alias que evita la proxima. Perder una decision es recuperable;
    inventar una es catastrofico."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "picking"})
    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert not r.resolved
    assert r.needs_human


# ------------------------------------------- coherencia de slots (error b)


def test_el_choque_de_slots_marca_sospechosa_aunque_otros_coincidan(env):
    """El caso 'mismo proceso, otro sitio'. Comparte `proceso` y choca en
    `sitio`: la regla literal del diseno —'no comparte ningun slot'— lo dejaria
    pasar, que es justo lo que existe para atrapar."""
    st, _ = env
    d = mk(st, "Reslotear la clase A del CD Pudahuel",
           {"proceso": "slotting", "sitio": "pudahuel"})
    ok, motivo = slot_coherence("hay que arreglar el slotting de Quilicura", d)
    assert not ok
    assert "choque de slots" in motivo
    assert "quilicura" in motivo and "pudahuel" in motivo


def test_sin_ningun_slot_en_comun_tambien_es_sospechosa(env):
    st, _ = env
    d = mk(st, "Reslotear la clase A del CD Pudahuel", {"proceso": "slotting"})
    ok, motivo = slot_coherence("el tema del turno de noche", d)
    assert not ok
    assert "no comparte ningun slot" in motivo


def test_la_cita_coherente_pasa(env):
    st, _ = env
    d = mk(st, "Reslotear la clase A del CD Pudahuel",
           {"proceso": "slotting", "sitio": "pudahuel"})
    assert slot_coherence("el slotting de Pudahuel quedo mal", d)[0] is True


# ------------------------------------------ alias envenenado (error c)


def test_unalias_retira_y_reprocesa_las_menciones(env):
    """La operacion que ningun enfoque original tenia. Sin ella, el
    determinismo que se gana es determinismo del error."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)
    assert resolve("lo del slotting", st, st.get_meeting("m1")).layer == "L1"

    r = unalias(astore, "lo del slotting", "se confirmo contra el simbolo equivocado", HOY)
    assert r["retirados"] == 1
    assert r["menciones_a_recola"]

    assert resolve("lo del slotting", st, st.get_meeting("m1")).layer != "L1"
    # El error queda escrito, no borrado.
    assert any(m.get("estado") == "REVERTIDA" for m in astore.mentions())


def test_unalias_sobre_algo_que_no_existe_no_revienta(env):
    st, _ = env
    r = unalias(AliasStore(st.root), "cualquier cosa", "prueba", HOY)
    assert r["retirados"] == 0


def test_la_colision_se_detecta_por_creacion_no_por_uso(env):
    """Detectarlo al crear es lo que evita que el primer uso despues de la
    colision resuelva mal con confianza 1,0."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting", "sitio": "pudahuel"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)

    nueva = mk(st, "Cambiar la secuencia de slotting del mismo CD",
               {"proceso": "slotting", "sitio": "pudahuel"})
    marcados = mark_disputed(astore, nueva, [st.get("D-001")])
    assert marcados == ["lo del slotting"]

    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert r.layer != "L1" or r.tier == "AMBIGUOUS"


def test_el_alias_en_disputa_explica_por_que_no_resolvio(env):
    """Un silencio sin explicacion parece un descuido."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)
    aliases = astore.load()
    aliases[0].estado = "EN_DISPUTA"
    astore.save_all(aliases)

    r = resolve("lo del slotting", st, st.get_meeting("m1"))
    assert "en_disputa" in r.evidence


def test_tick_dispara_la_disputa_solo_hacia_los_simbolos_anteriores(env):
    """Si se disputara en ambas direcciones, una colision mataria tambien el
    alias bueno del simbolo viejo."""
    st, _ = env
    mk(st, "Reslotear la clase A a la zona dorada", {"proceso": "slotting", "sitio": "pudahuel"})
    astore = AliasStore(st.root)
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)
    confirm(astore, "la secuencia nueva", "D-001", "pudahuel/slotting", "Marcela Perez", HOY)

    mk(st, "Cambiar la secuencia de slotting del mismo CD",
       {"proceso": "slotting", "sitio": "pudahuel"})
    r = tick(st, HOY)
    assert set(r["alias_en_disputa"]) == {"lo del slotting", "la secuencia nueva"}
    assert r["sin_cambios"] is False


def test_la_mencion_guarda_procedencia_completa(env):
    """El error queda escrito y reauditable en vez de desaparecer dentro del
    indice."""
    st, _ = env
    mk(st, "Reslotear la clase A del CD Pudahuel", {"proceso": "slotting", "sitio": "pudahuel"})
    mk(st, "Cambiar la secuencia de slotting del mismo CD",
       {"proceso": "slotting", "sitio": "pudahuel"})
    astore = AliasStore(st.root)
    previa = resolve("lo del slotting", st, st.get_meeting("m1"))
    confirm(astore, "lo del slotting", "D-001", "pudahuel/slotting", "Marcela Perez", HOY,
            resolution=previa, meeting_id="m1")

    m = astore.mentions()[0]
    assert m["capa_resolutora"] == "L2"
    assert m["tier"] == "AMBIGUOUS"
    assert m["candidatos_descartados"] == ["D-002"]
    assert m["confirmado_por"] == "Marcela Perez"
