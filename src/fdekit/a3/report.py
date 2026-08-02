"""Generador de A3.

Un A3 no es un formato bonito: es una restriccion. Si el problema, el analisis,
la contramedida y el plan no caben en una hoja, todavia no entendiste el
problema. Aca se genera en Markdown para versionarlo junto al codigo — el A3 y
el commit que lo implementa viven en el mismo repo, y esa trazabilidad es lo que
hace que la revision de los 90 dias sea corta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class A3:
    title: str
    owner: str
    site: str = ""
    date_str: str = field(default_factory=lambda: date.today().isoformat())

    background: str = ""
    current_condition: list[str] = field(default_factory=list)
    target_condition: list[str] = field(default_factory=list)
    root_cause: list[str] = field(default_factory=list)
    countermeasures: list[dict] = field(default_factory=list)  # {accion, dueno, fecha, efecto_esperado}
    plan: list[dict] = field(default_factory=list)  # {paso, dueno, fecha}
    followup: list[str] = field(default_factory=list)
    charts: list[str] = field(default_factory=list)  # rutas relativas a imagenes

    def add_countermeasure(self, accion: str, dueno: str, fecha: str, efecto: str):
        self.countermeasures.append(
            {"accion": accion, "dueno": dueno, "fecha": fecha, "efecto_esperado": efecto}
        )
        return self

    def validate(self) -> list[str]:
        issues = []
        if not self.current_condition:
            issues.append("condicion actual vacia: sin numeros no hay A3")
        if not any(any(ch.isdigit() for ch in c) for c in self.current_condition):
            issues.append("la condicion actual no contiene ningun numero")
        if not self.target_condition:
            issues.append("condicion objetivo vacia: ¿cuanto, para cuando?")
        if not self.root_cause:
            issues.append("sin causa raiz: las contramedidas van a atacar sintomas")
        if len(self.countermeasures) > 5:
            issues.append("mas de 5 contramedidas: no es un A3, es un plan estrategico")
        for c in self.countermeasures:
            if not c.get("dueno") or not c.get("fecha"):
                issues.append(f"contramedida sin dueno o sin fecha: {c.get('accion','?')}")
        return issues

    def to_markdown(self) -> str:
        def bullets(items):
            return "\n".join(f"- {i}" for i in items) if items else "_(pendiente)_"

        cm = "\n".join(
            f"| {c['accion']} | {c['dueno']} | {c['fecha']} | {c['efecto_esperado']} |"
            for c in self.countermeasures
        ) or "| _(pendiente)_ | | | |"

        pl = "\n".join(f"| {p['paso']} | {p.get('dueno','')} | {p.get('fecha','')} |" for p in self.plan) or "| _(pendiente)_ | | |"

        imgs = "\n".join(f"![{c}]({c})" for c in self.charts)

        return f"""# A3 — {self.title}

**Dueno:** {self.owner}  |  **Sitio:** {self.site}  |  **Fecha:** {self.date_str}

## 1. Antecedentes
{self.background or "_(pendiente)_"}

## 2. Condicion actual
{bullets(self.current_condition)}

{imgs}

## 3. Condicion objetivo
{bullets(self.target_condition)}

## 4. Analisis de causa raiz
{bullets(self.root_cause)}

## 5. Contramedidas
| accion | dueno | fecha | efecto esperado |
|---|---|---|---|
{cm}

## 6. Plan
| paso | dueno | fecha |
|---|---|---|
{pl}

## 7. Seguimiento
{bullets(self.followup)}

