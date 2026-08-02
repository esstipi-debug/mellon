"""Caso de valor: Monte Carlo, VAN, payback y el detector de humo."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .archetypes import Archetype
from .levers import Lever


@dataclass
class ValueResult:
    annual_total_usd: np.ndarray
    annual_cash_usd: np.ndarray
    npv_usd: np.ndarray
    payback_months: np.ndarray
    per_lever: pd.DataFrame
    horizon_months: int
    cost_total_usd: float
    # Caja efectivamente ahorrada entre el mes 1 y el 12, despues de la rampa.
    # `annual_cash_usd` es run-rate en regimen; esto es lo que entra al P&L del
    # primer ano. Confundirlos es el sobreestimador silencioso mas comun.
    year1_cash_usd: np.ndarray = field(default_factory=lambda: np.array([]))

    def pct(self, arr: np.ndarray, q: float) -> float:
        # `payback_months` trae inf cuando no hay recuperacion dentro del
        # horizonte. Es informacion, no un error: se conserva el inf y se
        # silencia el aviso de numpy al interpolar entre infinitos.
        with np.errstate(invalid="ignore"):
            return float(np.percentile(arr, q))

    def summary(self) -> dict:
        return {
            "beneficio_anual_total_usd": {
                "p10": round(self.pct(self.annual_total_usd, 10)),
                "p50": round(self.pct(self.annual_total_usd, 50)),
                "p90": round(self.pct(self.annual_total_usd, 90)),
            },
            "beneficio_anual_caja_usd": {
                "p10": round(self.pct(self.annual_cash_usd, 10)),
                "p50": round(self.pct(self.annual_cash_usd, 50)),
                "p90": round(self.pct(self.annual_cash_usd, 90)),
            },
            "caja_primer_ano_usd": {
                "p50": round(self.pct(self.year1_cash_usd, 50)) if self.year1_cash_usd.size else None,
                "vs_run_rate": (
                    round(
                        float(np.percentile(self.year1_cash_usd, 50))
                        / max(float(np.percentile(self.annual_cash_usd, 50)), 1e-9),
                        2,
                    )
                    if self.year1_cash_usd.size
                    else None
                ),
            },
            "costo_total_proyecto_usd": round(self.cost_total_usd),
            "van_caja_usd": {
                "p10": round(self.pct(self.npv_usd, 10)),
                "p50": round(self.pct(self.npv_usd, 50)),
                "p90": round(self.pct(self.npv_usd, 90)),
            },
            "prob_van_positivo": round(float((self.npv_usd > 0).mean()), 3),
            "payback_meses": {
                "p50": _fmt_payback(self.pct(self.payback_months, 50)),
                "p90": _fmt_payback(self.pct(self.payback_months, 90)),
            },
            "horizonte_meses": self.horizon_months,
        }

    def to_markdown(self) -> str:
        s = self.summary()
        lev = self.per_lever
        rows = "\n".join(
            f"| {r['name']} | {r['unit']} | {r['p50_total_usd']:,.0f} | "
            f"{r['p50_cash_usd']:,.0f} | {r['cash_share']:.0%} | {r['source']} |"
            for _, r in lev.iterrows()
        )
        return f"""## Caso de valor

| palanca | unidad | beneficio p50 (USD/ano) | de eso, caja | % caja | medido por |
|---|---|---:|---:|---:|---|
{rows}

**Beneficio anual total** p50 USD {s['beneficio_anual_total_usd']['p50']:,}
(p10 {s['beneficio_anual_total_usd']['p10']:,} - p90 {s['beneficio_anual_total_usd']['p90']:,})

**De eso, caja** p50 USD {s['beneficio_anual_caja_usd']['p50']:,}. Es el unico
numero que el CFO va a aceptar como ahorro.

