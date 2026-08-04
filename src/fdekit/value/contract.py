"""Contrato de `hallazgos.json`: que lee el caso economico y de donde.

`levers_from_findings` lee el archivo con `.get(clave, 0.0)` en cada nivel. Eso
es correcto para el archivo que produce `fdekit demo`, y peligroso para
cualquier otro: si un bloque no viene, el termino que dependia de el vale cero y
la palanca sigue apareciendo, mas chica, sin una sola linea de aviso.

`_reject_preannualized` ya cubre la mitad del problema —rechaza los nombres de
clave viejos— pero solo esos. No cubre el caso que importa ahora: un productor
DISTINTO de `fdekit demo` que emita algunos bloques y no otros. Con un segundo
productor, "el bloque no esta" deja de ser un caso legacy y pasa a ser el caso
normal.

Los dos casos extremos ya estan bien y tienen test:

    findings = {}          -> ninguna palanca. `test_findings_vacio_no_inventa_una_palanca`
    findings completo      -> las seis palancas

El que falta es el del medio, y es el unico que miente:

    findings parcial       -> la palanca aparece, subestimada, y parece completa

Ejemplo concreto: sin el bloque `travel`, L1 pierde la caminata excedente pero
conserva la brecha de trabajo estandar y las horas de gemba. Sale un numero
plausible al que le falta un termino entero. El VAN se imprime igual.

Este modulo no decide nada: declara que campo lee cada palanca y responde cual
falto. Lo que se hace con esa respuesta es de quien llama.
"""

from __future__ import annotations

# Subir cuando cambie un nombre de campo consumido, no cuando se agregue una
# seccion nueva a `hallazgos.json`: el contrato es lo que se LEE, no lo que se
# escribe. El archivo trae unas treinta secciones; el caso economico toca once
# campos.
CONTRACT_VERSION = 1

# Que campo lee cada palanca. Es dato y no prosa a proposito: el chequeo de
# conformidad, el mensaje de aviso y la documentacion salen todos de aca, asi
# que no pueden desincronizarse de la lista.
#
# Notacion: `a.b` es anidado; `bloque[].campo` es una lista de filas donde cada
# fila tiene ese campo; `bloque[]` es una lista cuyo contenido se recorre entero.
FINDINGS_CONTRACT: dict[str, tuple[str, ...]] = {
    "L1_productividad": (
        "cycle_times.n_cases",
        "travel.orders",
        "travel.walking_hours_in_window",
        "slotting.reduction_pct",
        "standard_work_gap.cases_in_window",
        "standard_work_gap.recoverable_hours_in_window",
        "gemba.value_input.hours_per_shift",
    ),
    "L2_reproceso": (
        "rework[].hours_lost_in_window",
        "rework[].cases_in_window",
        "defects_to_rework.population_attributable_fraction_pct",
    ),
    "L3_capacidad_diferida": ("sizing_sweep[]",),
    "L4_servicio": ("diff_in_diff",),
    "L5_capital_de_trabajo": ("data_quality.rates.any_defect.rate_pct",),
    "L6_incidentes": ("edi_smoke[].severity", "contract_check[].severity"),
}


def _presente(findings: dict, path: str) -> bool:
    """Si el campo esta declarado. Presente y en cero NO es lo mismo que ausente.

    Un `rework: []` es una medicion: se busco reproceso y no habia. Un
    `hallazgos.json` sin la clave `rework` es otra cosa: nadie la midio. La
    primera vale cero de verdad; la segunda no vale cero, no se sabe. Es la
    misma distincion de tres estados que `Observation.in_event_log`.
    """
    if path.endswith("[]"):
        return isinstance(findings.get(path[:-2]), list)

    if "[]." in path:
        bloque, campo = path.split("[].", 1)
        filas = findings.get(bloque)
        if not isinstance(filas, list):
            return False
        # Lista vacia: medido, sin filas. Lista con filas a las que les falta el
        # campo: el formato no es el que se espera.
        return all(isinstance(f, dict) and campo in f for f in filas)

    nodo = findings
    for parte in path.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return False
        nodo = nodo[parte]
    return True


def findings_contract(findings: dict) -> dict:
    """Que palanca puede calcularse entera, cual a medias y cual no.

    `PARCIAL` es el unico estado que hay que mirar: `COMPLETA` esta bien y
    `AUSENTE` ya se nota porque la palanca no aparece en el resultado. Una
    palanca parcial aparece con un numero mas chico y nada la distingue de una
    entera.
    """
    palancas = {}
    for palanca, campos in FINDINGS_CONTRACT.items():
        ausentes = tuple(c for c in campos if not _presente(findings, c))
        if not ausentes:
            estado = "COMPLETA"
        elif len(ausentes) == len(campos):
            estado = "AUSENTE"
        else:
            estado = "PARCIAL"
        palancas[palanca] = {
            "estado": estado,
            "ausentes": ausentes,
            "presentes": tuple(c for c in campos if c not in ausentes),
        }

    parciales = tuple(k for k, v in palancas.items() if v["estado"] == "PARCIAL")
    completas = tuple(k for k, v in palancas.items() if v["estado"] == "COMPLETA")
    ausentes = tuple(k for k, v in palancas.items() if v["estado"] == "AUSENTE")

    if parciales:
        detalle = "; ".join(
            f"{k} sin {', '.join(palancas[k]['ausentes'])}" for k in parciales
        )
        nota = (
            f"{len(parciales)} palanca(s) SUBESTIMADA(S) por campos ausentes: {detalle}. "
            "El caso economico se calcula igual y el numero sale mas chico sin decirlo."
        )
    else:
        nota = (
            f"{len(completas)} palanca(s) completa(s), {len(ausentes)} sin datos. "
            "Ninguna subestimada."
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "palancas": palancas,
        "completas": completas,
        "parciales": parciales,
        "ausentes": ausentes,
        "cuadra": len(completas) + len(parciales) + len(ausentes) == len(FINDINGS_CONTRACT),
        "nota": nota,
    }
