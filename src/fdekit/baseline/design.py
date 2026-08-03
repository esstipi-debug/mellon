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


def icc_from_log(values, groups, strata=None, confidence: float = 0.95) -> dict:
    """Correlacion intraclase entre unidades del mismo grupo, medida del log.

    El `icc` de `required_days` era el parametro de mayor apalancamiento del
    bloque de medicion —multiplica el tamano de muestra por 17 con 300 pedidos
    al dia— y estaba puesto a mano. No hace falta ningun sensor para medirlo:
    hace falta la ventana historica que el cliente ya tiene. Esta funcion la
    convierte en un numero, que es la unica forma de que `days_per_group` deje
    de ser una opinion.

    ANOVA de una via de efectos aleatorios, que es el estimador estandar:

        ICC = (MSB - MSW) / (MSB + (k0 - 1) * MSW)

    `k0` es el tamano de grupo efectivo, que NO es el promedio cuando los dias
    traen distinta cantidad de pedidos — usar el promedio simple sesga el ICC
    hacia arriba justo cuando hay dias de peak, que es cuando importa.

    `strata` resta la media de cada estrato antes de estimar. Sirve para lo que
    siempre aparece en una ventana historica real: un cambio de nivel conocido
    —peak, cambio de layout, alta de dotacion— que sin remover se cuela como si
    fuera correlacion intra-dia e infla el ICC. Removerlo es la diferencia entre
    medir el ruido del dia y medir la estacionalidad.

    Devuelve intervalo por la F (Searle) porque un ICC puntual sobre pocos dias
    es tan blando como el 0,02 que vino a reemplazar: con 6 dias el intervalo es
    ancho, y eso hay que verlo antes de comprometer una ventana de medicion.
    """
    v = np.asarray(values, dtype=float)
    g = np.asarray(groups)
    if strata is not None:
        s = np.asarray(strata)
        v = v.copy()
        for lab in np.unique(s):
            m = s == lab
            v[m] = v[m] - v[m].mean()

    ok = ~np.isnan(v)
    v, g = v[ok], g[ok]
    labels, counts = np.unique(g, return_counts=True)
    m, n = len(labels), len(v)

    base = {
        "n_groups": int(m),
        "n_units": int(n),
        "strata_removed": strata is not None,
    }
    # Los dos modos de fallar son distintos y la accion que piden tambien, asi
    # que se diagnostican por separado: con un solo dia hay que pedir mas
    # ventana, con un valor por dia hay que pedir otro nivel de grano.
    if m < 2:
        return {
            **base,
            "icc": None,
            "icc_for_design": None,
            "usable": False,
            "reason": (
                f"{m} grupo(s): hacen falta al menos 2 dias para separar la varianza entre "
                "dias de la de adentro del dia. El ICC queda SIN MEDIR, que no es lo mismo "
                "que cero — pedir mas ventana historica."
            ),
        }
    if n <= m:
        return {
            **base,
            "icc": None,
            "icc_for_design": None,
            "usable": False,
            "reason": (
                f"{n} unidades en {m} grupos: hay un solo valor por dia. El log viene "
                "agregado y no queda varianza intra-dia que medir — hay que pedirlo a "
                "nivel de pedido. El ICC queda SIN MEDIR, que no es lo mismo que cero."
            ),
        }

    grand = v.mean()
    means = np.array([v[g == lab].mean() for lab in labels])
    ssb = float((counts * (means - grand) ** 2).sum())
    ssw = float(sum(((v[g == lab] - mu) ** 2).sum() for lab, mu in zip(labels, means)))
    df_b, df_w = m - 1, n - m
    msb, msw = ssb / df_b, ssw / df_w

    # Tamano de grupo efectivo. Con grupos iguales coincide con el tamano.
    k0 = (n - (counts.astype(float) ** 2).sum() / n) / df_b

    if msw <= 0:
        return {
            **base,
            "icc": None,
            "icc_for_design": None,
            "usable": False,
            "reason": (
                "varianza intra-grupo cero: el log esta agregado a nivel de dia, o todas "
                "las unidades del dia son identicas. Con un solo valor por dia no hay ICC "
                "que estimar — hay que pedir el log a nivel de pedido."
            ),
        }

    icc = (msb - msw) / (msb + (k0 - 1) * msw)
    f = msb / msw
    a = 1 - confidence
    f_hi = float(stats.f.ppf(1 - a / 2, df_b, df_w))
    f_lo = float(stats.f.ppf(1 - a / 2, df_w, df_b))
    fl, fu = f / f_hi, f * f_lo

    def to_icc(fv: float) -> float:
        return (fv - 1) / (fv + k0 - 1)

    return {
        **base,
        "icc": round(float(icc), 4),
        # Un ICC negativo es ruido, no una propiedad: significa que las unidades
        # del mismo dia se parecen MENOS que al azar. Llevarlo al diseno daria un
        # efecto de diseno bajo 1 —clustering que "ayuda"— y subestimaria la
        # muestra. Se reporta crudo y se acota a 0 para el calculo.
        "icc_for_design": round(max(0.0, float(icc)), 4),
        "ci_low": round(float(to_icc(fl)), 4),
        "ci_high": round(float(to_icc(fu)), 4),
        "mean_group_size_effective": round(float(k0), 1),
        "f_stat": round(float(f), 2),
        "usable": True,
        "reason": (
            ""
            if m >= 10
            else f"solo {m} grupos: el ICC puntual es blando y el intervalo lo muestra. "
            "Para comprometer una ventana de medicion, estimarlo sobre 4 semanas."
        ),
    }
