"""Adaptador al `EventLog` de process mining. El mejor ratio valor/codigo del set.

El registro de decisiones ya es un log de eventos: cada decision es un caso, y
su ciclo de vida —discutida, decidida, reabierta, revertida— son las
actividades. Mapearlo desbloquea `variants`, `rework_summary`,
`directly_follows`, `bottlenecks` y `to_mermaid`, todo ya testeado en el kit.

    case_id    = decision_id
    activity   = estado del ciclo de vida
    timestamp  = fecha del evento
    resource   = meeting_id

Y entonces se puede preguntar cosas que hoy nadie puede: cuantas reuniones pasan
entre que un tema se menciona y se decide, que fraccion de las decisiones se
reabre, y —con `rework_summary`— cuanto cuesta la reapertura.

REGLA DURA heredada del diseno: ninguna metrica agregada se computa sobre
aristas no confirmadas. Los eventos de aca salen del registro, que es
DECIDIDA — nada viene del resolutor probabilistico. Un tablero construido sobre
resolucion probabilistica miente con cara de rigor, y un gerente actua sobre el
el lunes.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..processmining import EventLog
from .schema import HIST_RE
from .store import DecideStore

# Actividades del ciclo de vida. `DISCUTIDA` y `REABIERTA` son el reproceso:
# es la lista que se le pasa a `rework_summary`.
REWORK_ACTIVITIES = ("DISCUTIDA", "REABIERTA")

# La expresion vive en `schema`, al lado de `hist_line`, que es quien escribe.
# Tener el lector aca y el escritor alla, unidos solo por una convencion, es
# exactamente como las supersesiones desaparecieron del log sin que nada fallara.
_RE_HIST = HIST_RE


def build_event_log(store: DecideStore, c=None) -> EventLog:
    """Construye el log de ciclo de vida de las decisiones.

    `c` es un `Corpus` ya calculado; se pasa para no recalcularlo por cada
    llamada en cadena. Si falta, se calcula.
    """
    decisions = store.decisions()
    questions = store.questions()
    meetings = {m.id: m for m in store.meetings()}

    def meeting_date(mid: str, fallback: date) -> date:
        m = meetings.get(mid)
        return m.date if m else fallback

    rows: list[tuple] = []

    for d in decisions:
        # DISCUTIDA: cada pregunta abierta que bloqueaba esta decision es una
        # vuelta previa del tema. Es lo que hace medible el "toques para
        # decidir" — un tema que aparecio en cinco reuniones y recien en la
        # quinta se decidio.
        for q in questions:
            if d.id in q.blocks:
                rows.append((d.id, "DISCUTIDA", meeting_date(q.meeting_id, d.date_decided),
                             q.meeting_id or "?", q.resolver))

        rows.append((d.id, "DECIDIDA", d.date_decided, d.meeting_id or "?", d.owner))

        for q in questions:
            if q.reopen_of == d.id:
                rows.append((d.id, "REABIERTA", meeting_date(q.meeting_id, d.date_decided),
                             q.meeting_id or "?", q.resolver))

        # El historial guarda "YYYY-MM-DD ESTADO: motivo" — es la unica fuente
        # de la fecha en que una decision cambio de estado.
        for linea in d.historial_statements:
            m = _RE_HIST.match(linea)
            if m:
                rows.append((d.id, m.group(2), date.fromisoformat(m.group(1)),
                             d.meeting_id or "?", d.owner))

        if d.status == "EN_RIESGO":
            # Sin fecha propia: se ancla al vencimiento del supuesto que la puso
            # en riesgo, que es el evento que efectivamente ocurrio.
            vencidos = [
                a.check_by for a in store.assumptions()
                if a.decision_id == d.id and a.pone_en_riesgo
            ]
            if vencidos:
                rows.append((d.id, "EN_RIESGO", min(vencidos), d.meeting_id or "?", d.owner))

    if not rows:
        return EventLog(pd.DataFrame(columns=["case_id", "activity", "timestamp", "resource", "location"]))

    df = pd.DataFrame(rows, columns=["case_id", "activity", "timestamp", "resource", "owner"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["location"] = df.pop("owner")
    # El log GANA una columna, no pierde filas. Si se le sacaran los eventos de
    # las sesiones fuera del corpus, `lifecycle_rework` sub-reportaria el
    # reproceso —un daily donde el tema volvio OCURRIO— y `circular_minutes`
    # cambiaria de significado el set `con_avance`. Un log de eventos al que se
    # le sacan eventos es la mentira silenciosa que la regla 3 prohibe.
    #
    # Las metricas de CONTROL filtran por esta columna; las DESCRIPTIVAS no.
    en_corpus = (c or store.corpus()).meeting_ids
    df["en_serie"] = df["resource"].isin(en_corpus)
    return EventLog(df)


def lifecycle_rework(store: DecideStore) -> dict:
    """Reproceso del ciclo de vida, en la unidad correcta.

    `processmining.rework_summary` sirve tal cual para el log del WMS, pero
    aplicado aca importa un supuesto que no vale: su `annual_hours_lost`
    multiplica por 250 turnos al ano porque asume que la ventana observada es un
    turno. En un registro de decisiones la ventana son meses y el "costo
    directo" de una transicion es la semana que pasa entre dos reuniones, que es
    espera, no trabajo. El resultado son millones de horas perdidas al ano — un
    numero absurdo que igual se ve serio en una tabla.

    La unidad correcta del reproceso de decisiones es la **reunion extra**: cada
    vuelta de un tema es una aparicion mas en una agenda, y eso si se puede
    convertir en minutos-persona con la duracion real del transcripto.
    """
    log = build_event_log(store)
    if len(log) == 0:
        return {"reuniones_extra": 0, "por_actividad": {}, "nota": "sin eventos"}

    df = log.df
    meetings = {m.id: m for m in store.meetings()}
    por_actividad = {
        act: {
            "ocurrencias": int((df["activity"] == act).sum()),
            "decisiones_afectadas": int(df[df["activity"] == act]["case_id"].nunique()),
            "pct_decisiones": round(
                df[df["activity"] == act]["case_id"].nunique() / log.n_cases * 100, 1
            ),
        }
        for act in REWORK_ACTIVITIES
        if (df["activity"] == act).any()
    }

    extra = sum(v["ocurrencias"] for v in por_actividad.values())

    # Minutos-persona solo donde hay transcripto con tiempos. Sin audio no se
    # estima: se dice que falta.
    from .transcript import TranscriptStore

    minutos = 0.0
    medidas = 0
    for _, row in df[df["activity"].isin(REWORK_ACTIVITIES)].iterrows():
        m = meetings.get(row["resource"])
        if not m:
            continue
        utts = TranscriptStore(store.root, m.id).load()
        ini = [u.t_start for u in utts if u.t_start is not None]
        fin = [u.t_end for u in utts if u.t_end is not None]
        if ini and fin:
            minutos += (max(fin) - min(ini)) / 60 * len(m.roster)
            medidas += 1

    return {
        "reuniones_extra": extra,
        "por_actividad": por_actividad,
        "minutos_persona": round(minutos, 1),
        "eventos_con_tiempo_medido": medidas,
        "eventos_sin_tiempo": extra - medidas,
        "nota": (
            "el costo del reproceso de decisiones se mide en reuniones extra, no en "
            "horas de turno. Los minutos-persona salen de la duracion real del "
            "transcripto; los eventos sin audio no entran al numero."
        ),
    }


TOUCH_COLUMNS = ("toques", "toques_en_serie")


def touches_to_decide(store: DecideStore, c=None) -> pd.DataFrame:
    """Reuniones en que un tema aparecio hasta su primer DECIDIDA.

    Es la metrica central del bucle. Un tema que necesito cinco vueltas para
    cerrarse no es un tema dificil: casi siempre es un tema al que le faltaba un
    dato que nadie fue a buscar.

    Devuelve **dos columnas y no una**, porque son dos preguntas distintas:

      `toques`           todas las vueltas. Cuanto trabajo costo de verdad.
      `toques_en_serie`  solo las de sesiones del corpus. Comparable entre si.

    El diseno original filtraba y devolvia una sola, con este argumento: "un
    caso que pertenece tiene por construccion al menos su propia reunion (el
    +1), asi que ningun filtro puede deflacionarlo a 1". **Es falso.** El `+1`
    es una constante, no la reunion propia: cuando TODAS las vueltas previas
    ocurrieron fuera del corpus, el caso cae al piso. Medido — un tema masticado
    en tres cambios de turno y cerrado en el comite pasa de 4 toques a 1, y el
    trabajo real desaparece del numero.

    Y hay una razon mas fuerte para no elegir por el llamador: los limites del
    XmR estan CONGELADOS (regla 6). Cambiar cual columna alimenta la serie
    corrompe el grafico exactamente igual que recalcular los limites — medido,
    center 3,33 -> 2,42 y ucl 7,20 -> 3,87 sobre la misma data. Por eso
    `freeze_baseline` guarda con QUE columna se congelo, y `touches_xmr` se
    niega a mezclar.
    """
    corpus = c or store.corpus()
    log = build_event_log(store, corpus)
    if len(log) == 0:
        return pd.DataFrame(
            columns=["case_id", "toques", "toques_en_serie", "en_corpus",
                     "dias_hasta_decidir", "decidida"]
        )

    df = log.df
    rows = []
    for cid, g in df.groupby("case_id"):
        dec = g[g["activity"] == "DECIDIDA"]
        if dec.empty:
            continue
        t_dec = dec["timestamp"].min()
        previas = g[(g["activity"] == "DISCUTIDA") & (g["timestamp"] <= t_dec)]
        primera = previas["timestamp"].min() if not previas.empty else t_dec
        rows.append(
            {
                "case_id": cid,
                "toques": int(previas["resource"].nunique()) + 1,
                "toques_en_serie": int(previas[previas["en_serie"]]["resource"].nunique()) + 1,
                # El CASO entra a la serie solo si su propia sesion esta en el
                # corpus. Es el filtro de caso, distinto del de toque.
                "en_corpus": cid in corpus.decision_ids,
                "dias_hasta_decidir": int((t_dec - primera).days),
                "decidida": t_dec.date().isoformat(),
            }
        )
    return pd.DataFrame(rows).sort_values("toques", ascending=False).reset_index(drop=True)


def touches_excluidas(store: DecideStore, c=None) -> dict:
    """Que se dejo afuera al pasar de `toques` a `toques_en_serie`.

    Va SIEMPRE al lado del grafico. Un filtro que no publica lo que filtro es la
    forma mas barata de mejorar un numero.
    """
    t = touches_to_decide(store, c)
    if t.empty:
        return {"casos": 0, "casos_fuera_del_corpus": 0, "casos_deflacionados_al_piso": 0}

    deflacionados = t[(t["toques"] > 1) & (t["toques_en_serie"] == 1)]
    perdidos = int((t["toques"] - t["toques_en_serie"]).sum())
    return {
        "casos": len(t),
        "casos_fuera_del_corpus": int((~t["en_corpus"]).sum()),
        "casos_deflacionados_al_piso": len(deflacionados),
        "ids_deflacionados": list(deflacionados["case_id"]),
        "toques_no_contados": perdidos,
        "nota": (
            f"{len(deflacionados)} caso(s) perdieron TODAS sus vueltas previas al filtrar "
            "por corpus: el trabajo ocurrio, pero fuera de una serie de decision. "
            f"En total no se cuentan {perdidos} toque(s)."
        ) if perdidos else "ninguna vuelta quedo fuera de la serie.",
    }
