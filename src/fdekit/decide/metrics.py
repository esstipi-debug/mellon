"""Las metricas del sistema: como se sabe si redujo friccion.

Todas se calculan con el propio registro. Ninguna necesita instrumentacion
aparte. Se publican en una hoja imprimible que se lleva a la reunion de
operaciones — **no en un tablero**, doctrina explicita del kit.

Tres reglas duras:

  1. **Compuerta de volumen.** Nada de esto dice algo antes de ~50 decisiones y
     ~15 reuniones. Bajo ese volumen las metricas re-descubren los titulos de la
     agenda, y prometer el numero bonito el dia 1 es la forma mas rapida de
     quemar la credibilidad del sistema.
  2. **Ninguna metrica agregada sobre aristas no confirmadas.** Si se quiere el
     numero, se calcula solo sobre el subconjunto EXTRACTED y se reporta la
     cobertura al lado.
  3. **Se mide la LECTURA, no solo la escritura.** El registro que nadie
     consulta es un pasivo, no un activo, y es el modo de falla dominante de los
     sistemas de gestion de conocimiento. Por eso existe `QueryLog`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np

from ..stats import risk_ratio_2x2
from .eventlog import TOUCH_COLUMNS, build_event_log, touches_excluidas, touches_to_decide
from .resolve import AliasStore
from .schema import CAPTURE_FAILURES, es_zombi
from .store import DecideStore

MIN_DECISIONS = 50
MIN_MEETINGS = 15
# Puntos de linea base para congelar los limites del XmR. Bajo 8 los limites
# son ruido con apariencia de control estadistico.
XMR_BASELINE = 12


def volume_gate(store: DecideStore) -> dict:
    """La compuerta. Se consulta antes de publicar cualquier numero.

    Cuenta el **corpus de control**, no todo lo que hay en disco. La diferencia
    no es cosmetica: `decide add` sin `--meeting` es una ruta legitima —la
    decision de pasillo— pero por ahi no hay roster, no hay consentimiento, y el
    techo de 7 ni se evalua. Medido: doce llamadas con `meeting_id=""` y un
    dueno que no esta en ningun roster se escriben las doce, y la compuerta las
    contaba las doce. La regla 5 se podia abrir entera con decisiones que nadie
    valido.

    Lo mismo del otro lado: quince cambios de turno en tres semanas satisfacian
    el minimo de reuniones sin que se hubiera decidido nada.

    **Migracion:** en un registro que ya tiene decisiones de pasillo, este numero
    BAJA. Es correcto, y por eso va con `nota` al lado en vez de en silencio.
    """
    c = store.corpus()
    n_d, n_m = len(c.decisions), len(c.meetings)
    ok = n_d >= MIN_DECISIONS and n_m >= MIN_MEETINGS
    return {
        "decisiones": n_d,
        "reuniones": n_m,
        "decisiones_en_disco": c.total_decisions,
        "reuniones_en_disco": c.total_meetings,
        "fuera_del_corpus": {
            "reuniones": c.meetings_fuera,
            "decisiones": c.decisions_fuera,
        },
        "nota": c.nota(),
        "minimo_decisiones": MIN_DECISIONS,
        "minimo_reuniones": MIN_MEETINGS,
        "ok": ok,
        "veredicto": (
            "hay volumen para publicar metricas"
            if ok
            else (
                f"volumen insuficiente ({n_d}/{MIN_DECISIONS} decisiones, "
                f"{n_m}/{MIN_MEETINGS} reuniones). Hasta llegar ahi, una tabla ordenada "
                "por dueno y fecha es estrictamente mejor que cualquier metrica de aca."
            )
        ),
    }


# --------------------------------------------------------- captura (hueco H6)


def capture_state(store: DecideStore, meeting_id: str) -> dict:
    """Estado de captura de una sesion, **derivado de los hechos**.

    El hueco que cierra: una reunion sin capturas se veia igual que una sana.
    Cero decisiones registradas puede significar cinco cosas —no hubo nada que
    decidir, nadie dijo la frase, Whisper fallo, el audio era inutilizable,
    nadie reviso la cola— y las cinco producian el mismo output: nada. La falla
    silenciosa es la peor propiedad posible en un sistema del que despues se
    leen conclusiones.

    Se DERIVA y no se escribe, por dos razones que aparecieron al intentar
    escribirlo: el flujo canonico sin audio (meeting -> draft -> review) no
    tiene donde poner CAPTURADA, porque el unico que lo sabia era `transcribe`,
    que ahi no corre; y cualquier default reinterpreta como fallida cada sesion
    ya persistida.

    `CAPTURADA` y `COLA_NO_REVISADA` **no son excluyentes**: "hubo decisiones
    registradas" y "quedo residuo sin revisar" son dos hechos, no dos estados —
    y los borradores dejan residuo por construccion, asi que la precedencia
    inversa reportaba como fallida a toda sesion sana. Por eso `cola_pendiente`
    va aparte y siempre.
    """
    from .draft import DraftStore, review_queue
    from .transcript import TranscriptStore

    m = store.get_meeting(meeting_id)
    ts = TranscriptStore(store.root, meeting_id)
    hubo_habla = ts.exists() or ts.lapida.exists()

    drafts = DraftStore(store.root, meeting_id).load()
    pendientes = review_queue(drafts)
    promovidas = sum(
        1
        for grupo in (store.decisions(), store.commitments(),
                      store.assumptions(), store.questions())
        for e in grupo
        if getattr(e, "meeting_id", "") == meeting_id
    )

    base = {
        "meeting": meeting_id,
        "clase": m.clase,
        "promovidas": promovidas,
        "borradores": len(drafts),
        "cola_pendiente": len(pendientes),
        "hubo_habla": hubo_habla,
    }

    # La falla declarada gana: es informacion que el sistema NO puede observar.
    if m.falla_captura:
        return {**base, "estado": m.falla_captura, "ok": False,
                "motivo": f"declarada por quien corrio el pipeline: {m.falla_captura}"}

    if promovidas:
        return {**base, "estado": "CAPTURADA", "ok": True,
                "motivo": f"{promovidas} entidad(es) promovida(s) desde esta sesion"}

    if pendientes:
        return {**base, "estado": "COLA_NO_REVISADA", "ok": False,
                "motivo": f"{len(pendientes)} borrador(es) esperando revision. "
                          "El sistema capturo; nadie confirmo."}

    if hubo_habla:
        return {**base, "estado": "SIN_RITUAL", "ok": False,
                "motivo": "hubo canal HABLADA y no salio ni un borrador: nadie dijo la "
                          "frase-marcador, o el lexico no la reconocio."}

    # El caso que da nombre al hueco. El sistema NO puede distinguir "no hubo
    # nada que decidir" de "nadie registro nada", y elegir uno de los dos seria
    # exactamente la mentira que este estado existe para impedir.
    return {
        **base,
        "estado": "SIN_REGISTRO",
        "ok": False,
        "motivo": (
            "sin habla y sin promociones. El sistema NO puede distinguir 'no hubo nada "
            "que decidir' de 'nadie registro nada' — son indistinguibles desde afuera y "
            "solo las separa alguien que estuvo. Se cierra declarando la falla "
            f"({', '.join(CAPTURE_FAILURES)}) o registrando lo que se decidio."
        ),
    }


def capture_summary(store: DecideStore) -> dict:
    """La linea que no existia en ninguna hoja: **cuantas sesiones no capturaron
    y por que**.

    Un tablero construido sobre las que si capturaron es una muestra sesgada, y
    es exactamente la que se estaba publicando.
    """
    estados = [capture_state(store, m.id) for m in store.meetings()]
    if not estados:
        return {"sesiones": 0, "linea": "sin sesiones registradas"}

    por_estado: dict[str, list[str]] = {}
    for e in estados:
        por_estado.setdefault(e["estado"], []).append(e["meeting"])
    fallidas = [e for e in estados if not e["ok"]]
    cola = sum(e["cola_pendiente"] for e in estados)

    detalle = ", ".join(
        f"{len(v)} {k}" for k, v in sorted(por_estado.items()) if k != "CAPTURADA"
    )
    return {
        "sesiones": len(estados),
        "capturadas": len(estados) - len(fallidas),
        "por_estado": por_estado,
        "cola_pendiente_total": cola,
        "linea": (
            f"{len(fallidas)} de {len(estados)} sesiones sin captura, motivos: {detalle}"
            if fallidas
            else f"las {len(estados)} sesiones dejaron registro"
        ) + (f". {cola} borrador(es) sin revisar." if cola else ""),
    }


# ------------------------------------------------------- lectura (hueco H2)


@dataclass
class QueryLog:
    """Bitacora de consultas. Quince lineas que cierran el hueco mas grande.

    Los cuatro disenos del estudio se juzgaban por cuanto capturaban. Ninguno
    media el consumo — y un registro que nadie consulta es una libreta personal
    cara.
    """

    root: Path

    def __post_init__(self):
        self.path = Path(self.root) / "queries.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, op: str, actor: str, symbol: str = "", hit: bool = True, in_room: bool = False):
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now().astimezone().isoformat(),
                "op": op, "actor": actor, "symbol": symbol, "hit": hit, "in_room": in_room,
            }, ensure_ascii=False) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_metrics(store: DecideStore) -> dict:
    q = QueryLog(store.root).entries()
    if not q:
        return {
            "consultas": 0,
            "veredicto": (
                "nadie consulto el registro. Es el modo de falla dominante de los "
                "sistemas de gestion de conocimiento y no se ve en ninguna metrica de "
                "captura: el registro se llena y no sirve para nada."
            ),
        }
    lectores = {e["actor"] for e in q}
    fallidas = sum(1 for e in q if not e["hit"])
    fuera = sum(1 for e in q if not e.get("in_room"))
    return {
        "consultas": len(q),
        "lectores_unicos": len(lectores),
        "consultas_fuera_de_sala_pct": round(fuera / len(q) * 100, 1),
        "tasa_consulta_fallida_pct": round(fallidas / len(q) * 100, 1),
        "por_operacion": {op: sum(1 for e in q if e["op"] == op) for op in {e["op"] for e in q}},
        "veredicto": (
            "el unico que consulta es quien escribe: es una libreta personal cara"
            if len(lectores) <= 1
            else "el registro se consulta"
        ),
    }


# --------------------------------------------------------------- friccion


def reopening_split(store: DecideStore) -> dict:
    """Reapertura por ignorancia contra reapertura legitima.

    Separa desperdicio puro de aprendizaje. Una decision que se reabre porque
    llego un dato nuevo es sana; una que se reabre porque nadie sabia que ya
    estaba decidida —y nadie consulto el registro antes— es la friccion que el
    sistema existe para eliminar. Ninguna herramienta actual distingue las dos.
    """
    reaperturas = [q for q in store.questions() if q.reopen_of]
    if not reaperturas:
        return {"reaperturas": 0, "veredicto": "sin reaperturas registradas"}

    consultas = QueryLog(store.root).entries()
    consultado: set[str] = {
        e["symbol"] for e in consultas if e["op"] in ("why", "refs") and e["symbol"]
    }

    por_ignorancia = []
    for q in reaperturas:
        cita_id = q.reopen_of in (q.question + " " + q.new_evidence)
        if not cita_id and q.reopen_of not in consultado:
            por_ignorancia.append(q.id)

    return {
        "reaperturas": len(reaperturas),
        "por_ignorancia": len(por_ignorancia),
        "ids_por_ignorancia": por_ignorancia,
        "pct_por_ignorancia": round(len(por_ignorancia) / len(reaperturas) * 100, 1),
        "criterio": (
            "reapertura sin citar el ID y sin que nadie haya consultado why()/refs() "
            "sobre esa decision antes"
        ),
    }


def circular_minutes(store: DecideStore) -> dict:
    """Minutos circulares: el unico numero en pesos.

    Suma, sobre las reuniones que no movieron ningun estado, el tiempo de habla
    por la cantidad de asistentes. El tiempo se **mide** desde los offsets del
    transcripto, no se estima — requiere fase 3 con audio.
    """
    from .transcript import TranscriptStore

    log = build_event_log(store)
    con_avance = set(log.df["resource"]) if len(log) else set()

    total_min = 0.0
    sin_datos, evaluadas = [], []
    for m in store.meetings():
        if m.id in con_avance:
            continue
        ts = TranscriptStore(store.root, m.id)
        utts = ts.load()
        tiempos = [u.t_end for u in utts if u.t_end is not None]
        inicio = [u.t_start for u in utts if u.t_start is not None]
        if not tiempos or not inicio:
            sin_datos.append(m.id)
            continue
        minutos = (max(tiempos) - min(inicio)) / 60
        total_min += minutos * len(m.roster)
        evaluadas.append({"meeting": m.id, "minutos_persona": round(minutos * len(m.roster), 1)})

    return {
        "reuniones_sin_avance": len(evaluadas) + len(sin_datos),
        "minutos_persona_circulares": round(total_min, 1),
        "detalle": evaluadas,
        "sin_timestamps": sin_datos,
        "nota": (
            f"{len(sin_datos)} reunion(es) sin timestamps: el tiempo de habla se mide "
            "desde los offsets de Whisper, no se estima. Sin audio no entran al numero."
            if sin_datos else ""
        ),
    }


def orphans_and_zombies(store: DecideStore) -> dict:
    """Meta: cero. Un zombi es gente ejecutando algo que ya se revirtio — un bug
    real, silencioso, y hoy estructuralmente invisible."""
    decisions = {d.id: d for d in store.decisions()}
    huerfanos, zombis = [], []
    for c in store.commitments():
        if not c.decision_id or not c.owner:
            huerfanos.append(c.id)
        elif es_zombi(c, decisions.get(c.decision_id)):
            zombis.append(c.id)
    return {
        "huerfanos": huerfanos,
        "zombis": zombis,
        "meta": 0,
        "ok": not huerfanos and not zombis,
    }


def decider_executor_presence(store: DecideStore) -> dict:
    """¿Se cumple menos un compromiso cuyo dueno no estaba cuando se decidio?

    Usa el mismo 2x2 que `dataquality.link_defects_to_rework`. Si el riesgo
    relativo es alto, la contramedida no es software: es no cerrar un compromiso
    sin que su dueno este en la sala.
    """
    cs = [c for c in store.commitments() if c.owner_presente_al_decidir is not None]
    if len(cs) < 4:
        return {"evaluables": len(cs), "veredicto": "sin datos suficientes"}

    def incumplido(c) -> bool:
        return c.status in ("VENCIDO", "ZOMBI")

    a = sum(1 for c in cs if not c.owner_presente_al_decidir and incumplido(c))
    b = sum(1 for c in cs if not c.owner_presente_al_decidir and not incumplido(c))
    cc = sum(1 for c in cs if c.owner_presente_al_decidir and incumplido(c))
    d = sum(1 for c in cs if c.owner_presente_al_decidir and not incumplido(c))
    out = risk_ratio_2x2(a, b, cc, d)
    out["lectura"] = (
        f"un compromiso cuyo dueno no estaba se incumple {out['risk_ratio']}x mas"
        if isinstance(out["risk_ratio"], float) and np.isfinite(out["risk_ratio"])
        else "sin variacion suficiente para estimar"
    )
    return out


# ------------------------------------------------- calidad del indice


def index_quality(store: DecideStore) -> dict:
    """Anti-autoengano.

    La tasa de resolucion automatica tiene que **subir** sesion a sesion; si no
    sube, la tabla de alias no esta aprendiendo. Y se publica siempre junto a la
    tasa de correccion, para que "menos cola" no se logre confirmando mas rapido
    y peor.
    """
    astore = AliasStore(store.root)
    ms = astore.mentions()
    aliases = astore.load()
    if not ms:
        return {"menciones": 0, "veredicto": "sin menciones registradas"}

    vigentes = [m for m in ms if m.get("estado") != "REVERTIDA"]
    auto = sum(1 for m in vigentes if m.get("capa_resolutora") in ("L0", "L1"))
    revertidas = sum(1 for m in ms if m.get("estado") == "REVERTIDA")
    retirados = sum(1 for a in aliases if a.estado == "RETIRADO")
    disputa = sum(1 for a in aliases if a.estado == "EN_DISPUTA")

    return {
        "menciones": len(vigentes),
        "resolucion_automatica_pct": round(auto / len(vigentes) * 100, 1) if vigentes else 0.0,
        "tasa_correccion_pct": round(revertidas / len(ms) * 100, 1),
        "alias_vigentes": sum(1 for a in aliases if a.estado == "VIGENTE"),
        "alias_en_disputa": disputa,
        "alias_retirados": retirados,
        "veredicto": (
            "el criterio de confirmacion en la cola es demasiado laxo"
            if retirados and retirados / max(len(aliases), 1) > 0.15
            else "indice sano"
        ),
    }


# -------------------------------------------------------------- XmR


BASELINE_FILE = "xmr_baseline.json"


def freeze_baseline(store: DecideStore, today: date, baseline: int = XMR_BASELINE,
                    columna: str = "toques_en_serie") -> dict:
    """Congela la linea base del XmR **en disco**. Se corre una sola vez.

    Sin esto, "congelado" era una palabra del docstring y no un hecho:
    `touches_xmr` recalculaba `serie[:baseline]` desde el store en cada llamada,
    ordenando por fecha de decision. Una sola decision registrada hoy pero
    **fechada antes** de la ventana entra a la linea base y corre los limites.
    Medido: center 2,83 -> 2,58 y sigma 1,69 -> 1,85 con un solo registro.

    Eso es exactamente el modo de falla que la regla 6 existe para impedir. Un
    CD que se degrada de a poco ensancha sus propios limites y no alarma nunca:
    la degradacion se vuelve la nueva normalidad, y el grafico sigue diciendo
    "en control" mientras el proceso empeora.

    Se guardan los **valores** de los puntos, no los limites derivados, para que
    `compute_limits` los reproduzca identicos; y los `case_id`, que es lo que
    permite despues detectar que los datos se movieron debajo.
    """
    if columna not in TOUCH_COLUMNS:
        raise ValueError(f"columna desconocida: {columna!r}. Validas: {TOUCH_COLUMNS}")
    t = touches_to_decide(store)
    if len(t) < baseline:
        raise ValueError(
            f"{len(t)} decisiones cerradas: hacen falta {baseline} para congelar una "
            "linea base. Congelarla antes fija ruido con apariencia de control."
        )
    orden = t.sort_values("decidida")
    puntos = orden.head(baseline)
    datos = {
        "congelada_el": today.isoformat(),
        "n_baseline": baseline,
        "case_ids": list(puntos["case_id"]),
        # Con QUE definicion se congelo. Cambiar de columna despues corrompe el
        # grafico exactamente igual que recalcular los limites: medido, center
        # 3,33 -> 2,42 y ucl 7,20 -> 3,87 sobre la MISMA data.
        "columna": columna,
        "toques": [float(x) for x in puntos[columna]],
        "hasta": str(puntos["decidida"].max()),
        "nota": (
            "NO editar a mano ni regenerar para 'actualizar' los limites. Si el "
            "proceso mejoro de verdad, se documenta el cambio y se congela una "
            "linea base NUEVA, con fecha, conservando esta al lado."
        ),
    }
    (store.root / BASELINE_FILE).write_text(
        json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return datos


def touches_xmr(store: DecideStore, baseline: int = XMR_BASELINE,
                columna: str | None = None) -> dict:
    """Grafico de control de toques-para-decidir, con limites CONGELADOS.

    Solo desde la reunion ~15: antes es ruido. Los limites salen de la linea
    base persistida por `freeze_baseline` y no se recalculan nunca.

    Usa `toques_en_serie` por default, que es la columna de CORPUS. El XmR es la
    metrica de CONTROL, y las de control filtran — las descriptivas no. Con la
    columna descriptiva, una pregunta abierta desde una ventana de WhatsApp
    contra una decision de sala le suma un toque: medido, 3 -> 4. La ventana no
    es una serie de decision y no puede aportar puntos a un grafico de control.

    Una linea base ya congelada CONSERVA su columna: cambiarla bajo limites
    congelados corrompe el grafico igual que recalcular los limites, que es la
    razon por la que `freeze_baseline` la guarda.

    Si no hay linea base congelada, los limites se calculan igual pero salen
    marcados `congelada=False` y con el veredicto diciendolo: un grafico de
    control cuyos limites se mueven solos no es un grafico de control, y
    presentarlo como tal es peor que no tenerlo.
    """
    gate = volume_gate(store)
    t = touches_to_decide(store)
    if len(t) < baseline + 4:
        return {
            "puntos": len(t),
            "necesarios": baseline + 4,
            "ok": False,
            "congelada": False,
            "columna": columna or "toques_en_serie",
            "veredicto": (
                f"{len(t)} decisiones cerradas: hacen falta al menos {baseline + 4} para "
                "una linea base creible. Antes de eso el grafico dibuja ruido con "
                "apariencia de control estadistico."
            ),
            "volumen": gate,
        }

    from ..spc import degradation_alarm

    orden = t.sort_values("decidida")
    path = store.root / BASELINE_FILE
    avisos: list[str] = []

    if path.exists():
        fija = json.loads(path.read_text(encoding="utf-8"))
        col = fija.get("columna", "toques")  # las bases viejas conservan la suya
        if columna is not None and columna != col:
            raise ValueError(
                f"la linea base se congelo con '{col}' y se esta pidiendo '{columna}'. "
                "Cambiar la definicion de un punto bajo limites congelados corrompe el "
                "grafico igual que recalcular los limites. Si de verdad hay que cambiarla, "
                "se congela una linea base NUEVA y se conserva esta al lado."
            )
        congelados = list(fija["case_ids"])
        base = [float(x) for x in fija["toques"]]
        # Todo lo que NO es de la linea base es monitoreo — incluida una decision
        # fechada hacia atras. Que entre al monitoreo y no a la base es el punto:
        # la base es un periodo declarado, no los primeros N por fecha.
        en_base = set(congelados)
        mon = [float(x) for x in orden[~orden["case_id"].isin(en_base)][col]]

        actuales = set(orden["case_id"])
        faltan = [c for c in congelados if c not in actuales]
        if faltan:
            avisos.append(
                f"{len(faltan)} caso(s) de la linea base ya no estan en el registro "
                f"({', '.join(faltan[:5])}): los limites siguen siendo los congelados, "
                "pero la base ya no es reproducible desde los datos de hoy."
            )
        nuevos_viejos = [
            c for c in orden.head(baseline)["case_id"] if c not in en_base
        ]
        if nuevos_viejos:
            avisos.append(
                f"{len(nuevos_viejos)} decision(es) fechada(s) dentro de la ventana de "
                f"la linea base se registraron despues de congelarla "
                f"({', '.join(nuevos_viejos[:5])}). NO entraron a los limites —"
                " entraron al monitoreo, que es lo correcto— pero conviene saber que "
                "el pasado del registro cambio."
            )
        congelada, cuando = True, fija["congelada_el"]
    else:
        col = columna or "toques_en_serie"
        serie = [float(x) for x in orden[col]]
        base, mon = serie[:baseline], serie[baseline:]
        congelada, cuando = False, None
        avisos.append(
            "linea base NO congelada: estos limites se recalculan en cada corrida y se "
            "mueven solos cuando entra una decision fechada hacia atras. Correr "
            "`freeze_baseline(store, today)` antes de presentarlos como control."
        )

    alarm = degradation_alarm(base, mon, direction="lower_is_better", lcl_floor=1.0)
    veredicto = alarm["verdict"]
    if not congelada:
        veredicto = f"{veredicto} (limites PROVISORIOS: linea base sin congelar)"
    return {
        "puntos": len(orden),
        "baseline": baseline,
        "ok": True,
        "congelada": congelada,
        "congelada_el": cuando,
        "columna": col,
        "excluidas": touches_excluidas(store),
        "limites": alarm["limits"],
        "veredicto": veredicto,
        "violaciones_criticas": alarm["critical_violations"],
        "corrimiento_sigmas": alarm["shift_sigmas"],
        "avisos": avisos,
        "volumen": gate,
    }


# ------------------------------------------------------------- la hoja


def report(store: DecideStore) -> str:
    """La hoja imprimible. No es un tablero: es una hoja que se lleva a la
    reunion de operaciones, misma doctrina que el XmR del A3."""
    gate = volume_gate(store)
    reab = reopening_split(store)
    oz = orphans_and_zombies(store)
    lect = read_metrics(store)
    idx = index_quality(store)
    circ = circular_minutes(store)
    t = touches_to_decide(store)

    L = ["# Metricas del registro de decisiones", ""]
    if not gate["ok"]:
        L += [
            "> **Volumen insuficiente.** " + gate["veredicto"],
            ">",
            "> Los numeros de abajo se calculan igual, pero no se publican ni se llevan a",
            "> una reunion todavia. Prometer el numero bonito el dia 1 es la forma mas",
            "> rapida de quemar la credibilidad del sistema.",
            "",
        ]

    cap = capture_summary(store)
    L += [
        f"**Volumen:** {gate['decisiones']} decisiones, {gate['reuniones']} reuniones.",
        f"**Corpus:** {gate['nota']}",
        "",
        "## Captura — de que muestra salen los numeros de abajo",
        "",
        # La linea que no existia en ninguna propuesta. Un tablero construido
        # sobre las sesiones que SI capturaron es una muestra sesgada, y es la
        # que se estaba publicando.
        f"**{cap['linea']}**",
        "",
    ]
    fallidas = sorted(
        (e, ids) for e, ids in cap.get("por_estado", {}).items() if e != "CAPTURADA"
    )
    if fallidas:
        L += ["| estado | sesiones |", "|---|---|"]
        L += [f"| {e} | {', '.join(ids)} |" for e, ids in fallidas]
        L.append("")

    L += [
        "## Supervivencia",
        "",
        f"- Compromisos huerfanos: {len(oz['huerfanos'])} (meta 0)",
        f"- Compromisos zombi: {len(oz['zombis'])} (meta 0)",
        "",
        "## Lectura — el registro que nadie consulta es un pasivo",
        "",
        f"- Consultas: {lect.get('consultas', 0)}"
        + (f", lectores unicos: {lect['lectores_unicos']}" if lect.get("consultas") else ""),
    ]
    if lect.get("consultas"):
        L += [
            f"- Consultas fuera de la sala: {lect['consultas_fuera_de_sala_pct']}%",
            f"- Tasa de consulta fallida: {lect['tasa_consulta_fallida_pct']}%",
        ]
    L += [f"- {lect['veredicto']}", "", "## Friccion", ""]

    if not t.empty:
        L.append(f"- Toques-para-decidir: mediana {t['toques'].median():.0f}, "
                 f"maximo {t['toques'].max()}")
    L.append(f"- Reaperturas: {reab['reaperturas']}"
             + (f", por ignorancia {reab['pct_por_ignorancia']}%" if reab["reaperturas"] else ""))
    L.append(f"- Minutos-persona circulares: {circ['minutos_persona_circulares']}")
    if circ["nota"]:
        L.append(f"  - {circ['nota']}")

    L += ["", "## Calidad del indice", ""]
    if idx.get("menciones"):
        L += [
            f"- Resolucion automatica (L0+L1): {idx['resolucion_automatica_pct']}% "
            "— tiene que subir sesion a sesion",
            f"- Tasa de correccion: {idx['tasa_correccion_pct']}% "
            "— se publica al lado para que 'menos cola' no se logre confirmando peor",
            f"- Alias: {idx['alias_vigentes']} vigentes, {idx['alias_en_disputa']} en disputa, "
            f"{idx['alias_retirados']} retirados",
        ]
    else:
        L.append("- sin menciones registradas todavia")
    L += ["", "---", "", "_Se imprime y se lleva a la reunion. No es un tablero._"]
    return "\n".join(L)
