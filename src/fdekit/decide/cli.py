"""Subcomandos `fdekit decide`. Fase 1: agenda | meeting | add | why | refs | close | tick.

Tiene que funcionar sin red y en el notebook prestado. Nada de lo que hay aca
importa torch, transformers ni networkx.
"""

from __future__ import annotations

import json
from datetime import date as _date
from datetime import datetime as _dt
from pathlib import Path

from .query import agenda, referencing, safe_close, tick, why
from .schema import (
    Assumption,
    Commitment,
    Consent,
    DECISION_ORIGIN,
    Decision,
    MEETING_CHANNEL,
    MEETING_CLASS,
    Meeting,
    OpenQuestion,
    parse_date,
)
from .store import DecideStore, PromotionBudgetExceeded, ValidationError


def _out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _print(df):
    print(df.to_string(index=False) if len(df) else "(vacio)")


def _store(a) -> DecideStore:
    return DecideStore(Path(a.root))


def _csv(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _guarded(fn):
    """Los errores de validacion son el producto, no una falla: se imprimen
    completos y se sale con codigo 2. Un `except Exception` generico esconderia
    justamente lo que hay que leer."""

    def wrapper(a):
        try:
            return fn(a)
        except ValidationError as exc:
            print(f"\nRECHAZADO — {exc.args[0]}\n")
            print("Un registro con huecos es peor que ninguno: genera falsa confianza.")
            print("Corregir, o usar --force si de verdad corresponde.")
            return 2
        except PromotionBudgetExceeded as exc:
            print(f"\nPRESUPUESTO EXCEDIDO — {exc}\n")
            return 2
        except KeyError as exc:
            print(f"\nNo existe: {exc}\n")
            return 2
        except ValueError as exc:
            # `slip` y `supersede` levantan ValueError con el motivo escrito
            # adentro, y sin esta rama salia un traceback en vez del mensaje.
            # No es cosmetico: el mensaje ES el producto de esas operaciones,
            # y un traceback ensena que la herramienta esta rota cuando lo que
            # paso es que la operacion se nego por una razon buena.
            print(f"\nRECHAZADO — {exc}\n")
            return 2

    return wrapper


# ---------------------------------------------------------------- comandos


def cmd_meeting(a):
    consent = Consent(
        granted=not a.no_consent,
        granted_by=a.consent_by,
        basis=a.basis,
        recording_allowed=a.recording,
        retention_days=a.retention_days,
    )
    m = Meeting(
        id=a.id,
        date=parse_date(a.date),
        roster=tuple(_csv(a.roster)),
        consent=consent,
        facilitator=a.facilitator,
        scope=a.scope,
        clase=a.clase,
        canal=a.canal,
    )
    _store(a).add_meeting(m, force=a.force)
    print(f"reunion {m.id} registrada | roster: {', '.join(m.roster)}")
    return 0


def cmd_add(a):
    st = _store(a)
    if a.kind == "decision":
        obj = st.add_decision(
            Decision(
                id="",
                statement=a.statement,
                owner=a.owner,
                date_decided=parse_date(a.date),
                criteria=a.criteria,
                rationale=a.rationale,
                meeting_id=a.meeting or "",
                depends_on=_csv(a.depends_on),
                scope=a.scope or "",
                # Sin esta linea el rescate de un acta historica aterrizaba como
                # REUNION —auditable, con fecha de hace seis meses— y era la
                # linea base entera del XmR. El campo existia y no tenia ruta de
                # escritura fuera de la siembra.
                origen=a.origen,
            ),
            force=a.force,
        )
    elif a.kind == "commitment":
        obj = st.add_commitment(
            Commitment(
                id="",
                decision_id=a.decision,
                what=a.what,
                owner=a.owner,
                due=parse_date(a.due),
                evidence_of_done=a.evidence,
                meeting_id=a.meeting or "",
            ),
            force=a.force,
        )
    elif a.kind == "assumption":
        obj = st.add_assumption(
            Assumption(
                id="",
                decision_id=a.decision,
                statement=a.statement,
                check_by=parse_date(a.check_by),
                source=a.source,
                meeting_id=a.meeting or "",
            ),
            force=a.force,
        )
        for adv in obj.advisories():
            print(f"aviso: {adv}")
    else:  # question
        obj = st.add_question(
            OpenQuestion(
                id="",
                question=a.question,
                resolver=a.resolver,
                resolve_by=parse_date(a.resolve_by),
                blocks=_csv(a.blocks),
                reopen_of=a.reopen_of or "",
                new_evidence=a.new_evidence or "",
                meeting_id=a.meeting or "",
            ),
            force=a.force,
        )
    print(f"{obj.id} registrado")
    return 0


def cmd_draft(a):
    """Corre el parser sobre un transcripto de texto plano y encola borradores."""
    from .draft import DraftStore, draft_decisions

    st = _store(a)
    meeting = st.get_meeting(a.meeting)
    texto = Path(a.file).read_text(encoding="utf-8")

    drafts = draft_decisions(texto, meeting.roster, meeting.date, meeting_id=a.meeting)
    DraftStore(a.root, a.meeting).append(drafts)

    listos = sum(1 for d in drafts if d.ready)
    print(f"{len(drafts)} borrador(es): {listos} listo(s), {len(drafts) - listos} a revisar")
    if not drafts:
        print(
            "\nCero capturas. No es un error del parser: el detector solo reconoce las\n"
            "formas verbales del lexico ('queda decidido', 'queda pendiente', 'asumimos',\n"
            "'se compromete a'). Si nadie las dijo, no hay nada que capturar — y esa\n"
            "tasa de declaracion es la metrica de supervivencia del sistema."
        )
    for d in drafts:
        marca = "OK " if d.ready else "REV"
        print(f"  {marca} {d.kind:<11} {str(d.fields.get('statement') or d.fields.get('what') or d.fields.get('question'))[:52]}")
    return 0


def cmd_review(a):
    """Revisa la cola. Objetivo duro: 90 segundos para una reunion de una hora.

    Si toma mas de 3 minutos, el detector esta mal calibrado, no el usuario.
    """
    from .draft import EXPIRA_EN_HORAS, DraftStore, expire, review_queue, to_entity

    st = _store(a)
    ds = DraftStore(a.root, a.meeting)
    drafts = ds.load()
    if not drafts:
        print("no hay borradores para esta reunion")
        return 0

    vivos, muertos = expire(drafts, _dt.now().astimezone())
    if muertos:
        # Sin el desglose, un lote historico expirado se reportaba como "a las
        # 24 h" y mandaba a buscar el bug donde no estaba.
        detalle = ", ".join(
            f"{d.kind} ({(d.expira_en_horas or EXPIRA_EN_HORAS) // 24 or 1} "
            f"{'dia(s)' if (d.expira_en_horas or EXPIRA_EN_HORAS) >= 24 else 'h'})"
            for d in muertos[:5]
        )
        print(f"{len(muertos)} borrador(es) expirado(s): no existen. {detalle}\n")

    from .anchor import cite, find_utterance, freeze
    from .transcript import TranscriptStore

    ts = TranscriptStore(a.root, a.meeting)
    anonimizar = tuple(x.strip() for x in (a.anonymize or "").split(",") if x.strip())

    promovidos, rechazados = [], []
    for d in [x for x in vivos if x.ready]:
        try:
            obj = to_entity(d, a.meeting)
            # Congelar la cita ANTES de persistir: si el canal HABLADA caduca,
            # el DECIDIDA tiene que sobrevivir igual. Por eso se copia y no se
            # enlaza.
            if hasattr(obj, "anchor") and ts.exists():
                idx = find_utterance(ts, d.utterance)
                if idx >= 0:
                    obj.anchor = freeze(ts, idx, anonymize=anonimizar)
            obj = _ADD[d.kind](st, obj, force=False)
            promovidos.append(
                f"{obj.id} {d.kind}"
                + (f"  {cite(obj.anchor)}" if getattr(obj, "anchor", None) and not obj.anchor.empty else "")
            )
        except (ValidationError, PromotionBudgetExceeded, KeyError) as exc:
            rechazados.append(f"{d.kind}: {exc.args[0].splitlines()[0]}")

    for linea in promovidos:
        print(f"  + {linea}")
    for linea in rechazados:
        print(f"  x {linea}")

    cola = review_queue(vivos)
    if cola:
        print(f"\n{len(cola)} pendiente(s) de revision, ordenados por lo que falta:\n")
        for d in cola:
            print(f"  [{d.kind}] {d.utterance[:80]}")
            print(f"      falta: {', '.join(d.missing)}")
            for n in d.notes:
                print(f"      nota: {n}")
        # El plazo se lee de la cola, no se afirma. Con un lote historico adentro
        # esta linea decia "24 h" sobre borradores que viven dos semanas: el
        # mismo patron de siempre, un texto plausible y falso que nadie verifica.
        horas = {d.expira_en_horas or EXPIRA_EN_HORAS for d in cola}
        plazo = (
            f"{min(horas) // 24} dia(s)" if min(horas) >= 24 * 2 else f"{min(horas)} h"
        )
        print(
            "\nCompletar con `fdekit decide add ...` usando el enunciado de arriba.\n"
            f"Lo que no se revise en {plazo} expira: la decision no existe."
            + (
                "\nHay borradores con plazos distintos en la cola; el que manda es el "
                "mas corto.\nLos de acta historica lo dicen en su nota."
                if len(horas) > 1 else ""
            )
        )

    ds.rewrite([d for d in cola])
    st.rebuild_index()
    return 0


def cmd_transcribe(a):
    """Audio o texto plano -> canal HABLADA, con su hash."""
    from .transcript import TranscriptStore, transcribe_meeting

    st = _store(a)
    m = st.get_meeting(a.meeting)
    ts = TranscriptStore(a.root, a.meeting)

    if a.text:
        utts = ts.ingest_text(Path(a.text).read_text(encoding="utf-8"))
        nota = "texto plano: sin timestamps, las citas van a quedar sin mm:ss"
    else:
        if not m.consent.recording_allowed:
            print(
                "El consentimiento de esta reunion no permite grabar.\n"
                "El sistema degrada limpio a solo-DECIDIDA y sigue entregando ~60% del\n"
                "valor. Re-registrar la reunion con --recording si corresponde."
            )
            return 2
        utts, _ = transcribe_meeting(a.audio, a.root, a.meeting)
        nota = "audio local con Whisper"

    m.transcript_sha256 = ts.sha256()
    m.transcript_ref = str(ts.path)
    st.save(m)
    print(f"{len(utts)} enunciado(s) | sha256 {ts.sha256()[:12]} | {nota}")
    return 0


def cmd_resolve(a):
    """Resuelve una mencion contra el registro. Nunca adivina en silencio."""
    from .resolve import resolve

    st = _store(a)
    r = resolve(a.surface, st, st.get_meeting(a.meeting), agenda_symbol=a.agenda_symbol)
    _out(r.to_dict())
    if r.tier == "AMBIGUOUS":
        print(
            "\nAMBIGUO: es un error reportado, no una eleccion. Igual que un compilador\n"
            "ante una referencia ambigua. Confirmar con `decide confirm`."
        )
    return 0


def cmd_confirm(a):
    """El humano colapsa la incertidumbre y el sistema aprende un alias."""
    from .resolve import AliasStore, confirm, resolve, slot_coherence

    st = _store(a)
    m = st.get_meeting(a.meeting)
    simbolo = st.get(a.symbol)

    if a.quote:
        ok, motivo = slot_coherence(a.quote, simbolo)
        if not ok and not a.force:
            print(f"\nSOSPECHOSA — {motivo}\n")
            print(
                "Confirmar esto escribiria un alias que resuelve mal para siempre, y con\n"
                "confianza 1,0. Es el caso 'mismo proceso, otro sitio', donde un resolutor\n"
                "semantico se equivoca con mas seguridad. Revisar, o --force si de verdad\n"
                "corresponde."
            )
            return 2

    astore = AliasStore(st.root)
    previa = resolve(a.surface, st, m, alias_store=astore)
    alias = confirm(
        astore, a.surface, simbolo, a.scope or m.scope or simbolo.scope,
        a.by, m.date, resolution=previa, meeting_id=a.meeting,
    )
    print(
        f"alias '{alias.surface_norm}' -> {alias.symbol_id} en scope '{alias.scope}'\n"
        f"desde {alias.valido_desde}, confirmado por {alias.confirmado_por}\n"
        "La proxima vez esta mencion resuelve en L1, deterministico."
    )
    return 0


def cmd_unalias(a):
    from .resolve import AliasStore, unalias

    st = _store(a)
    r = unalias(AliasStore(st.root), a.surface, a.reason, _date.today())
    _out(r)
    return 0


def cmd_aliases(a):
    from .resolve import AliasStore

    for al in AliasStore(_store(a).root).load():
        hasta = al.valido_hasta.isoformat() if al.valido_hasta else "abierto"
        print(
            f"{al.estado:<11} {al.surface_norm:<28} -> {al.symbol_id:<8} "
            f"scope={al.scope or '(vacio)'} [{al.valido_desde} .. {hasta}] "
            f"por {al.confirmado_por} ({len(al.mentions_resueltas)} mencion/es)"
        )
    return 0


def _leer_filas(path: Path):
    """La planilla de siembra: CSV con encabezado, separador `;`.

    `;` y no `,` porque las filas de criterio llevan comas —"100% de los SKU
    clase A, antes del 30-09"— y un CSV con comas se parte en la mitad de la
    unica columna que la regla 1 exige completa.
    """
    import csv

    from .seed import FilaSiembra

    with path.open(encoding="utf-8-sig", newline="") as fh:
        filas = []
        for n, row in enumerate(csv.DictReader(fh, delimiter=";"), start=2):
            faltan = [c for c in ("statement", "owner", "criteria", "rationale")
                      if not (row.get(c) or "").strip()]
            if faltan:
                raise ValueError(
                    f"fila {n} de {path.name}: faltan columnas {faltan}. La siembra no "
                    "completa huecos: una fila incompleta se arregla en la planilla, "
                    "donde la esta mirando quien la declaro."
                )
            filas.append(FilaSiembra(
                statement=row["statement"].strip(),
                owner=row["owner"].strip(),
                criteria=row["criteria"].strip(),
                rationale=row["rationale"].strip(),
                alias=(row.get("alias") or "").strip(),
                scope=(row.get("scope") or "").strip(),
                date_decided=parse_date(row["fecha"].strip()) if (row.get("fecha") or "").strip() else None,
            ))
    return filas


def cmd_seed(a):
    """La siembra del kickoff. Imprime lo que entro y **lo que no**."""
    from .seed import seed_decisions

    st = _store(a)
    rep = seed_decisions(st, a.meeting, _leer_filas(Path(a.file)),
                         by=a.by, today=_date.today())

    print(f"\nsembradas: {len(rep.escritas)} -> {', '.join(rep.escritas) or '(ninguna)'}")
    print(f"alias:     {len(rep.alias_escritos)} -> {', '.join(rep.alias_escritos) or '(ninguno)'}")
    if rep.rechazadas:
        print("\nNO entraron al registro:")
        for statement, motivos in rep.rechazadas:
            print(f"  - {statement[:70]}")
            for m in motivos:
                print(f"      {m}")
    if rep.alias_rechazados:
        print("\nalias NO escritos:")
        for superficie, motivo in rep.alias_rechazados:
            print(f"  - '{superficie}': {motivo}")
    print(f"\n{rep.nota}")
    # Codigo 2 si algo quedo afuera: la siembra corrio, pero hay trabajo humano
    # pendiente y un `&&` en un script no puede seguir como si nada.
    return 2 if (rep.rechazadas or rep.alias_rechazados) else 0


def cmd_brief(a):
    """Lo unico que un recien llegado va a leer entero."""
    from .rotacion import onboarding_brief

    b = onboarding_brief(_store(a), a.scope, today=_date.today())
    if a.json:
        _out(b)
        return 0

    print(f"\n# Que esta decidido en '{b['scope']}'\n")
    print(f"_{b['nota']}_\n")
    for d in b["decisiones"]:
        marca = "" if d["auditable"] else f"  [{d['origen']} — no auditable]"
        dep = f"  (depende de {', '.join(d['depende_de'])})" if d["depende_de"] else ""
        print(f"{d['id']} — {d['statement']}{dep}{marca}")
        print(f"    dueno {d['owner']} · desde {d['decidida']} · listo cuando: {d['criteria']}")
        print(f"    porque: {d['rationale']}")
    if b["supuestos"]:
        print("\n## Lo que sostiene todo esto (y su edad)\n")
        for s in b["supuestos"]:
            print(f"{s['id']} [{s['status']}] {s['statement']}")
            print(f"    hace {s['edad_dias']} dias · fuente: {s['source']} · "
                  f"se revisa el {s['check_by']}")
    if b["compromisos"]:
        print("\n## Lo que sigue abierto\n")
        for c in b["compromisos"]:
            corridas = f" ({c['corridas']} corridas)" if c["corridas"] else ""
            print(f"{c['id']} {c['due']} {c['owner']}: {c['what']}{corridas}")
    return 0


def cmd_publish(a):
    """La pagina que el cliente si va a abrir."""
    from .render import write_html

    p = write_html(_store(a), a.scope, Path(a.out), today=_date.today(), idioma=a.idioma)
    print(f"escrito: {p}")
    print(
        "Un archivo, sin red y sin login: se adjunta, se sube al SharePoint del\n"
        "proyecto o se imprime. Va agrupado por decision y no por persona, y lo\n"
        "dice en la pagina: un registro leido como tablero de desempeno individual\n"
        "mata el sistema en dos semanas sin ninguna senal tecnica."
    )
    return 0


def cmd_reassign(a):
    from .rotacion import reassign_owner

    r = reassign_owner(_store(a), a.sale, a.entra, today=_date.today(), apply=a.apply)
    print(f"\n{len(r['reasignados'])} a reasignar: {', '.join(r['reasignados']) or '(nada)'}")
    if r["intactos"]:
        print(f"{len(r['intactos'])} intacto(s) por estar cerrados: {', '.join(r['intactos'])}")
    print(f"\n{r['nota']}")
    return 0


def cmd_huerfanos(a):
    from .rotacion import duenos_huerfanos

    r = duenos_huerfanos(_store(a), tuple(_csv(a.activos)), today=_date.today())
    for persona, ids in r["huerfanos"].items():
        print(f"{persona}: {', '.join(ids)}")
    print(f"\n{r['nota']}")
    return 2 if r["total"] else 0


def cmd_card(a):
    from .rotacion import tarjeta_de_piso

    print(tarjeta_de_piso(_store(a), a.id))
    return 0


def cmd_slip(a):
    """Correr la fecha de un compromiso. Una linea, desde el telefono.

    Es deliberadamente el comando mas corto del CLI: si renegociar cuesta mas
    que incumplir en silencio, la gente elige el silencio, y ahi el tablero de
    vencidos pasa a ser ruido que todos ignoran sin ninguna senal tecnica.
    """
    from .query import slip

    st = _store(a)
    r = slip(st, a.id, parse_date(a.nueva_fecha), motivo=a.motivo, por=a.por,
             today=_date.today())
    print(f"{r['id']}: {r['de']} -> {r['a']} ({r['corridas_hacia_adelante']} corrida/s)")
    if r["escalado"]:
        print(f"\n{r['nota']}\nPregunta abierta: {r['escalado']}")
        return 2
    return 0


def cmd_seed_minutes(a):
    """Las actas anteriores al sistema, a la cola. No promueve nada."""
    from .seed import seed_minutes

    st = _store(a)
    raiz = Path(a.dir)
    actas = sorted(p for p in raiz.iterdir() if p.is_file()) if raiz.is_dir() else [raiz]
    rep = seed_minutes(st, a.meeting, actas, now=_dt.now().astimezone())

    print(f"\nactas leidas: {len(rep.actas_leidas)} -> {rep.borradores} borrador(es) a la cola")
    if rep.actas_sin_captura:
        print("\nleidas pero SIN capturar nada:")
        for n in rep.actas_sin_captura:
            print(f"  - {n}")
    if rep.actas_rechazadas:
        print("\nNO se procesaron:")
        for nombre, motivo in rep.actas_rechazadas:
            print(f"  - {nombre}: {motivo}")
    print(f"\n{rep.nota}")
    print(
        "\nRevisar con `fdekit decide review --meeting <id>`. Lo que siga vigente se "
        "registra con\n`fdekit decide add decision --origen ACTA_HISTORICA`: sin ese "
        "flag el rescate\naterriza como REUNION, auditable y con fecha vieja, y se "
        "vuelve la linea base del XmR."
    )
    return 2 if rep.actas_rechazadas else 0


_ADD = {
    "decision": lambda st, o, force: st.add_decision(o, force=force),
    "commitment": lambda st, o, force: st.add_commitment(o, force=force),
    "assumption": lambda st, o, force: st.add_assumption(o, force=force),
    "question": lambda st, o, force: st.add_question(o, force=force),
}


def cmd_pilot(a):
    """Fase 0. En la sala no entra software: entra una planilla y una hoja."""
    from .pilot import (
        baseline_from_calendar,
        evaluate_pilot,
        load_calendar,
        scaffold,
        score_survey,
        score_tally,
        weekly_panel,
    )

    if a.pilot_cmd == "init":
        r = scaffold(a.out, site=a.site, metric_owner=a.owner,
                     control_series=a.control, start=parse_date(a.start) if a.start else None)
        _out(r)
        print(
            "\nDos semanas. Nada de esto se instala en la sala.\n"
            "Si la disciplina no se sostiene con una planilla, no se sostiene con software."
        )
        return 0

    if a.pilot_cmd == "baseline":
        b = baseline_from_calendar(load_calendar(a.calendar))
        _out(b)
        return 0

    if a.pilot_cmd == "score":
        r = score_tally(a.tally)
        _out(r)
        print(f"\n{r['veredicto']}")
        return 0 if r.get("ok") else 2

    if a.pilot_cmd == "survey":
        _out(score_survey(a.survey))
        return 0

    cal = load_calendar(a.calendar)
    panel = weekly_panel(cal, _csv(a.treat), _csv(a.control), parse_date(a.cutoff))
    v = evaluate_pilot(panel)
    _out(v.to_dict())
    print(
        f"\n{'SIGUE' if v.passes else 'SE APAGA'} — "
        f"{v.pct_vs_baseline}% contra el control, umbral {v.threshold_pct}%.\n{v.note}"
    )
    return 0 if v.passes else 2


def cmd_metrics(a):
    from .metrics import (
        circular_minutes,
        decider_executor_presence,
        index_quality,
        read_metrics,
        reopening_split,
        report,
        touches_xmr,
        volume_gate,
    )

    st = _store(a)
    if a.json:
        _out({
            "volumen": volume_gate(st),
            "lectura": read_metrics(st),
            "reaperturas": reopening_split(st),
            "minutos_circulares": circular_minutes(st),
            "presencia_decisor_ejecutor": decider_executor_presence(st),
            "indice": index_quality(st),
            "xmr_toques": touches_xmr(st),
        })
    else:
        print(report(st))
    return 0


def cmd_mine(a):
    """Process mining sobre el ciclo de vida de las decisiones."""
    from ..processmining import variants
    from .eventlog import build_event_log, lifecycle_rework, touches_to_decide
    from .metrics import volume_gate

    st = _store(a)
    gate = volume_gate(st)
    if not gate["ok"] and not a.force:
        print(f"{gate['veredicto']}\n\nUsar --force para verlo igual.")
        return 2

    log = build_event_log(st)
    if len(log) == 0:
        print("sin eventos: el registro no tiene decisiones")
        return 0

    print(f"{len(log):,} eventos | {log.n_cases} decisiones | {len(log.activities)} estados\n")
    print("-- toques para decidir --")
    _print(touches_to_decide(st).head(10))
    print("\n-- variantes del ciclo de vida --")
    _print(variants(log, top=10, collapse_repeats=False))
    print("\n-- reproceso, en reuniones extra --")
    _out(lifecycle_rework(st))
    return 0


def cmd_export(a):
    from .export import to_mermaid, write_graphify

    st = _store(a)
    if a.mermaid:
        Path(a.mermaid).write_text(to_mermaid(st), encoding="utf-8")
        print(f"mermaid en {a.mermaid}")
    r = write_graphify(st, a.out, force=a.force, include_inferred=a.include_inferred)
    _out(r)
    return 0 if r["escrito"] else 2


def cmd_agenda(a):
    ag = agenda(_store(a), a.meeting, today=parse_date(a.today) if a.today else None)
    print(ag.to_markdown())
    return 0


def _log_query(store, op: str, actor: str, symbol: str, hit: bool, in_room: bool):
    """Cierra el hueco H2: todas las metricas median escritura y ninguna
    lectura. Un registro que nadie consulta es un pasivo."""
    from .metrics import QueryLog

    QueryLog(store.root).log(op, actor or "anonimo", symbol, hit, in_room)


def cmd_why(a):
    st = _store(a)
    try:
        r = why(st, a.id)
    except KeyError:
        _log_query(st, "why", a.actor, a.id, hit=False, in_room=a.in_room)
        raise
    _log_query(st, "why", a.actor, a.id, hit=True, in_room=a.in_room)
    _out(r)
    return 0


def cmd_refs(a):
    st = _store(a)
    try:
        r = referencing(st, a.id, depth=a.depth)
    except KeyError:
        _log_query(st, "refs", a.actor, a.id, hit=False, in_room=a.in_room)
        raise
    _log_query(st, "refs", a.actor, a.id, hit=True, in_room=a.in_room)
    _out(r)
    print(f"\nCobertura: {r['coverage']}")
    return 0


def cmd_supersede(a):
    from .query import supersede

    r = supersede(_store(a), a.id, a.by, reason=a.reason, apply=a.apply, today=_date.today())
    _out(r)
    if r["triage"]:
        print(
            f"\n{r['referencias_a_resolver']} referencia(s) siguen apuntando a {a.id}.\n"
            "supersede NO las reasigna: en codigo renombrar arregla las referencias,\n"
            "aca cambiar el alcance las invalida. Resolverlas a mano."
        )
    if not a.apply:
        print("\n(reporte de triage: no se escribio nada. Agregar --apply)")
    return 0


def cmd_head(a):
    from .query import head_of

    r = head_of(_store(a), a.id)
    _out(r)
    if r.get("head") and r["head"] != a.id:
        print(f"\n{a.id} fue superada. La que rige hoy es {r['head']}.")
    return 0


def cmd_close(a):
    r = safe_close(_store(a), a.id, apply=a.apply, reason=a.reason, today=_date.today())
    _out(r)
    return 0 if r["closed"] else 2


def cmd_tick(a):
    st = _store(a)
    today = parse_date(a.today) if a.today else _date.today()
    r = tick(st, today, apply=not a.dry_run)
    _out(r)
    if not a.dry_run:
        st.rebuild_index()
    return 0


# ----------------------------------------------------------------- parser


def register(subparsers):
    p = subparsers.add_parser(
        "decide", help="canal DECIDIDA: registro de decisiones de reunion (fases 0-4)"
    )
    p.add_argument("--root", default="decide", help="directorio del registro")
    p.add_argument("--force", action="store_true", help="persistir aunque validate() falle")
    sub = p.add_subparsers(dest="decide_cmd", required=True)

    m = sub.add_parser("meeting", help="registra una reunion y su roster")
    m.add_argument("--id", required=True, help="YYYY-MM-DD-slug")
    m.add_argument("--date", required=True)
    m.add_argument("--roster", required=True, help="nombres separados por coma")
    m.add_argument("--facilitator", default="")
    m.add_argument("--consent-by", default="", dest="consent_by")
    m.add_argument("--basis", default="interes_legitimo")
    m.add_argument("--no-consent", action="store_true", dest="no_consent")
    m.add_argument("--recording", action="store_true")
    m.add_argument("--retention-days", type=int, default=None, dest="retention_days")
    m.add_argument("--scope", default="", help="scope de la serie, p.ej. pudahuel/slotting")
    m.add_argument("--clase", default="COMITE", choices=list(MEETING_CLASS),
                   help="el perfil de la clase solo puede BAJAR el techo de 7")
    m.add_argument("--canal", default="SINCRONICO", choices=list(MEETING_CHANNEL))
    m.set_defaults(func=_guarded(cmd_meeting))

    ad = sub.add_parser("add", help="registra decision, compromiso, supuesto o pregunta")
    ak = ad.add_subparsers(dest="kind", required=True)

    d = ak.add_parser("decision")
    d.add_argument("--statement", required=True)
    d.add_argument("--owner", required=True)
    d.add_argument("--criteria", required=True, help="debe traer un numero o predicado verificable")
    d.add_argument("--rationale", required=True)
    d.add_argument("--date", required=True)
    d.add_argument("--meeting", default="")
    d.add_argument("--depends-on", default="", dest="depends_on")
    d.add_argument("--scope", default="")
    d.add_argument("--origen", default="REUNION", choices=list(DECISION_ORIGIN),
                   help="solo REUNION es auditable y cuenta para la compuerta de volumen")
    d.set_defaults(func=_guarded(cmd_add))

    c = ak.add_parser("commitment")
    c.add_argument("--decision", required=True)
    c.add_argument("--what", required=True)
    c.add_argument("--owner", required=True)
    c.add_argument("--due", required=True, help="fecha absoluta YYYY-MM-DD")
    c.add_argument("--evidence", required=True, dest="evidence")
    c.add_argument("--meeting", default="")
    c.set_defaults(func=_guarded(cmd_add))

    s = ak.add_parser("assumption")
    s.add_argument("--decision", required=True)
    s.add_argument("--statement", required=True)
    s.add_argument("--check-by", required=True, dest="check_by")
    s.add_argument("--source", default="sin_fuente")
    s.add_argument("--meeting", default="")
    s.set_defaults(func=_guarded(cmd_add))

    q = ak.add_parser("question")
    q.add_argument("--question", required=True)
    q.add_argument("--resolver", required=True)
    q.add_argument("--resolve-by", required=True, dest="resolve_by")
    q.add_argument("--blocks", default="")
    q.add_argument("--reopen-of", default="", dest="reopen_of")
    q.add_argument("--new-evidence", default="", dest="new_evidence")
    q.add_argument("--meeting", default="")
    q.set_defaults(func=_guarded(cmd_add))

    dr = sub.add_parser("draft", help="parsea un transcripto y encola borradores")
    dr.add_argument("--meeting", required=True)
    dr.add_argument("--file", required=True, help="transcripto en texto plano")
    dr.set_defaults(func=_guarded(cmd_draft))

    rv = sub.add_parser("review", help="promueve los borradores listos y lista lo que falta")
    rv.add_argument("--meeting", required=True)
    rv.add_argument("--anonymize", default="", help="nombres a redactar, separados por coma")
    rv.set_defaults(func=_guarded(cmd_review))

    tc = sub.add_parser("transcribe", help="audio o texto -> canal HABLADA con hash")
    tc.add_argument("--meeting", required=True)
    tc.add_argument("--audio", help="ruta del audio (requiere el extra 'audio')")
    tc.add_argument("--text", help="transcripto en texto plano, sin timestamps")
    tc.set_defaults(func=_guarded(cmd_transcribe))

    rs = sub.add_parser("resolve", help="resuelve una mencion: L0 -> L1 -> L2")
    rs.add_argument("surface")
    rs.add_argument("--meeting", required=True)
    rs.add_argument("--agenda-symbol", default=None, dest="agenda_symbol")
    rs.set_defaults(func=_guarded(cmd_resolve))

    cf = sub.add_parser("confirm", help="confirma una mencion y aprende el alias")
    cf.add_argument("surface")
    cf.add_argument("--symbol", required=True)
    cf.add_argument("--meeting", required=True)
    cf.add_argument("--by", required=True)
    cf.add_argument("--scope", default="")
    cf.add_argument("--quote", default="", help="cita para el chequeo de coherencia de slots")
    cf.set_defaults(func=_guarded(cmd_confirm))

    ua = sub.add_parser("unalias", help="retira un alias y reprocesa lo que decidio")
    ua.add_argument("surface")
    ua.add_argument("--reason", required=True)
    ua.set_defaults(func=_guarded(cmd_unalias))

    sd = sub.add_parser(
        "seed",
        help="siembra las decisiones vigentes declaradas en el kickoff (origen SIEMBRA)",
    )
    sd.add_argument("--meeting", required=True,
                    help="la reunion de siembra, YA registrada con `decide meeting`")
    sd.add_argument("--file", required=True, help="planilla CSV con separador ';'")
    sd.add_argument("--by", required=True, help="quien declara las filas")
    sd.set_defaults(func=_guarded(cmd_seed))

    sm = sub.add_parser(
        "minutes",
        help="encola actas anteriores al sistema; no promueve nada (origen ACTA_HISTORICA)",
    )
    sm.add_argument("--meeting", required=True, help="la reunion del lote, YA registrada")
    sm.add_argument("--dir", required=True,
                    help="carpeta de actas, o un archivo. El nombre trae la fecha: "
                         "'YYYY-MM-DD-...'; sin fecha, el acta se rechaza")
    sm.set_defaults(func=_guarded(cmd_seed_minutes))

    sl = sub.add_parser("slip", help="corre la fecha de un compromiso, conservando la anterior")
    sl.add_argument("id")
    sl.add_argument("--nueva-fecha", required=True, dest="nueva_fecha")
    sl.add_argument("--motivo", required=True)
    sl.add_argument("--por", required=True, help="quien acordo la fecha nueva")
    sl.set_defaults(func=_guarded(cmd_slip))

    br = sub.add_parser("brief", help="que esta decidido, en que orden y que lo sostiene")
    br.add_argument("--scope", default="", help="acota por CD o area; vacio trae todo")
    br.add_argument("--json", action="store_true")
    br.set_defaults(func=_guarded(cmd_brief))

    pb = sub.add_parser("publish", help="pagina HTML para el cliente: sin red, sin login")
    pb.add_argument("--scope", default="")
    pb.add_argument("--out", required=True, help="ruta del .html")
    pb.add_argument("--idioma", default="es", choices=["es", "en"])
    pb.set_defaults(func=_guarded(cmd_publish))

    ra = sub.add_parser("reassign", help="rota el dueno de todo lo vivo de una persona")
    ra.add_argument("--sale", required=True)
    ra.add_argument("--entra", required=True, help="tiene que estar en algun roster")
    ra.add_argument("--apply", action="store_true", help="sin esto solo reporta")
    ra.set_defaults(func=_guarded(cmd_reassign))

    hf = sub.add_parser("orphans", help="lo vivo que apunta a gente que ya no esta")
    hf.add_argument("--activos", required=True, help="lista separada por comas")
    hf.set_defaults(func=_guarded(cmd_huerfanos))

    cd = sub.add_parser("card", help="tres lineas de un compromiso, para el que ejecuta")
    cd.add_argument("id")
    cd.set_defaults(func=_guarded(cmd_card))

    al = sub.add_parser("aliases", help="lista la tabla de alias")
    al.set_defaults(func=_guarded(cmd_aliases))

    pl = sub.add_parser("pilot", help="fase 0: piloto de proceso, sin software en la sala")
    ps = pl.add_subparsers(dest="pilot_cmd", required=True)

    pi = ps.add_parser("init", help="escribe planilla, hoja de sala, encuesta y protocolo")
    pi.add_argument("--out", default="piloto")
    pi.add_argument("--site", default="")
    pi.add_argument("--owner", default="", help="dueno de la metrica del lado del cliente")
    pi.add_argument("--control", default="", help="serie de control que NO adopta nada")
    pi.add_argument("--start", default="")
    pi.set_defaults(func=_guarded(cmd_pilot))

    pb = ps.add_parser("baseline", help="la variable dependiente, del export de calendario")
    pb.add_argument("--calendar", required=True)
    pb.set_defaults(func=_guarded(cmd_pilot))

    psc = ps.add_parser("score", help="puntua la planilla contra el criterio de continuacion")
    psc.add_argument("--tally", required=True)
    psc.set_defaults(func=_guarded(cmd_pilot))

    pv = ps.add_parser("survey", help="puntua la encuesta de tres preguntas")
    pv.add_argument("--survey", required=True)
    pv.set_defaults(func=_guarded(cmd_pilot))

    pd_ = ps.add_parser("verdict", help="criterio de muerte a la semana 10, contra el control")
    pd_.add_argument("--calendar", required=True)
    pd_.add_argument("--cutoff", required=True, help="fin del periodo pre, YYYY-MM-DD")
    pd_.add_argument("--treat", required=True, help="series tratadas, separadas por coma")
    pd_.add_argument("--control", required=True, help="series de control, separadas por coma")
    pd_.set_defaults(func=_guarded(cmd_pilot))

    mt = sub.add_parser("metrics", help="la hoja imprimible; respeta la compuerta de volumen")
    mt.add_argument("--json", action="store_true")
    mt.set_defaults(func=_guarded(cmd_metrics))

    mn = sub.add_parser("mine", help="process mining sobre el ciclo de vida de las decisiones")
    mn.set_defaults(func=_guarded(cmd_mine))

    ex = sub.add_parser("export", help="vista derivada a graphify (nunca fuente de verdad)")
    ex.add_argument("--out", default="graphify-in/decide.json")
    ex.add_argument("--mermaid", default="")
    ex.add_argument("--include-inferred", action="store_true", dest="include_inferred")
    ex.set_defaults(func=_guarded(cmd_export))

    g = sub.add_parser("agenda", help="agenda calculada; puede recomendar cancelar")
    g.add_argument("--meeting", required=True)
    g.add_argument("--today", default=None)
    g.set_defaults(func=_guarded(cmd_agenda))

    w = sub.add_parser("why", help="por que se decidio esto")
    w.add_argument("id")
    w.add_argument("--actor", default="", help="quien consulta (para medir lectura)")
    w.add_argument("--in-room", action="store_true", dest="in_room")
    w.set_defaults(func=_guarded(cmd_why))

    r = sub.add_parser("refs", help="todo lo que cuelga de una decision")
    r.add_argument("id")
    r.add_argument("--depth", type=int, default=1)
    r.add_argument("--actor", default="")
    r.add_argument("--in-room", action="store_true", dest="in_room")
    r.set_defaults(func=_guarded(cmd_refs))

    sp = sub.add_parser("supersede", help="marca SUPERADA y lista lo que hay que retriar")
    sp.add_argument("id", help="la decision que queda superada")
    sp.add_argument("--by", required=True, help="la decision que la reemplaza")
    sp.add_argument("--reason", default="")
    sp.add_argument("--apply", action="store_true", help="escribe; exige --reason")
    sp.set_defaults(func=_guarded(cmd_supersede))

    hd = sub.add_parser("head", help="sigue la cadena de supersesion hasta la que rige hoy")
    hd.add_argument("id")
    hd.set_defaults(func=_guarded(cmd_head))

    cl = sub.add_parser("close", help="cierra si nada cuelga; si algo cuelga, lo lista")
    cl.add_argument("id")
    cl.add_argument("--apply", action="store_true", help="marca REVERTIDA; exige --reason")
    cl.add_argument("--reason", default="")
    cl.set_defaults(func=_guarded(cmd_close))

    t = sub.add_parser("tick", help="vence compromisos y supuestos, marca riesgo y zombis")
    t.add_argument("--today", default=None)
    t.add_argument("--dry-run", action="store_true", dest="dry_run")
    t.set_defaults(func=_guarded(cmd_tick))