**VAN sobre caja** ({self.horizon_months} meses) p50 USD {s['van_caja_usd']['p50']:,} |
probabilidad de VAN positivo {s['prob_van_positivo']:.0%} |
payback p50 {s['payback_meses']['p50']} meses.
"""


def _fmt_payback(v: float):
    return None if not np.isfinite(v) else round(v, 1)


@dataclass
class ValueCase:
    archetype: Archetype
    levers: list[Lever]
    cost_to_serve_usd: float
    horizon_months: int = 36
    ramp_months: int = 6
    sites: int = 1
    has_control_group: bool = False
    # Dos curvas de experiencia, no una. El sitio 2 rinde casi lo mismo que el 1
    # (0.95) pero cuesta bastante menos (0.55): el descubrimiento ya se hizo, las
    # herramientas existen, y lo que queda es adaptar. Usar un solo multiplicador
    # para ambos hace que sumar sitios nunca mejore la economia, que es
    # exactamente lo contrario de por que existe un rollout.
    benefit_learning: float = 0.95
    cost_learning: float = 0.55
    seed: int = 0
    _result: ValueResult | None = field(default=None, repr=False)

    @staticmethod
    def _experience(sites: int, learning: float) -> float:
        if sites <= 1:
            return 1.0
        return float(sum(learning ** np.log2(i + 1) for i in range(sites)))

    @property
    def benefit_multiplier(self) -> float:
        return self._experience(self.sites, self.benefit_learning)

    @property
    def cost_multiplier(self) -> float:
        return self._experience(self.sites, self.cost_learning)

    def simulate(self, n: int = 20_000) -> ValueResult:
        rng = np.random.default_rng(self.seed)
        mult = self.benefit_multiplier

        total = np.zeros(n)
        cash = np.zeros(n)
        rows = []
        for lev in self.levers:
            t, c = lev.sample_annual_usd(rng, n)
            t, c = t * mult, c * mult
            total += t
            cash += c
            rows.append(
                {
                    "key": lev.key,
                    "name": lev.name,
                    "unit": lev.unit,
                    "p50_total_usd": float(np.percentile(t, 50)),
                    "p50_cash_usd": float(np.percentile(c, 50)),
                    "cash_share": lev.cash_share_mode,
                    "attribution_p50": float(np.percentile(lev.attribution.sample(rng, n), 50)),
                    "source": lev.source,
                }
            )

        cols = [
            "key", "name", "unit", "p50_total_usd", "p50_cash_usd",
            "cash_share", "attribution_p50", "source",
        ]
        per_lever = pd.DataFrame(rows, columns=cols)
        if not per_lever.empty:
            per_lever = per_lever.sort_values("p50_cash_usd", ascending=False)
        cost = self.cost_to_serve_usd * self.cost_multiplier

        npv, payback, year1 = _npv_payback(
            cash, cost, self.horizon_months, self.ramp_months, self.archetype.wacc
        )
        self._result = ValueResult(
            total, cash, npv, payback, per_lever, self.horizon_months, cost, year1
        )
        return self._result

    # ------------------------------------------------------------- guardrails

    def warnings(self, result: ValueResult | None = None) -> list[str]:
        """Detector de humo. Cada linea que devuelve es una pregunta que el
        cliente va a hacer — mejor responderla antes."""
        r = result or self._result
        if r is None:
            r = self.simulate(2_000)

        w: list[str] = []
        arch = self.archetype

        attr_p50 = float(np.median([l.attribution.mode for l in self.levers])) if self.levers else 0
        if attr_p50 > 0.6 and not self.has_control_group:
            w.append(
                f"atribucion mediana {attr_p50:.0%} sin grupo de control: no es estimable, "
                "es un deseo. Definir contrafactual (herramienta 6) antes de firmar."
            )

        labor = [l for l in self.levers if l.unit == "h/ano"]

        # Procedencia del flex. Es la variable mas importante del modelo, y un
        # prior sin validar no se puede llevar a una reunion de renovacion.
        if labor and arch.labor_regime == "sin_calibrar":
            w.append(
                "labor_flex_share sin regimen laboral calibrado: es la variable mas "
                "importante del modelo y esta corriendo con un prior sin validar. "
                "Usar labor_regime='chile'|'usa'|'australia'|'argentina'."
            )
        elif labor and arch.staffing_model == "planta_propia":
            w.append(
                f"modelo de dotacion asumido 'planta_propia' ({arch.labor_regime}): si el "
                "CD opera con 3PL, el numero cambia entre -30 y +25 puntos segun la "
                "clausula de volumen comprometido. Pedir el contrato antes que cualquier "
                "estadistica — la institucion que manda es el contrato, no el pais."
            )

        if labor and max(l.cash_share_mode for l in labor) > 0.5:
            w.append(
                f"cash_share de horas > 50% (labor_flex_share={arch.labor_flex_share:.0%}): "
                "solo cuenta como caja lo que se deja de pagar. El resto es capacidad."
            )

        # El sobreestimador silencioso mas comun segun el estudio de 4 paises:
        # reportar el run-rate como si fuera la caja del primer ano.
        if r.year1_cash_usd.size and r.pct(r.annual_cash_usd, 50) > 0:
            ratio = r.pct(r.year1_cash_usd, 50) / r.pct(r.annual_cash_usd, 50)
            if ratio > 0.90:
                w.append(
                    f"la caja del ano 1 es el {ratio:.0%} del run-rate: con una rampa de "
                    f"{self.ramp_months} mes(es) el modelo esta reportando practicamente "
                    "el regimen como si fuera caja del primer ano. La referencia del "
                    "estudio es 45-55%. Revisar ramp_months."
                )

        # Cada palanca se contrasta contra SU denominador. Comparar el beneficio
        # total contra los ingresos es el error clasico: para un 3PL el ingreso
        # es una tarifa por pedido, y para un mayorista la palanca dominante es
        # capital de trabajo, que no tiene nada que ver con la venta anual.
        annual = r.pct(r.annual_total_usd, 50)
        lev = r.per_lever.set_index("key")["p50_total_usd"].to_dict()

        labor_benefit = sum(v for k, v in lev.items() if k in ("L1_productividad", "L2_reproceso"))
        if arch.annual_labor_cost_usd > 0:
            share = labor_benefit / arch.annual_labor_cost_usd
            if share > 0.15:
                w.append(
                    f"las palancas de horas valen {share:.0%} de la base de costo laboral "
                    f"({arch.direct_ftes:.0f} FTE directos): estas prometiendo recortar 1 de "
                    f"cada {1/max(share,1e-9):.0f} horas de la operacion. Revisar el factor de escala."
                )

        capital = lev.get("L5_capital", 0.0)
        if arch.inventory_value_usd > 0 and arch.carrying_cost_pct > 0:
            freed = capital / arch.carrying_cost_pct
            if freed / arch.inventory_value_usd > 0.10:
                w.append(
                    f"se asume liberar {freed/arch.inventory_value_usd:.0%} del inventario por "
                    "calidad de datos. Sobre 10% hay que mostrar la politica de stock de "
                    "seguridad antes y despues, no un supuesto."
                )

        if annual > 0 and arch.annual_revenue_usd > 0:
            w.append(
                f"referencia: beneficio p50 = {annual/arch.annual_revenue_usd:.2%} de los "
                f"ingresos, {annual/max(arch.annual_labor_cost_usd,1):.1%} de la base laboral. "
                "Llevar ambos a la reunion; el CFO va a elegir el denominador que le convenga."
            )

        pb = r.pct(r.payback_months, 50)
        if np.isfinite(pb) and pb < 3:
            w.append(f"payback p50 de {pb:.1f} meses: demasiado bueno. Revisar la aritmetica.")

        if not np.isfinite(pb):
            w.append("no hay payback dentro del horizonte: el caso no se sostiene como esta.")

        if r.pct(r.annual_cash_usd, 50) / max(annual, 1e-9) < 0.25:
            w.append(
                "menos del 25% del beneficio es caja. Es un caso de capacidad, no de ahorro: "
                "venderlo como ahorro garantiza una discusion perdida en el mes 9."
            )

        if self.sites > 3 and self.cost_learning >= 0.9:
            w.append(
                f"rollout a {self.sites} sitios asumiendo casi cero aprendizaje en costo "
                f"(cost_learning={self.cost_learning}): el sitio 2 nunca cuesta lo mismo "
                "que el 1, y si lo cuesta el rollout no tiene sentido economico."
            )
        if self.sites > 1:
            w.append(
                f"rollout a {self.sites} sitios: beneficio x{self.benefit_multiplier:.2f}, "
                f"costo x{self.cost_multiplier:.2f}. Verificar contra los dias reales del "
                "segundo despliegue antes de comprometer el tercero."
            )
        return w


def _npv_payback(
    annual_cash: np.ndarray, cost: float, horizon: int, ramp: int, wacc: float
) -> tuple[np.ndarray, np.ndarray]:
    """VAN y payback mensual con rampa lineal de adopcion.

    El costo se carga en los primeros `ramp` meses (que es cuando el FDE esta
    en terreno) y el beneficio entra en rampa. Cargar todo el costo en el mes 0
    y todo el beneficio desde el mes 1 es la forma mas comun de inventar un
    payback de dos meses.
    """
    n = annual_cash.size
    monthly_rate = (1 + wacc) ** (1 / 12) - 1
    cum = np.zeros(n)
    npv = np.zeros(n)
    year1 = np.zeros(n)
    payback = np.full(n, np.inf)

    for m in range(1, horizon + 1):
        adoption = min(1.0, m / max(ramp, 1))
        benefit = annual_cash / 12 * adoption
        spend = cost / max(ramp, 1) if m <= ramp else 0.0
        disc = (1 + monthly_rate) ** m

        npv += (benefit - spend) / disc
        cum += benefit - spend
        if m <= 12:
            year1 += benefit
        newly = np.isinf(payback) & (cum > 0)
        payback[newly] = m

    return npv, payback, year1
