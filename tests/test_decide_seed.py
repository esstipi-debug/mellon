"""H4 — el arranque en frio: siembra, alias iniciales, ingesta historica.

El dia 1 el registro esta vacio y compite contra tres anos de historial: `why()`
y `referencing()` devuelven vacio justo en las cuatro semanas donde se juega la
adopcion, y las ~20 decisiones que YA gobiernan —tomadas antes de que el sistema
existiera— son exactamente las que se van a re-discutir.

La tentacion obvia de cerrarlo es relajar `validate()` para que 30 filas
declaradas de memoria entren de una. Eso es la regla dura 1 de frente: un
registro con huecos genera falsa confianza. Estos tests fijan lo contrario —
**la siembra no relaja nada y publica todo lo que dejo afuera**.
"""

from datetime import date

import pytest

from fdekit.decide import Consent, DecideStore, Decision, Meeting, why
from fdekit.decide.draft import DraftStore, expire, to_entity
from fdekit.decide.metrics import index_quality, volume_gate
from fdekit.decide.resolve import AliasStore, resolve
from fdekit.decide.seed import FilaSiembra, seed_aliases, seed_decisions, seed_minutes
from fdekit.decide.store import PromotionBudgetExceeded

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="kickoff", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"),
        clase="KICKOFF", scope="pudahuel",
    ))
    return st


def fila(i=1, **kw):
    base = dict(
        statement=f"El corte de pedidos del CD Pudahuel es a las 14:00 en la ola {i}",
        owner="Marcela Perez",
        criteria="100% de los pedidos cortados antes de las 14:00",
        rationale="el transporte sale a las 15:00 y no espera",
        alias="lo del corte",
        scope="pudahuel",
    )
    base.update(kw)
    return FilaSiembra(**base)


# ------------------------------------------------------ la siembra escribe


def test_la_siembra_persiste_con_origen_y_sin_force(store):
    r = seed_decisions(store, "kickoff", [fila()], by="Marcela Perez", today=HOY)
    assert r.escritas == ["D-001"]
    d = store.get("D-001")
    assert d.origen == "SIEMBRA"
    assert d.auditable is False


def test_la_fila_que_no_pasa_validate_va_a_la_cola_con_el_nombre_de_lo_que_falta(store):
    """La regla dura 1. Forzar la cuantificacion es el valor de los 90 minutos
    de la sesion de siembra, no un obstaculo que hay que saltar con `force`."""
    r = seed_decisions(
        store, "kickoff",
        [fila(), fila(2, criteria="que funcione mejor"), fila(3, owner="Alguien de afuera")],
        by="Marcela Perez", today=HOY,
    )
    assert r.escritas == ["D-001"]
    assert len(r.rechazadas) == 2
    motivos = " ".join(m for _, ms in r.rechazadas for m in ms)
    assert "predicado verificable" in motivos
    assert "roster" in motivos
    # Y no quedo ninguna a medias en disco.
    assert len(store.decisions()) == 1


def test_la_siembra_nunca_usa_force(store):
    """`force` es un interruptor general, no una exencion puntual: apaga roster,
    criterio, rationale, ancla Y presupuesto de una sola vez, y no deja marca en
    el archivo resultante. Una sembrada con `force` es indistinguible de una
    auditada: no falla, miente."""
    import inspect

    from fdekit.decide import seed

    fuente = inspect.getsource(seed)
    assert "force=True" not in fuente


def test_la_fecha_futura_se_rechaza(store):
    """Una decision vigente se tomo en el pasado. Una con fecha futura es un
    error de tipeo que despues corre la linea base del XmR."""
    r = seed_decisions(store, "kickoff", [fila(date_decided=date(2027, 1, 1))],
                       by="Marcela Perez", today=HOY)
    assert r.escritas == []
    assert "futura" in " ".join(m for _, ms in r.rechazadas for m in ms)


# --------------------------------------------------------- los dos carriles


def test_treinta_sembradas_no_consumen_el_techo_de_la_sala(store):
    """El carril declarado es paralelo. Sin esto la unica salida es borrar el
    `--meeting`, que es peor: por ahi no hay roster ni consentimiento."""
    r = seed_decisions(store, "kickoff", [fila(i) for i in range(30)],
                       by="Marcela Perez", today=HOY)
    assert len(r.escritas) == 30

    for i in range(7):
        store.add_decision(Decision(
            id="", statement=f"Reslotear la clase A a la zona dorada, tanda {i}",
            owner="Marcela Perez", date_decided=HOY,
            criteria="antes del 30-09", rationale="el mix cambio", meeting_id="kickoff"))
    with pytest.raises(PromotionBudgetExceeded):
        store.add_decision(Decision(
            id="", statement="Reslotear la clase B tambien", owner="Marcela Perez",
            date_decided=HOY, criteria="antes del 30-09", rationale="el mix cambio",
            meeting_id="kickoff"))


