"""Fase 0: el piloto de proceso. Dos semanas, y en la sala no hay software.

Es la fase mas importante del plan y la que se va a querer saltear. Si el
marcador verbal no aguanta dos semanas con una planilla compartida, no va a
aguantar con 4.500 lineas de Python — y descubrirlo cuesta dos semanas en vez
de tres meses.

    Criterio de continuacion: >=70% de los puntos de agenda de decision
    terminan con una fila escrita. Por debajo de eso el problema no es el
    software, y el software no lo va a arreglar.

**Por que hay codigo en una fase que el diseno declara sin codigo.** El piloto
no lleva software: el facilitador dice la frase, alguien llena cinco columnas en
una planilla, y la agenda se arma leyendo esa planilla. Lo que hay aca es el
arnes para *medir* el piloto, que es exactamente lo que pide el hueco H1 del
critico —"exportar el calendario, calcular horas-persona por serie, elegir una
serie de control, y declarar el criterio de muerte antes de empezar"— y que el
propio critico estima en un dia-persona.

La distincion importa: si el cliente toca software en estas dos semanas, la
prueba deja de medir lo unico que tiene que medir, que es si la disciplina del
marcador verbal se sostiene sin herramienta.

Y el hueco H1 en una linea: sin linea base ni contrafactual, el proyecto es
infalsable. Cualquier resultado se puede narrar como exito. Es una violacion
directa de la doctrina del propio kit — lo que no esta cuantificado no entra al
analisis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..baseline import BaselineSpec, diff_in_diff, mde, sd_from_log

# Los cinco campos que el facilitador dice en voz alta y alguien anota.
CAMPOS = ("que", "dueno", "fecha", "porque", "supuesto")
TASA_MINIMA = 0.70
# Caida minima de horas-persona contra el control para que el proyecto siga.
UMBRAL_MUERTE = 0.15
SEMANAS_PILOTO = 2
SEMANAS_HASTA_VEREDICTO = 10


# El cuerpo de un invite viene lleno de boilerplate de videollamada: el bloque
# de "unirse a la reunion" de Teams son cientos de caracteres. Medir agenda por
# largo bruto haria que TODA reunion con link parezca tener agenda escrita, que
# es exactamente al reves de lo que se quiere detectar.
_BOILERPLATE = (
    r"https?://\S+",
    r"_{5,}",
    r"microsoft teams|zoom|google meet|webex",
    r"unirse a la reunion|join the meeting|join microsoft teams",
    r"id de (la )?reunion|meeting id|codigo de acceso|passcode",
    r"llamar al|dial[- ]?in|marcar\s*\+?\d",
    r"obtener ayuda|learn more|conocer mas|opciones de reunion|meeting options",
)
# Texto util minimo para considerar que alguien escribio una agenda. Dos lineas
# cortas: no es un umbral fino, es la diferencia entre "algo" y "nada".
_MIN_AGENDA_CHARS = 40


def _tiene_agenda(body: str) -> bool:
    """¿El invite trae agenda escrita, descontando el boilerplate?"""
    import re

    t = str(body or "").lower()
    for pat in _BOILERPLATE:
        t = re.sub(pat, " ", t)
    return len(" ".join(t.split())) >= _MIN_AGENDA_CHARS


# ------------------------------------------------------- linea base (H1)


def load_calendar(path: str | Path) -> pd.DataFrame:
    """Carga un export de calendario. Tolerante con los nombres de columna.

    Outlook exporta `Subject,Start Date,Start Time,...`; Graph API devuelve
    `subject,start,end,attendees`. Se normaliza a: serie, inicio, fin,
    asistentes, agenda_escrita.
    """
    df = pd.read_csv(path)
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_sub = pick("subject", "asunto", "titulo", "serie")
    c_ini = pick("start", "inicio", "start_datetime")
    c_fin = pick("end", "fin", "end_datetime")
    c_asis = pick("attendees", "asistentes", "required_attendees")
    c_body = pick("body", "cuerpo", "agenda", "description")

    faltan = [n for n, c in [("subject", c_sub), ("start", c_ini), ("end", c_fin),
                             ("attendees", c_asis)] if c is None]
    if faltan:
        raise ValueError(
            f"al export de calendario le faltan columnas: {faltan}. "
            "Minimo: subject, start, end, attendees."
        )

    out = pd.DataFrame({
        "serie": df[c_sub].astype(str).str.strip(),
        "inicio": pd.to_datetime(df[c_ini]),
        "fin": pd.to_datetime(df[c_fin]),
    })
    out["asistentes"] = pd.to_numeric(
        df[c_asis].astype(str).str.count(";").add(1) if df[c_asis].dtype == object else df[c_asis],
        errors="coerce",
    ).fillna(1)
    out["agenda_escrita"] = (
        df[c_body].astype(str).map(_tiene_agenda) if c_body else False
    )
    out["horas"] = (out["fin"] - out["inicio"]).dt.total_seconds() / 3600
    out["horas_persona"] = out["horas"] * out["asistentes"]
    out["semana"] = out["inicio"].dt.to_period("W").astype(str)
    return out


def baseline_from_calendar(cal: pd.DataFrame) -> dict:
    """Los cuatro numeros del hueco H1. Todos salen del mismo export.

    Es la variable dependiente del proyecto. Sin ella cualquier resultado se
    puede narrar como exito, y el proyecto entero es infalsable.
    """
    if cal.empty:
        return {"error": "calendario vacio"}

    semanas = cal["semana"].nunique()
    por_serie = (
        cal.groupby("serie")
        .agg(reuniones=("horas", "size"), horas_persona=("horas_persona", "sum"))
        .assign(horas_persona_semana=lambda d: (d["horas_persona"] / semanas).round(1))
        .sort_values("horas_persona", ascending=False)
    )
    recurrentes = por_serie[por_serie["reuniones"] >= semanas].index.tolist()

    return {
        "semanas_observadas": int(semanas),
        "horas_persona_semana": round(cal["horas_persona"].sum() / semanas, 1),
        "reuniones_por_semana": round(len(cal) / semanas, 1),
        "series_totales": int(cal["serie"].nunique()),
        "series_recurrentes": len(recurrentes),
        "pct_sin_agenda_escrita": round((~cal["agenda_escrita"]).mean() * 100, 1),
        "top_series": por_serie.head(8).reset_index().to_dict("records"),
        "candidatas_a_control": recurrentes[1:4],
        "nota_control": (
            "elegir UNA serie recurrente que NO adopte el sistema durante 8 semanas. "
            "Sin grupo de control el efecto es indistinguible del efecto Hawthorne, que "
            "en este tipo de intervencion es grande y real."
        ),
    }


def pilot_spec(metric_owner: str, control_series: str, weeks: int = SEMANAS_HASTA_VEREDICTO) -> BaselineSpec:
    """El spec de medicion del piloto. `BaselineSpec` no se adapta: se adopta."""
    return BaselineSpec(
        metric_name="Horas-persona de reunion por semana en el scope",
        metric_definition="sum(duracion_horas x asistentes) / semanas, del export de calendario",
        data_source="export de calendario (Outlook CSV o Graph API)",
        unit_of_analysis="semana x serie",
        direction="lower_is_better",
        target_change_pct=-UMBRAL_MUERTE * 100,
        baseline_window_days=weeks * 7,
        control_group=control_series,
        known_confounders=("cierre de mes", "peak estacional", "vacaciones", "efecto Hawthorne"),
        owner_client_side=metric_owner,
    )


# ------------------------------------------------- la planilla de 5 columnas


def tally_template() -> str:
    """La unica herramienta que entra a la sala.

    Una fila por punto de agenda de decision — no por decision tomada. Esa
    diferencia es lo que hace calculable la tasa de declaracion: el denominador
    tiene que existir antes de la reunion, o el numero se vuelve autocumplido.
    """
    cab = "reunion,fecha,punto_agenda,que,dueno,fecha_compromiso,porque,supuesto,supuesto_vence"
    ejemplo = (
        'comite-01,2026-08-03,"slotting clase A",'
        '"reslotear la clase A a la zona dorada","Marcela Perez",2026-09-30,'
        '"69% de las visitas son clase A","el layout no cambia",2026-08-20'
    )
    vacio = 'comite-01,2026-08-03,"turno de noche",,,,,,'
    return "\n".join([cab, ejemplo, vacio, ""])


def tally_instructions() -> str:
    """La hoja que se imprime y se deja sobre la mesa."""
    return """# Piloto de decisiones — hoja de sala

