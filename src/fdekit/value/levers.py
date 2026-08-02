"""Palancas de valor: las seis cosas que el trabajo del FDE efectivamente mueve.

Cada palanca sale de una herramienta concreta del kit. Si una palanca no tiene
herramienta que la mida, no entra al caso — esa es la regla que separa este
modelo de una planilla de vendor.

    L1 productividad    <- gemba pareto, standard_work_gap, travel_stats
    L2 reproceso        <- rework_summary + link_defects_to_rework (PAF)
    L3 capacidad        <- sizing_sweep (la rodilla de la curva)
    L4 nivel de servicio<- cycle_time_stats + diff_in_diff
    L5 capital de trabajo<- auditoria de maestros (error de cubicaje y stock)
    L6 incidentes       <- probe (EDI/contratos) + spc (degradacion)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Range:
    """Distribucion triangular. Un numero puntual es una opinion disfrazada."""

    low: float
    mode: float
    high: float

    @staticmethod
    def of(value, spread: float = 0.0) -> "Range":
        if isinstance(value, Range):
            return value
        v = float(value)
        return Range(v * (1 - spread), v, v * (1 + spread))

    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if self.high - self.low < 1e-12:
            return np.full(n, self.mode)
        return rng.triangular(self.low, np.clip(self.mode, self.low, self.high), self.high, n)

    def __repr__(self) -> str:
        return f"({self.low:.3g} / {self.mode:.3g} / {self.high:.3g})"


@dataclass
class Lever:
    """Una palanca de valor.

    annual_units  unidades fisicas al ano (horas, pedidos, USD de inventario)
    usd_per_unit  valor economico de una unidad
    cash_share    fraccion que llega al estado de resultados como caja
    attribution   fraccion del efecto atribuible al proyecto
    realization   fraccion del potencial que se captura en regimen
    source        que herramienta del kit lo midio (trazabilidad)
    """

    key: str
    name: str
    unit: str
    annual_units: Range
    usd_per_unit: Range
    cash_share: float | Range
    attribution: Range
    realization: Range
    source: str = ""

    @property
    def cash_share_mode(self) -> float:
        """El punto central, para tablas y guardrails."""
        return self.cash_share.mode if isinstance(self.cash_share, Range) else self.cash_share

    def sample_annual_usd(self, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Devuelve (beneficio_total, beneficio_caja) anual en regimen.

        `cash_share` acepta un Range: la fraccion de una hora liberada que se
        convierte en caja es la variable mas importante del modelo y era la
        unica sin incertidumbre. Depende de la composicion contractual del
        cliente —planta, plazo fijo, suministro transitorio— y de la estacion,
        y eso no se conoce con un decimal.
        """
        gross = (
            self.annual_units.sample(rng, n)
            * self.usd_per_unit.sample(rng, n)
            * np.clip(self.attribution.sample(rng, n), 0, 1)
            * np.clip(self.realization.sample(rng, n), 0, 1)
        )
        share = (
            np.clip(self.cash_share.sample(rng, n), 0, 1)
            if isinstance(self.cash_share, Range)
            else self.cash_share
        )
        return gross, gross * share


# Perfiles por defecto de cada palanca. `cash_share` es lo mas discutible y por
# eso esta explicito: es la conversacion que hay que tener con el controller del
# cliente en la semana 2, no en el mes 9.
LEVER_CATALOG: dict[str, dict] = {
    "L1_productividad": {
        "name": "Horas de operacion recuperadas",
        "unit": "h/ano",
        "cash_share": None,  # lo define labor_flex_share del arquetipo
        "source": "gemba.pareto + timestudy.standard_work_gap + travel_stats",
    },
    "L2_reproceso": {
        "name": "Reproceso evitado",
        "unit": "h/ano",
        "cash_share": None,
        "source": "processmining.rework_summary + dataquality.link_defects_to_rework",
    },
    "L3_capacidad": {
        "name": "Capex / dotacion diferida",
        "unit": "estaciones",
        "cash_share": 1.0,  # no gastar es caja pura
        "source": "sim.sizing_sweep",
    },
    "L4_servicio": {
        "name": "Pedidos fuera de SLA evitados",
        "unit": "pedidos/ano",
        "cash_share": 0.7,  # parte es penalidad real, parte es retencion difusa
        "source": "timestudy.cycle_time_stats + baseline.diff_in_diff",
    },
    "L5_capital": {
        "name": "Capital de trabajo liberado",
        "unit": "USD de inventario",
        "cash_share": 1.0,  # el costo de mantener es caja
        "source": "dataquality.audit_summary",
    },
    "L6_incidentes": {
        "name": "Incidentes de integracion evitados",
        "unit": "incidentes/ano",
        "cash_share": 0.6,
        "source": "probe.smoke_report + spc.degradation_alarm",
    },
}


