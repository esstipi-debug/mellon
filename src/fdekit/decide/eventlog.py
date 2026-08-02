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

import re
from datetime import date

import pandas as pd

from ..processmining import EventLog
from .store import DecideStore

# Actividades del ciclo de vida. `DISCUTIDA` y `REABIERTA` son el reproceso:
# es la lista que se le pasa a `rework_summary`.
REWORK_ACTIVITIES = ("DISCUTIDA", "REABIERTA")

_RE_HIST = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+([A-Z_]+):")


def build_event_log(store: DecideStore) -> EventLog:
    """Construye el log de ciclo de vida de las decisiones."""
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


def touches_to_decide(store: DecideStore) -> pd.DataFrame:
    """Reuniones en que un tema aparecio hasta su primer DECIDIDA.

    Es la metrica central del bucle. Un tema que necesito cinco vueltas para
    cerrarse no es un tema dificil: casi siempre es un tema al que le faltaba un
    dato que nadie fue a buscar.
    """
    log = build_event_log(store)
    if len(log) == 0:
        return pd.DataFrame(columns=["case_id", "toques", "dias_hasta_decidir", "decidida"])

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
                "dias_hasta_decidir": int((t_dec - primera).days),
                "decidida": t_dec.date().isoformat(),
            }
        )
    return pd.DataFrame(rows).sort_values("toques", ascending=False).reset_index(drop=True)