## Lo unico que hay que hacer

Al cerrar cada punto de agenda de decision, el facilitador dice en voz alta:

> **"Queda decidido: QUE. Dueno NOMBRE. Para FECHA. Porque RAZON."**

Seis segundos. Alguien anota lo que se dijo en la planilla. Nada mas.

Los otros dos marcadores, cuando corresponda:

> **"Queda pendiente: QUE. Lo resuelve NOMBRE. Antes del FECHA."**
> **"Asumimos QUE. Lo verificamos antes del FECHA."**

## Reglas

1. **Una fila por punto de agenda de decision, escrita ANTES de la reunion.**
   Si el punto se cierra, se llenan los cuatro campos de la frase: **que, dueno,
   fecha y porque**. Si no se cierra, la fila queda vacia — y eso es el dato.
   El `supuesto` se llena SOLO si alguien declaro uno en voz alta: no todo punto
   de decision tiene un supuesto detras, y pedirlo siempre invita a inventar uno.
2. **Fechas absolutas.** "El viernes" no; "2026-08-07" si. Si nadie dijo una
   fecha, la celda queda vacia.
3. **Nadie inventa un dueno.** Si no lo nombraron, la celda queda vacia.
4. **No se usa software.** El punto de estas dos semanas es saber si la
   disciplina se sostiene sin herramienta.