def test_las_sembradas_no_abren_la_compuerta_de_volumen(store):
    """30 sembradas + 20 reales = 50 y la compuerta se abriria sin una sola
    metrica real detras. Es el peor caso posible: la compuerta existe justo
    para impedir eso."""
    seed_decisions(store, "kickoff", [fila(i) for i in range(30)],
                   by="Marcela Perez", today=HOY)
    g = volume_gate(store)
    assert g["decisiones"] == 0
    assert g["decisiones_en_disco"] == 30
    assert g["ok"] is False


def test_why_de_una_sembrada_no_afirma_que_hubo_reunion(store):
    """`why()` de una sembrada devolvia el mismo texto que una registrada en una
    reunion real: 'se registro sin canal HABLADA'. Para una sembrada eso es
    literalmente falso y hace concluir que existio una sesion donde se decidio."""
    seed_decisions(store, "kickoff", [fila()], by="Marcela Perez", today=HOY)
    r = why(store, "D-001")
    assert r["origen"] == "SIEMBRA"
    assert r["auditable"] is False
    assert "declarada" in r["nota_origen"]
    assert "sin canal HABLADA" not in r.get("nota_cita", "")


# ------------------------------------------------------------- los alias


def test_el_alias_sembrado_resuelve_en_L1_con_acentos_y_mayusculas(store):
    """La trampa central del hueco: sin el `_norm` canonico, `_l1` nunca hace
    match. La siembra escribe 30 filas, el comando dice que funciono, y el
    resolutor jamas las usa."""
    seed_decisions(store, "kickoff", [fila(alias="Lo del Córte")],
                   by="Marcela Perez", today=HOY)
    r = resolve("hablemos de lo del corte", store, store.get_meeting("kickoff"))
    assert (r.symbol_id, r.tier, r.layer) == ("D-001", "EXTRACTED", "L1")


def test_la_sembrada_lleva_slots_y_por_eso_su_alias_es_disputable(store):
    """Sin slots, `mark_disputed` no puede disputar el alias NUNCA y `_l2`
    tampoco puede proponer el simbolo: 30 alias declarados de memoria quedan
    resolviendo con confianza 1,0 de forma permanente e irrevisable."""
    seed_decisions(store, "kickoff", [fila()], by="Marcela Perez", today=HOY)
    assert store.get("D-001").slots


def test_la_fila_sin_slots_no_siembra_su_alias_y_sale_nombrada(store):
    """Un enunciado del que `extract_slots` no saca nada no puede aliasearse.
    La decision entra igual —es valida— pero el alias no, y la fila se NOMBRA:
    un alias que no se escribio en silencio es la regla 3 rota."""
    r = seed_decisions(
        store, "kickoff",
        [fila(statement="Mantener el arreglo vigente tal como quedo el ano pasado",
              criteria="ninguna excepcion aprobada", alias="lo de siempre")],
        by="Marcela Perez", today=HOY,
    )
    assert r.escritas == ["D-001"]
    assert r.alias_escritos == []
    assert any("slots" in m for _, m in r.alias_rechazados)


def test_el_alias_sin_scope_se_rechaza(store):
    """No existe el alias global: resolveria en contextos donde nadie lo
    confirmo, que es el camino directo al envenenamiento del indice."""
    st = DecideStore(store.root.parent / "otro")
    st.add_meeting(Meeting(
        id="kickoff", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"), clase="KICKOFF",
    ))  # reunion SIN scope
    r = seed_decisions(st, "kickoff", [fila(scope="")], by="Marcela Perez", today=HOY)
    assert r.alias_escritos == []
    assert AliasStore(st.root).load() == []


def test_el_alias_que_colisiona_se_rechaza(store):
    """Dos filas con la misma frase y el mismo scope apuntando a simbolos
    distintos dejan `_l1` en AMBIGUOUS para esa frase para siempre: la frase mas
    usada de la cuenta queda inservible y nadie sabe por que."""
    r = seed_decisions(store, "kickoff", [fila(1), fila(2)],
                       by="Marcela Perez", today=HOY)
    assert len(r.escritas) == 2
    assert r.alias_escritos == ["lo del corte"]
    assert any("colision" in m for _, m in r.alias_rechazados)