def _attr(has_control_group: bool) -> Range:
    """Atribucion segun el diseno de medicion.

    Sin grupo de control no se puede atribuir; se puede estimar, con descuento
    fuerte y un rango ancho que refleje la ignorancia real. Con DiD medido el
    rango se angosta y sube. Esta funcion es, en una linea, todo el argumento
    comercial de la herramienta 6.
    """
    return Range(0.65, 0.85, 0.95) if has_control_group else Range(0.20, 0.40, 0.65)


def levers_from_findings(
    findings: dict,
    arch,
    has_control_group: bool = False,
    realization: Range | float = 0.7,
) -> list[Lever]:
    """Arma las palancas desde el `hallazgos.json` que produce `fdekit demo`.

    Los hallazgos del kit estan expresados en la ventana observada (un turno);
    aca se convierten a base anual con los dias de operacion del arquetipo, y se
    escalan al volumen del cliente — el CD sintetico no tiene el tamano del CD
    del cliente y confundir los dos es el error mas caro del modelo.
    """
    real = Range.of(realization, 0.25) if not isinstance(realization, Range) else realization
    attribution = _attr(has_control_group)

    # La conversion a caja de una hora liberada entra como distribucion, no como
    # punto: depende de la composicion contractual del cliente y del pais, y
    # fingir que se conoce con un decimal es como se pierde la reunion del mes 9.
    lo, mode, hi = arch.cash_labor_bounds()
    labor_cash = Range(lo, mode, hi)

    # Factor de escala: el kit midio N pedidos, el cliente procesa otros tantos.
    observed_orders = float(findings.get("cycle_times", {}).get("n_cases", 1)) or 1.0
    scale = arch.annual_orders / (observed_orders * arch.operating_days)

    levers: list[Lever] = []

    # --- L1: caminata excedente + brecha de trabajo estandar
    walk_h = float(findings.get("travel", {}).get("walking_hours_annual", 0.0)) * scale
    slot_cut = float(findings.get("slotting", {}).get("reduction_pct", 0.0)) / 100
    sw_h = float(findings.get("standard_work_gap", {}).get("recoverable_hours_annual", 0.0)) * scale
    l1_units = walk_h * slot_cut + sw_h
    if l1_units > 0:
        levers.append(
            Lever(
                "L1_productividad",
                LEVER_CATALOG["L1_productividad"]["name"],
                "h/ano",
                Range(l1_units * 0.6, l1_units, l1_units * 1.2),
                Range.of(arch.labor_usd_h, 0.10),
                cash_share=labor_cash,
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L1_productividad"]["source"],
            )
        )

    # --- L2: reproceso, acotado por la fraccion atribuible a datos maestros
    rework_h = sum(float(r.get("annual_hours_lost", 0)) for r in findings.get("rework", [])) * scale
    paf = float(findings.get("defects_to_rework", {}).get("population_attributable_fraction_pct", 0)) / 100
    if rework_h > 0:
        # El PAF es el techo de lo que se elimina arreglando el maestro. Usarlo
        # como piso del rango y no como punto es lo honesto: parte del reproceso
        # tiene otras causas que el proyecto no toca.
        levers.append(
            Lever(
                "L2_reproceso",
                LEVER_CATALOG["L2_reproceso"]["name"],
                "h/ano",
                Range(rework_h * paf * 0.5, rework_h * max(paf, 0.05), rework_h * min(paf * 2.5, 0.8)),
                Range.of(arch.labor_usd_h, 0.10),
                cash_share=labor_cash,
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L2_reproceso"]["source"],
            )
        )

    # --- L3: capacidad diferida, leida de la rodilla del barrido
    sweep = findings.get("sizing_sweep", [])
    deferred = _knee_savings(sweep)
    if deferred > 0:
        levers.append(
            Lever(
                "L3_capacidad",
                LEVER_CATALOG["L3_capacidad"]["name"],
                "estaciones",
                Range(deferred * 0.5, deferred, deferred * 1.5),
                Range.of(arch.capex_per_station_usd * arch.wacc, 0.20),  # costo anual de diferir
                cash_share=1.0,
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L3_capacidad"]["source"],
            )
        )

    # --- L4: servicio, desde el efecto medido en tiempo de ciclo
    did = findings.get("diff_in_diff", {})
    improvement = -float(did.get("did_pct_of_baseline", 0.0)) / 100  # negativo = mejora
    if improvement > 0:
        # Supuesto explicito: la tasa de incumplimiento de SLA cae proporcional
        # a la mejora de la cola, con elasticidad 0.5 (conservadora).
        late_rate = 0.06
        avoided = arch.annual_orders * late_rate * improvement * 0.5
        levers.append(
            Lever(
                "L4_servicio",
                LEVER_CATALOG["L4_servicio"]["name"],
                "pedidos/ano",
                Range(avoided * 0.4, avoided, avoided * 1.6),
                Range.of(arch.late_order_cost_usd, 0.25),
                cash_share=LEVER_CATALOG["L4_servicio"]["cash_share"],
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L4_servicio"]["source"],
            )
        )

    # --- L5: capital de trabajo por datos maestros confiables
    dq_rate = float(
        findings.get("data_quality", {}).get("rates", {}).get("any_defect", {}).get("rate_pct", 0)
    ) / 100
    if arch.inventory_value_usd > 0 and dq_rate > 0:
        # Regla de terreno: el stock de seguridad absorbe la desconfianza en el
        # maestro. Bajar la tasa de defecto libera una fraccion del colchon.
        freed = arch.inventory_value_usd * dq_rate * 0.15
        levers.append(
            Lever(
                "L5_capital",
                LEVER_CATALOG["L5_capital"]["name"],
                "USD de inventario",
                Range(freed * 0.3, freed, freed * 1.4),
                Range.of(arch.carrying_cost_pct, 0.15),
                cash_share=1.0,
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L5_capital"]["source"],
            )
        )

    # --- L6: incidentes evitados
    edi_errors = sum(1 for r in findings.get("edi_smoke", []) if r.get("severity") == "ERROR")
    contract_errors = sum(1 for r in findings.get("contract_check", []) if r.get("severity") == "ERROR")
    found = edi_errors + contract_errors
    if found:
        # Cada defecto de contrato detectado antes del go-live evita entre 0.5 y
        # 3 incidentes al ano. Rango ancho a proposito: es el numero mas blando
        # del modelo y hay que decirlo.
        levers.append(
            Lever(
                "L6_incidentes",
                LEVER_CATALOG["L6_incidentes"]["name"],
                "incidentes/ano",
                Range(found * 0.5, found * 1.2, found * 3.0),
                Range.of(arch.incident_cost_usd, 0.30),
                cash_share=LEVER_CATALOG["L6_incidentes"]["cash_share"],
                attribution=attribution,
                realization=real,
                source=LEVER_CATALOG["L6_incidentes"]["source"],
            )
        )

    return levers


def _knee_savings(sweep: list[dict]) -> float:
    """Estaciones diferidas = las que el cliente iba a comprar menos las que la
    curva muestra necesarias en la rodilla.

    La rodilla es el ultimo punto donde agregar un recurso todavia compra mas de
    5% de mejora en el ciclo. Despues de eso se paga capex por nada, que es lo
    que el vendor de turno recomienda igual.
    """
    if len(sweep) < 2:
        return 0.0
    rows = sorted(sweep, key=lambda r: r["n_pickers"])
    knee = rows[0]["n_pickers"]
    for a, b in zip(rows, rows[1:]):
        gain = (a["mean_cycle_min"] - b["mean_cycle_min"]) / max(a["mean_cycle_min"], 1e-9)
        if gain > 0.05:
            knee = b["n_pickers"]
    return max(0.0, float(rows[-1]["n_pickers"] - knee))