## Por que importa que las celdas queden vacias

La celda vacia no es un error de la planilla: es la medicion. Al final de las
dos semanas se cuenta que fraccion de los puntos de agenda termino con una fila
completa. Si es menos del 70%, el problema no es el software y el software no lo
va a arreglar.

## Lo que NO hay que hacer

- No completar filas despues, de memoria. Una fila reconstruida el jueves no
  prueba nada sobre lo que paso el martes.
- No discutir la planilla en la reunion. Se llena y se sigue.
- No agregar columnas. Cinco campos es el punto.
"""


def score_tally(path: str | Path) -> dict:
    """Puntua la planilla contra el criterio de continuacion.

    Devuelve tambien que campo falta mas, que es el diagnostico util: si lo que
    falta siempre es `porque`, la frase se esta diciendo a medias; si es
    `dueno`, hay un problema politico y no de proceso.
    """
    df = pd.read_csv(path).fillna("")
    if "punto_agenda" not in df.columns:
        raise ValueError("la planilla no tiene la columna punto_agenda: es el denominador")

    df = df[df["punto_agenda"].astype(str).str.strip() != ""]
    if df.empty:
        return {"puntos": 0, "veredicto": "planilla vacia: no hay nada que puntuar"}

    presentes = {
        "que": df["que"].astype(str).str.strip() != "",
        "dueno": df["dueno"].astype(str).str.strip() != "",
        "fecha": df["fecha_compromiso"].astype(str).str.strip() != "",
        "porque": df["porque"].astype(str).str.strip() != "",
        "supuesto": df["supuesto"].astype(str).str.strip() != "",
    }
    completa = presentes["que"] & presentes["dueno"] & presentes["fecha"] & presentes["porque"]
    declarada = presentes["que"]

    tasa = float(declarada.mean())

    # **El diagnostico se calcula SOLO sobre los puntos que cerraron.** Un punto
    # que no cerro no dice nada sobre como se dijo la frase: dice que el punto
    # no cerro, y eso ya lo cuenta `tasa_declaracion`. Contarlo tambien aca
    # contamina el unico numero que decide que hacer despues.
    #
    # Medido ensayando el protocolo con dos semanas de datos realistas: el dueno
    # faltaba en 0% de los puntos cerrados y el reporte decia 38,5%. Con otro
    # reparto eso dispara la rama "el problema es politico" sobre un equipo que
    # nombra dueno siempre.
    base = int(declarada.sum())
    faltantes = {
        k: round((~v[declarada]).mean() * 100, 1) if base else 0.0
        for k, v in presentes.items()
        if k != "supuesto"
    }
    # Denominador cero: no hay campo que culpar, falla el ritual entero.
    # Inventar un `campo_que_mas_falta` aca seria el numero plausible y falso.
    peor = max(faltantes, key=faltantes.get) if base else None

    ok = tasa >= TASA_MINIMA
    return {
        "puntos_de_agenda": int(len(df)),
        "con_algo_escrito": int(declarada.sum()),
        "con_los_cuatro_campos": int(completa.sum()),
        "tasa_declaracion": round(tasa, 3),
        "minimo": TASA_MINIMA,
        "ok": ok,
        "campo_que_mas_falta": peor,
        "pct_faltante_por_campo": faltantes,
        # Sobre cuantas filas se calculo lo de arriba. Publicarlo es la
        # diferencia entre "falta el porque el 25% de las veces" y "falta el
        # porque en 2 de 8": con base chica el diagnostico es una anecdota.
        "base_del_diagnostico": base,
        "por_reunion": (
            df.assign(declarada=declarada)
            .groupby("reunion")["declarada"]
            .agg(["size", "sum"])
            .assign(tasa=lambda d: (d["sum"] / d["size"]).round(2))
            .reset_index()
            .to_dict("records")
        ),
        "veredicto": _veredicto_tally(ok, tasa, peor, faltantes, base),
    }


# Que significa que falte cada campo. Es el unico lugar del kit donde el
# diagnostico deja de ser tecnico: si falta el `porque` hay un problema de
# facilitacion, y si falta el `dueno` hay uno politico. Confundirlos manda al
# FDE a la conversacion equivocada.
_LECTURA_DEL_CAMPO = {
    "porque": (
        "Si falta el 'porque', la frase se esta diciendo a medias y hay que "
        "corregir al facilitador, no comprar software. "
    ),
    "dueno": (
        "Si falta el dueno, el problema es politico: un registro con dueno y fecha "
        "es un instrumento de rendicion de cuentas, y eso se manifiesta como 'no "
        "pongamos dueno todavia'. "
    ),
}


def _veredicto_tally(ok: bool, tasa: float, peor, faltantes: dict, base: int) -> str:
    """El texto que decide si el proyecto sigue.

    Estaba escrito como tres ternarios anidados dentro del `return`, y al
    agregarle la rama de base cero se comio el prefijo "NO seguir" sin que
    ningun test lo viera: el veredicto salia empezando por "Lo que mas falta
    es...". Un veredicto que no dice su veredicto es la peor version de este
    bug, porque lo lee alguien que esta decidiendo si sigue gastando.
    """
    if ok:
        return "seguir a fase 1: la disciplina se sostiene sin herramienta"

    cabeza = f"NO seguir. Tasa {tasa:.0%} bajo el minimo de {TASA_MINIMA:.0%}. "
    if peor is None:
        return (
            cabeza + "Ningun punto de agenda cerro con algo escrito: no falla un "
            "campo, falla el ritual. Empezar por si el facilitador esta diciendo la "
            "frase en voz alta. El software no arregla esto."
        )
    return (
        cabeza
        + f"Lo que mas falta es '{peor}', en {faltantes[peor]:.0f}% de los {base} "
        f"punto(s) que si cerraron. "
        + _LECTURA_DEL_CAMPO.get(peor, "")
        + "El software no arregla esto."
    )


# ---------------------------------------------------------------- encuesta

PREGUNTAS = (
    ("podian_ser_correo", "De las reuniones de esta semana, ¿cuantas podrian haber sido un correo?"),
    ("rediscutido", "¿Cuantas veces esta semana discutiste algo que ya se habia decidido antes?"),
    ("minutos_buscar", "Si tuvieras que averiguar por que se decidio algo hace dos meses, ¿cuantos minutos te tomaria?"),
)


def survey_template() -> str:
    cab = "fecha,persona,grupo," + ",".join(k for k, _ in PREGUNTAS)
    guia = "# " + " | ".join(f"{k}: {t}" for k, t in PREGUNTAS)
    return "\n".join([guia, "# grupo: treat | control", cab, ""])


def score_survey(path: str | Path) -> dict:
    """Mediana por grupo y por ola. Sesenta segundos, n~8, mensual.

    Es la unica medicion que capta la friccion percibida, que es distinta de la
    friccion medida y a veces se mueve antes.
    """
    df = pd.read_csv(path, comment="#")
    if df.empty:
        return {"respuestas": 0, "veredicto": "sin respuestas"}
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["ola"] = df["fecha"].dt.to_period("M").astype(str)

    out = {"respuestas": int(len(df)), "por_ola": {}}
    for ola, g in df.groupby("ola"):
        out["por_ola"][ola] = {
            k: {
                grupo: round(float(sub[k].median()), 1)
                for grupo, sub in g.groupby("grupo")
                if k in sub
            }
            for k, _ in PREGUNTAS
        }
    if len(out["por_ola"]) < 2:
        out["veredicto"] = "una sola ola: hace falta al menos la de inicio y una mensual"
    else:
        out["veredicto"] = "comparar treat contra control en cada ola, no contra si mismo"
    return out


# ------------------------------------------------------ criterio de muerte


@dataclass
class PilotVerdict:
    did_estimate: float
    pct_vs_baseline: float
    threshold_pct: float
    passes: bool
    significant: bool
    detail: dict
    note: str

    def to_dict(self) -> dict:
        return {**self.__dict__}


def weekly_panel(cal: pd.DataFrame, treat_series: list[str], control_series: list[str],
                 cutoff: date) -> pd.DataFrame:
    """Horas-persona por semana y serie, etiquetadas treat/control y pre/post."""
    df = cal[cal["serie"].isin([*treat_series, *control_series])].copy()
    df["group"] = np.where(df["serie"].isin(treat_series), "treat", "control")
    df["period"] = np.where(df["inicio"].dt.date < cutoff, "pre", "post")
    return (
        df.groupby(["group", "period", "semana"], as_index=False)["horas_persona"]
        .sum()
        .rename(columns={"horas_persona": "value"})
    )


def evaluate_pilot(panel: pd.DataFrame, threshold: float = UMBRAL_MUERTE) -> PilotVerdict:
    """El criterio de muerte, declarado ANTES de empezar.

    Si a la semana 10 las horas-persona del scope tratado no bajaron al menos el
    umbral **contra el control**, se apaga. Declararlo antes es lo que hace que
    el proyecto sea falsable; declararlo despues es elegir el umbral que da bien.
    """
    faltan = [
        (g, p) for g in ("treat", "control") for p in ("pre", "post")
        if panel[(panel["group"] == g) & (panel["period"] == p)].empty
    ]
    if faltan:
        return PilotVerdict(
            float("nan"), float("nan"), threshold * 100, False, False,
            {"celdas_vacias": faltan},
            "sin las cuatro celdas no hay contrafactual y el resultado no es interpretable",
        )

    did = diff_in_diff(panel, "value", "group", "period")
    base = did["means"]["treat_pre"]
    pct = did["did_estimate"] / base * 100 if base else float("nan")
    passes = pct <= -threshold * 100

    n_sem = panel[panel["group"] == "treat"]["semana"].nunique()
    sd = sd_from_log(panel[panel["group"] == "treat"]["value"])
    detectable = mde(sd, max(n_sem, 2)) / base * 100 if base else float("nan")

    return PilotVerdict(
        did_estimate=round(did["did_estimate"], 2),
        pct_vs_baseline=round(pct, 1),
        threshold_pct=round(-threshold * 100, 1),
        passes=bool(passes),
        significant=bool(did["significant"]),
        detail={
            **did,
            "semanas_por_grupo": int(n_sem),
            "mde_pct_con_estas_semanas": round(detectable, 1),
        },
        note=_nota_potencia(detectable, pct, threshold, n_sem, did),
    )


def _nota_potencia(detectable: float, pct: float, threshold: float, n_sem: int, did: dict) -> str:
    """La nota tiene que distinguir dos cosas que se confunden todo el tiempo:
    si el diseno puede detectar el UMBRAL, y si el efecto OBSERVADO supera lo
    detectable. Un diseno sin potencia para el umbral igual puede haber medido
    un efecto grande y real."""
    if not did.get("testable", True):
        return did.get("warning_varianza", "")
    if not np.isfinite(detectable):
        return "sin dispersion suficiente para estimar la potencia del diseno"

    if detectable <= threshold * 100:
        return "el diseno tiene potencia suficiente para el umbral declarado"

    base = (
        f"El efecto minimo detectable con {n_sem} semanas por grupo es {detectable:.0f}%, "
        f"por encima del umbral de {threshold*100:.0f}%: el diseno no puede probar el "
        "umbral y hay que alargar la ventana antes de comprometerlo."
    )
    if np.isfinite(pct) and abs(pct) >= detectable:
        return (
            base
            + f" Ahora bien, el efecto observado ({abs(pct):.0f}%) SI supera lo detectable, "
            "asi que la medicion sirve — lo que no sirve es prometer 15% con esta ventana."
        )
    return base


# ------------------------------------------------------------ artefactos


def scaffold(out: str | Path, site: str = "", metric_owner: str = "",
             control_series: str = "", start: date | None = None) -> dict:
    """Escribe los cuatro artefactos del piloto. Es todo lo que hace falta."""
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    start = start or date.today()

    (d / "planilla.csv").write_text(tally_template(), encoding="utf-8")
    (d / "hoja-de-sala.md").write_text(tally_instructions(), encoding="utf-8")
    (d / "encuesta.csv").write_text(survey_template(), encoding="utf-8")
    (d / "spec-medicion.md").write_text(
        pilot_spec(metric_owner or "<jefe de operaciones>",
                   control_series or "<serie de control>").to_markdown(),
        encoding="utf-8",
    )
    (d / "protocolo.md").write_text(protocol(site, start, control_series), encoding="utf-8")
    return {
        "carpeta": str(d),
        "archivos": ["planilla.csv", "hoja-de-sala.md", "encuesta.csv",
                     "spec-medicion.md", "protocolo.md"],
        "recordatorio": "en la sala solo entran planilla.csv y hoja-de-sala.md impresa",
    }


def protocol(site: str, start: date, control_series: str = "") -> str:
    fin_piloto = start + timedelta(weeks=SEMANAS_PILOTO)
    veredicto = start + timedelta(weeks=SEMANAS_HASTA_VEREDICTO)
    return f"""# Protocolo del piloto — {site or '<sitio>'}