def test_la_siembra_de_alias_no_escribe_menciones(store):
    """`resolucion_automatica_pct` es la metrica que tiene que SUBIR sesion a
    sesion. Sembrar menciones la arranca desde un piso que fabricamos nosotros."""
    seed_decisions(store, "kickoff", [fila(i) for i in range(5)],
                   by="Marcela Perez", today=HOY)
    astore = AliasStore(store.root)
    assert astore.mentions() == []
    assert not astore.mention_path.exists()
    assert index_quality(store)["menciones"] == 0


def test_el_cli_puede_declarar_el_origen_al_registrar_a_mano(store, tmp_path):
    """`origen` existia sin ninguna ruta de escritura fuera de la siembra, y ese
    era el agujero: el rescate de un acta historica —el producto declarado del
    ejercicio— aterrizaba como REUNION, auditable, con fecha de hace seis meses.

    `touches_xmr` ordena por fecha ascendente y toma los primeros doce como
    linea base congelada: las fechas viejas del historial SERIAN la linea base
    entera. Regla dura 6, rota por la puerta de al lado.
    """
    from fdekit.cli import build_parser

    a = build_parser().parse_args([
        "decide", "--root", str(store.root), "add", "decision",
        "--statement", "El corte de pedidos del CD Pudahuel es a las 14:00",
        "--owner", "Marcela Perez", "--criteria", "100% cortados antes de las 14:00",
        "--rationale", "el transporte sale a las 15:00", "--date", "2026-02-01",
        "--meeting", "kickoff", "--origen", "ACTA_HISTORICA",
    ])
    assert a.func(a) == 0
    d = store.get("D-001")
    assert d.origen == "ACTA_HISTORICA"
    assert d.auditable is False
    assert volume_gate(store)["decisiones"] == 0


# -------------------------------------------------- la ingesta de actas

ACTA = (
    "Queda decidido: el corte de pedidos del CD Pudahuel es a las 14:00, "
    "dueno Marcela Perez, porque el transporte sale a las 15:00.\n"
    "Rodrigo Munoz se compromete a mover 200 ubicaciones para el 30 de septiembre.\n"
)
AHORA = __import__("datetime").datetime(2026, 8, 1, 9, 0).astimezone()


def _acta(tmp_path, nombre, texto=ACTA):
    p = tmp_path / nombre
    p.write_text(texto, encoding="utf-8")
    return p


def test_la_fecha_del_acta_sale_del_nombre_del_archivo(store, tmp_path):
    """Un acta de febrero procesada contra hoy resuelve 'el 30 de septiembre' al
    ano equivocado y nace un compromiso con plazo inventado. La fecha base no
    viene de ningun reloj: viene del nombre."""
    r = seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    assert r.actas_leidas == ["2026-02-10-comite.txt"]
    assert r.borradores > 0
    d = DraftStore(store.root, "kickoff").load()[0]
    assert d.fields["date_decided"] == "2026-02-10"


def test_el_acta_sin_fecha_en_el_nombre_se_rechaza(store, tmp_path):
    """Jamas se procesa contra hoy: eso fabrica plazos y corre la linea base."""
    r = seed_minutes(store, "kickoff", [_acta(tmp_path, "acta-comite-final.txt")], now=AHORA)
    assert r.actas_leidas == []
    assert any("fecha" in m for _, m in r.actas_rechazadas)
    assert DraftStore(store.root, "kickoff").load() == []


def test_ningun_borrador_historico_sale_listo(store, tmp_path):
    """La pregunta real del ejercicio no es que se decidio: es si SIGUE
    VIGENTE. Auto-promover el 20% que parsea limpio llenaria la agenda de la
    primera reunion real con seis meses de compromisos vencidos."""
    seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    drafts = DraftStore(store.root, "kickoff").load()
    assert drafts
    assert all(not d.ready for d in drafts)
    assert all("sigue_vigente" in d.missing for d in drafts)


def test_el_lote_historico_no_se_evapora_con_la_ventana_de_24_horas(store, tmp_path):
    """Seis meses de actas revisadas al dia siguiente desaparecian, y el unico
    rastro era una linea impresa en consola. La politica viaja en el OBJETO, no
    en el llamador ni en una constante global: subir la global romperia la
    propiedad que sostiene el flujo corriente ('lo no revisado en 24 h no
    existe')."""
    from datetime import timedelta

    seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    drafts = DraftStore(store.root, "kickoff").load()

    vivos, muertos = expire(drafts, AHORA + timedelta(hours=48))
    assert muertos == [] and len(vivos) == len(drafts)
    # Pero no es eterno: a las dos semanas se acaba igual.
    vivos, muertos = expire(drafts, AHORA + timedelta(days=15))
    assert vivos == [] and len(muertos) == len(drafts)