---
_Generado con fde-field-kit. Los numeros de la seccion 2 son reproducibles:
correr `fdekit demo` sobre el mismo log devuelve los mismos valores._
"""


def build_a3_from_findings(
    title: str,
    owner: str,
    site: str,
    conformance: dict,
    bottleneck_row: dict,
    dq: dict,
    link: dict,
    travel: dict,
    charts: list[str] | None = None,
) -> A3:
    """Arma el A3 con los hallazgos del kit ya insertados.

    El objetivo es que la primera version del A3 salga del analisis, no de la
    memoria del consultor. Despues se edita a mano — pero se parte de numeros.
    """
    a3 = A3(title=title, owner=owner, site=site, charts=charts or [])

    a3.background = (
        f"Diagnostico de {conformance['cases']:,} pedidos del log del WMS. El flujo declarado en "
        f"el kickoff ({conformance['declared_flow']}) cubre solo el "
        f"{conformance['conformance_pct']}% de los casos reales."
    )

    a3.current_condition = [
        f"Conformidad con el flujo declarado: {conformance['conformance_pct']}% "
        f"({conformance['n_distinct_variants']} variantes distintas en el log).",
        f"Actividades que ocurren y no estaban declaradas: {', '.join(conformance['undeclared_activities']) or 'ninguna'}.",
        f"Mayor perdida de tiempo: {bottleneck_row['transition']} — "
        f"{bottleneck_row['total_wait_h']}h en la ventana "
        f"({bottleneck_row['pct_of_total_wait']}% de toda la espera del proceso).",
        f"Datos maestros: {dq['rates']['any_defect']['rate_pct']}% de SKUs con defecto "
        f"(IC95 {dq['rates']['any_defect']['ci_low_pct']}-{dq['rates']['any_defect']['ci_high_pct']}%). "
        f"Donde hay error dimensional, el volumen calculado se desvia "
        f"{dq['cube_error']['median_abs_pct_defective']}% (mediana).",
        f"Caminata: {travel['total_km']} km en la ventana, "
        f"{travel['median_m_per_order']} m por pedido (mediana).",
    ]

    a3.target_condition = [
        "Reducir en 50% el tiempo total de espera de la transicion critica.",
        f"Bajar la tasa de defecto de datos maestros bajo 5% en clase A (hoy "
        f"{dq['defect_rate_by_class_pct'].get('A', 'n/d')}%).",
        "Medicion con grupo de control definida y firmada antes del go-live.",
    ]

    a3.root_cause = [
        link.get("reading", "sin vinculo estadistico calculado"),
        f"Riesgo relativo de reproceso por maestro errado: {link.get('risk_ratio','n/d')}x "
        f"(p={link.get('p_value','n/d')}).",
        "La espera dominante es de cola, no de proceso: el recurso esta subdimensionado "
        "en el pico, no lento.",
    ]

    a3.add_countermeasure(
        "Corregir dimensiones de los SKUs clase A fuera de tolerancia",
        "Cliente — jefe de datos maestros",
        "semana 3",
        f"elimina ~{link.get('population_attributable_fraction_pct','?')}% del reproceso de carton",
    )
    a3.add_countermeasure(
        "Redimensionar la dotacion del recurso cuello en la ventana pico",
        "Cliente — jefe de operaciones",
        "semana 4",
        "reduce la espera dominante; validado por simulacion",
    )
    a3.add_countermeasure(
        "Congelar limites de control y encender el monitor de degradacion",
        "FDE",
        "go-live",
        "deteccion de degradacion antes del reclamo del cliente",
    )

    a3.plan = [
        {"paso": "Auditoria fisica de la muestra estratificada", "dueno": "FDE + cliente", "fecha": "semana 1-2"},
        {"paso": "Linea base medida con grupo de control", "dueno": "FDE", "fecha": "semana 3-6"},
        {"paso": "Piloto en una zona / una ola", "dueno": "FDE", "fecha": "semana 7-10"},
        {"paso": "Traspaso: runbook + hojas TWI firmadas", "dueno": "FDE", "fecha": "semana 11-12"},
    ]

    a3.followup = [
        "Revision semanal con el supervisor del turno, no con el sponsor.",
        "Grafico XmR de la metrica en la reunion de operaciones, no en un dashboard que nadie abre.",
        "Re-auditar el 10% de la muestra de datos maestros a los 90 dias.",
    ]
    return a3