**Inicio:** {start.isoformat()}  |  **Fin del piloto:** {fin_piloto.isoformat()}  |
**Veredicto:** {veredicto.isoformat()}

## Antes de empezar (1 dia-persona)

1. Exportar el calendario del scope de las ultimas 8 semanas y correr
   `fdekit decide pilot baseline --calendar <csv>`. Da la variable dependiente:
   horas-persona de reunion por semana. **Sin esto el proyecto es infalsable.**
2. Elegir **una serie de control** que NO adopte nada durante 8 semanas:
   {control_series or '<pendiente>'}. Sin control, el efecto es indistinguible
   del efecto Hawthorne, que en este tipo de intervencion es grande y real.
3. Pasar la encuesta de 3 preguntas (60 segundos, n~8) a los dos grupos.
4. Firmar el spec de medicion con el dueno del lado del cliente.

## Las dos semanas

- El facilitador dice la frase-marcador al cerrar cada punto de decision.
- Alguien llena los cuatro campos de la frase en `planilla.csv` (el supuesto,
  solo si alguien declaro uno).
- La agenda de cada reunion se arma **leyendo la planilla**: compromisos con
  fecha pasada y filas incompletas de la semana anterior.
- **No se instala nada.** El punto de estas dos semanas es saber si la
  disciplina se sostiene sin herramienta.

## Al cierre de las dos semanas

Correr `fdekit decide pilot score --tally planilla.csv`.

- **Tasa de declaracion >= {TASA_MINIMA:.0%}** -> seguir a fase 1.
- **Por debajo** -> no seguir. El problema no es el software.

Esta decision se toma con el numero, no con la sensacion de la sala. La
sensacion de la sala a las dos semanas siempre es buena: es el efecto Hawthorne.

## Semana 10 — criterio de muerte, declarado ahora

`fdekit decide pilot verdict --calendar <csv> --cutoff {fin_piloto.isoformat()}`

> Si las horas-persona del scope tratado no bajaron **>= {UMBRAL_MUERTE:.0%} contra
> el control**, el proyecto se apaga.

Declararlo ahora es lo que lo hace falsable. Declararlo despues es elegir el
umbral que da bien.

## Lo que NO hay que hacer en estas dos semanas

- Instalar `fdekit.decide`. Mide otra cosa.
- Cambiar la planilla porque "le falta una columna". Cinco campos es el punto.
- Completar filas de memoria al final de la semana.
- Contarle al grupo de control que existe un piloto.
"""