def test_el_borrador_de_reunion_sigue_expirando_a_las_24_horas(store, tmp_path):
    """El lote historico es la excepcion; el flujo corriente no se toca."""
    from datetime import timedelta

    from fdekit.decide.draft import draft_decisions

    d = draft_decisions(ACTA, ROSTER, HOY, meeting_id="kickoff", now=AHORA)[0]
    assert d.expired(AHORA + timedelta(hours=25))


def test_el_borrador_historico_promueve_con_su_origen(store, tmp_path):
    """El agujero que el diseno marco CRITICO: el rescate aterrizaba como
    REUNION, auditable, con fecha de hace seis meses — y `touches_xmr` toma los
    primeros doce por fecha ascendente como linea base congelada."""
    seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    d = next(x for x in DraftStore(store.root, "kickoff").load() if x.kind == "decision")
    # Lo que hace el humano al revisar: contesta la unica pregunta del ejercicio.
    d.missing = tuple(m for m in d.missing if m != "sigue_vigente")

    obj = to_entity(d, "kickoff")
    assert obj.origen == "ACTA_HISTORICA"
    assert obj.auditable is False


def test_el_acta_ilegible_no_mata_el_lote(store, tmp_path):
    """Seis meses de actas es un lote grande: un archivo roto no puede llevarse
    puestos los otros veinte, y tampoco puede desaparecer callado."""
    buena = _acta(tmp_path, "2026-02-10-comite.txt")
    rota = tmp_path / "2026-03-01-comite.txt"
    rota.write_bytes(b"\xff\xfe\x00 esto no es utf-8 \xff")

    r = seed_minutes(store, "kickoff", [rota, buena], now=AHORA)
    assert r.actas_leidas == ["2026-02-10-comite.txt"]
    assert len(r.actas_rechazadas) == 1
    assert r.borradores > 0


def test_el_acta_sin_marcadores_sale_nombrada_y_no_como_exito(store, tmp_path):
    """Cero capturas no es un error del parser, pero decir 'lei 20 actas' sin
    decir que 14 no produjeron nada es la regla 3 rota: el lector concluye que
    el historial esta en el registro."""
    r = seed_minutes(
        store, "kickoff",
        [_acta(tmp_path, "2026-02-10-comite.txt", "Se converso largo sobre el turno noche.\n")],
        now=AHORA,
    )
    assert r.actas_leidas == ["2026-02-10-comite.txt"]
    assert r.actas_sin_captura == ["2026-02-10-comite.txt"]
    assert r.borradores == 0
    assert "ni un borrador" in r.nota


def test_el_review_no_promete_24_horas_sobre_un_lote_que_vive_dos_semanas(store, tmp_path, capsys):
    """El cierre de `review` afirmaba '24 h' pasara lo que pasara. Con un lote
    historico en la cola eso es un texto plausible y falso — el patron dominante
    del repo — y manda a buscar el bug donde no esta."""
    from fdekit.cli import build_parser

    seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    a = build_parser().parse_args(
        ["decide", "--root", str(store.root), "review", "--meeting", "kickoff"]
    )
    assert a.func(a) == 0
    salida = capsys.readouterr().out
    assert "14 dia(s)" in salida
    assert "24 h" not in salida


def test_la_ingesta_historica_no_escribe_nada_en_el_registro(store, tmp_path):
    """No auto-promueve NADA, ni siquiera lo que parsea limpio."""
    seed_minutes(store, "kickoff", [_acta(tmp_path, "2026-02-10-comite.txt")], now=AHORA)
    assert store.decisions() == []
    assert volume_gate(store)["decisiones_en_disco"] == 0


def test_seed_aliases_es_la_ruta_para_el_glosario_precargado(store):
    """El glosario del cliente no cuelga de una fila de siembra: son alias de
    decisiones que ya existen."""
    seed_decisions(store, "kickoff", [fila(alias="")], by="Marcela Perez", today=HOY)
    r = seed_aliases(store, "kickoff", [("La Ola Grande", "D-001", "pudahuel")],
                     by="Marcela Perez", today=HOY)
    assert r.alias_escritos == ["la ola grande"]
    res = resolve("como quedo la ola grande", store, store.get_meeting("kickoff"))
    assert res.symbol_id == "D-001" and res.layer == "L1"
