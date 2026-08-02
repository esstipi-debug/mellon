"""Diseno de la medicion: que metrica, cuanto tiempo, y que se puede detectar.

Se completa ANTES del go-live y se firma. Un spec de linea base firmado por el
sponsor operativo vale mas que cualquier clausula del contrato: convierte la
conversacion del dia 90 de "¿funciono?" a "¿cuanto dio?".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy import stats


@dataclass
class BaselineSpec:
    """El contrato de medicion. Se llena en el kickoff, no despues."""

    metric_name: str
    metric_definition: str  # formula exacta, no descripcion
    data_source: str  # tabla/endpoint concreto
    unit_of_analysis: str  # pedido, linea, turno, dia
    direction: str  # "lower_is_better" | "higher_is_better"
    target_change_pct: float
    baseline_window_days: int
    control_group: str | None = None  # zona/turno/ola que NO recibe el cambio
    known_confounders: tuple[str, ...] = ()
    owner_client_side: str = ""

    def to_markdown(self) -> str:
        d = asdict(self)
        rows = "\n".join(f"| {k} | {v} |" for k, v in d.items())
        return (
            f"### Spec de linea base — {self.metric_name}\n\n"
            "| campo | valor |\n|---|---|\n" + rows + "\n\n"
            "Firmado por: ______________  Fecha: __________\n"
        )

    def validate(self) -> list[str]:
        """Devuelve la lista de problemas. Vacia = listo para firmar."""
        issues = []
        if "/" not in self.metric_definition and "=" not in self.metric_definition:
            issues.append("metric_definition no parece una formula; escribir el calculo exacto")
        if self.baseline_window_days < 10:
            issues.append("ventana de linea base menor a 10 dias: no captura el ciclo semanal")
        if not self.control_group:
            issues.append(
                "sin grupo de control: cualquier cambio estacional se va a atribuir al proyecto"
            )
        if not self.owner_client_side:
            issues.append("sin dueno del lado del cliente: la medicion muere en la semana 3")
        if not self.known_confounders:
            issues.append("sin confusores listados: ¿de verdad no hay peak, promo ni contratacion?")
        return issues


def mde(
    sd: float, n_per_group: int, alpha: float = 0.05, power: float = 0.80, two_sided: bool = True
) -> float:
    """Efecto minimo detectable, en unidades de la metrica.

    Se corre ANTES de prometer un numero. Si el MDE es 12% y el cliente espera
    5%, el diseno no puede probar la promesa y hay que cambiar el diseno o la
    promesa — pero hay que decirlo el dia 1.
    """
    z_a = stats.norm.ppf(1 - alpha / (2 if two_sided else 1))
    z_b = stats.norm.ppf(power)
    return float((z_a + z_b) * sd * math.sqrt(2 / n_per_group))


def required_n(sd: float, effect: float, alpha: float = 0.05, power: float = 0.80) -> int:
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return int(math.ceil(2 * ((z_a + z_b) * sd / effect) ** 2))


def required_days(
    sd: float, effect: float, units_per_day: float, alpha: float = 0.05, power: float = 0.80, icc: float = 0.0
) -> dict:
    """Dias de medicion necesarios, con inflacion por correlacion intra-dia.

    `icc` es la correlacion intraclase: los pedidos del mismo dia se parecen
    entre si (mismo clima, misma dotacion, misma promo). Ignorarla es el error
    que hace que un piloto "significativo" no se replique. Con icc=0.02 y 300
    pedidos por dia, el tamano efectivo cae ~7x.
    """
    n = required_n(sd, effect, alpha, power)
    deff = 1 + (units_per_day - 1) * icc  # efecto de diseno
    n_eff = n * deff
    return {
        "n_per_group_naive": n,
        "design_effect": round(deff, 2),
        "n_per_group_adjusted": int(math.ceil(n_eff)),
        "days_per_group": math.ceil(n_eff / units_per_day),
        "mde_at_2_weeks": round(mde(sd, int(units_per_day * 14 / max(deff, 1)), alpha, power), 4),
    }


def sd_from_log(values) -> float:
    """Desviacion robusta (IQR/1.349). El tiempo de ciclo tiene colas largas y
    la sd clasica sobreestima el ruido."""
    v = np.asarray(values, dtype=float)
    q1, q3 = np.nanpercentile(v, [25, 75])
    return float((q3 - q1) / 1.349)
