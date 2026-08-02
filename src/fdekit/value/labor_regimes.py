"""Calibracion de `labor_flex_share` por pais y por modelo de dotacion.

Estudio del 1-ago-2026: cuatro paises, un investigador y un refutador
adversarial por pais, mas un marco metodologico y una sintesis. Los numeros que
quedan son los del **refutador**, que bajo tres de las cuatro estimaciones.

Lo que mide: de 1.000 horas de trabajo directo liberadas por un proyecto, que
fraccion se convierte en egreso de caja evitado dentro de 12 meses. El resto
queda como capacidad ociosa — gente en planilla que sigue cobrando igual.

Cuatro vias, y una particion exhaustiva y excluyente para no contar dos veces:

    h_OT    horas con recargo, sin importar quien las trabaje  (prioridad 1)
    h_TEMP  horas a tarifa normal de eventuales                 (prioridad 2)
    h_PERM  horas a tarifa normal de permanentes                (residual)

La prioridad va al recargo: una hora extra de un eventual ahorra la tarifa con
recargo, no la normal. Sumar "30% eventual" de una fuente y "10% sobretiempo"
de otra es sumar porcentajes sobre bases solapadas — el error mas comun.

DOS CORRECCIONES QUE EL ESTUDIO OBLIGO A HACER EN ESTE MODULO:

1. El estudio expresa `labor_flex_share` **en horas**, y reporta el multiplicador
   de caja (recargo de sobretiempo, markup de agencia) por separado. El modelo
   multiplicaba la fraccion por `overtime_premium`, lo que aplicaba el recargo
   tambien a las horas que no son extra. Ver `Archetype.cash_labor_bounds`.

2. La diferencia grande no la hace el arquetipo de empresa: la hace el **modelo
   de dotacion**, y en particular la clausula de volumen comprometido del
   contrato. Un 3PL open-book en Chile puede tener mas flexibilidad de caja que
   planta propia en EE.UU. Pedir el contrato antes que cualquier estadistica.

SESGO DECLARADO. Los rangos de aca son **caja del ano 1**, que es la cifra que
el estudio verifico. El modelo los usa como si fueran run-rate y despues les
aplica su propia rampa de adopcion, que los descuenta una segunda vez (~x0,79
con `ramp_months=6`). O sea: las palancas de horas quedan subestimadas ~21%.

Se elige a proposito. La alternativa era usar el run-rate, que el estudio marca
como "derivado, no medido". Entre un numero verificado que subestima y uno
derivado que podria sobreestimar, en la variable mas incierta del modelo, se
toma el verificado — y se dice que subestima, en vez de esconderlo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

VERIFICADO_AL = "2026-08-01"


@dataclass(frozen=True)
class LaborRegime:
    """Rango verificado de `labor_flex_share` para un pais.

    Los tres valores son **caja del ano 1**, no run-rate. Es la distincion que
    hundio la estimacion chilena del investigador: reporto 0,88 —el run-rate—
    despues de haber escrito en su propio informe que habia que reportar la caja
    (0,55). Regla del estudio: `flex_cash_y1 ~ 0,45-0,55 x flex_run_rate`.
    """

    country: str
    name: str
    low: float
    mode: float
    high: float
    run_rate_ref: float  # derivado, no medido: solo para cruzar
    driver: str  # la institucion concreta que produce la diferencia
    sources: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()

    @property
    def spread(self) -> float:
        return self.high / self.low if self.low else float("inf")


REGIMES: dict[str, LaborRegime] = {
    "usa": LaborRegime(
        country="usa",
        name="Estados Unidos",
        low=0.25, mode=0.58, high=0.85, run_rate_ref=0.80,
        driver=(
            "empleo at-will: el costo de salida S ~ 0 meses, asi que no existe el mes "
            "de quiebre. El WARN Act no se dispara en el caso de uso real (umbrales de "
            "50/100 empleados). La evidencia es revelada, no teorica: JOLTS registra "
            "19,5% anual de layoffs and discharges en el sector"
        ),
        sources=(
            "BLS JOLTS, separaciones en transportation/warehousing/utilities",
            "BLS OEWS May-2025 (NAICS 493 vs 561320)",
            "BLS CES serie CEU4349300001",
        ),
        caveats=(
            "s_TEMP es esencialmente s_AGENCIA: hay 2.593.250 empleados en NAICS 561320 "
            "contra 1.963.680 en NAICS 493, y las agencias no se cuentan en el sector",
            "lambda_TEMP < 1: el trabajador de agencia gana ~20,5% menos que el de "
            "nomina propia, asi que apagar una hora de agencia ahorra MENOS que apagar "
            "una interna. Es al reves del supuesto habitual, aunque la materialidad es baja",
            "heterogeneidad estatal alta (New Jersey tiene reglas propias de agencias)",
        ),
    ),
    "argentina": LaborRegime(
        country="argentina",
        name="Argentina",
        low=0.15, mode=0.55, high=0.90, run_rate_ref=0.95,
        driver=(
            "la reforma de la Ley 27.742 y el uso intensivo de Empresas de Servicios "
            "Eventuales. El CCT 40/89 item 5.11.6 establece que el eventual percibe el "
            "convenio completo: no hay descuento salarial por usar eventuales, solo "
            "flexibilidad — y con el markup de la ESE, la hora de agencia CUESTA MAS "
            "que la interna, asi que apagarla ahorra mas"
        ),
        sources=(
            "Ley 24.013 y decreto 1694/2006 (Empresas de Servicios Eventuales)",
            "art. 29 LCT texto Ley 27.802 (solidaridad limitada de la usuaria)",
            "CCT 40/89 Camioneros, item 5.11.6",
        ),
        caveats=(
            "EL MAS FRAGIL DE LOS CUATRO. El refutador demostro que la moda de 0,55 "
            "sobrevive por compensacion de dos errores de signo opuesto, no porque el "
            "modelo sea correcto. Su analisis de sensibilidad publicado es enganoso",
            "el rango 0,15-0,90 es el mas ancho del estudio y refleja incertidumbre "
            "real, no falta de trabajo",
            "no se encontro ninguna estadistica argentina de estacionalidad en CDs",
        ),
    ),
    "chile": LaborRegime(
        country="chile",
        name="Chile",
        low=0.15, mode=0.45, high=0.70, run_rate_ref=0.80,
        driver=(
            "la restriccion chilena es de PRECIO, no de permiso: no hay autorizacion "
            "administrativa previa para despedir y el finiquito se paga en 10 dias "
            "habiles, pero la indemnizacion por anos de servicio pone el mes de quiebre "
            "lejos. El peak de retail cabe holgadamente en la ventana de 90 dias del "
            "art. 183-N de las EST; la operacion de regimen no"
        ),
        sources=(
            "Encla 2023 cap. 12 (Direccion del Trabajo)",
            "Ley 20.123 sobre subcontratacion y suministro de trabajadores transitorios",
        ),
        caveats=(
            "el investigador reporto 0,88 —el run-rate— despues de escribir en su propio "
            "informe que habia que reportar la caja. Es el error mas caro del estudio",
            "s_TEMP hay que leerlo en la fila de GRAN EMPRESA de la Encla (25,5%), no en "
            "la fila sectorial (10,7%), que es una mezcla por tamano de empresa",
            "subcontratacion en gran empresa: 54,4%, no el 34,9% nacional. El canal de "
            "subcontratacion es grande y no lo cubre la particion OT/TEMP/PERM",
            "el s_OT de la Encla (2,1%) tiene mes de referencia NOVIEMBRE 2022 —peak de "
            "retail—. Que el sobretiempo este en minimo justo en el peak debilita la "
            "hipotesis de que el almacen chileno usa poco sobretiempo",
        ),
    ),
    "australia": LaborRegime(
        country="australia",
        name="Australia",
        low=0.18, mode=0.42, high=0.78, run_rate_ref=0.65,
        driver=(
            "el empleo casual con 25% de loading y sin preaviso. Pero el costo de salida "
            "de un permanente es bajo (S ~ 2,53 meses segun la escala del Fair Work Act "
            "s.119 y la tabla de s.117), asi que Australia se parece a EE.UU. en caja de "
            "salida aunque su indice EPL diga otra cosa"
        ),
        sources=(
            "ABS Working Arrangements / Characteristics of Employment, division I",
            "Fair Work Act s.117 y s.119 (preaviso e indemnizacion por redundancia)",
            "Storage Services and Wholesale Award 2020 (MA000084)",
            "ABS Labour Account (labour hire se clasifica a ANZSIC 7212)",
        ),
        caveats=(
            "el s_OT de ANZSIC 53 (3,74%) es el UNICO parametro genuinamente medido "
            "sobre almacenamiento en los cuatro paises",
            "la linea base publicada esta medida en el VALLE: el mes de referencia de "
            "ABS Working Arrangements es agosto, pre-peak en el hemisferio sur. El 21,1% "
            "de casuales de la division I subestima el noviembre de un CD de retail",
            "las horas de labour hire se clasifican fuera de la division del CD, asi que "
            "no aparecen en la estadistica del sector",
        ),
    ),
}


# ------------------------------------------------------- modelo de dotacion

# JUICIO, NO MEDICION. Ninguna estadistica oficial de ningun pais publica
# s_TEMP ni rotacion por modelo de dotacion. Son deltas construidos sobre
# reglas contractuales verificadas mas aritmetica declarada.
#
# Cuando el CD opera con 3PL, las horas liberadas no estan en la nomina: estan
# en una factura. Eso las saca del Codigo del Trabajo y las mete en el contrato
# comercial, y la clausula que manda es la de volumen comprometido.
STAFFING_MODELS: dict[str, dict] = {
    "planta_propia": {
        "delta": (0.0, 0.0),
        "desc": "dotacion propia 100%",
        "mecanismo": "el resultado depende entero de la rotacion, del costo de salida y "
        "de la voluntad organizacional de ceder dotacion",
    },
    "3pl_open_book": {
        "delta": (0.10, 0.25),
        "desc": "3PL open-book / cost-plus con FTE facturados por hora",
        "mecanismo": "reducir un FTE facturado es una enmienda de orden de compra, no un "
        "despido. El costo de salida sale del P&L del cliente. Es el unico arreglo donde "
        "el mes de quiebre deja de existir como restriccion",
    },
    "3pl_closed_book": {
        "delta": (0.0, 0.05),
        "desc": "3PL closed-book / precio fijo por unidad manipulada",
        "mecanismo": "la eficiencia se captura SOLO en la renegociacion de tarifa, "
        "tipicamente en el aniversario del contrato. Un proyecto que corre en el mes 3 "
        "puede no ver un peso hasta el mes 13. En run-rate el delta seria +0,05 a +0,15; "
        "en caja del ano 1 es casi cero",
    },
    "3pl_volumen_comprometido": {
        "delta": (-0.30, -0.10),
        "desc": "3PL con volumen minimo comprometido o management fee piso",
        "mecanismo": "la clausula de volumen minimo actua exactamente como una garantia "
        "de horas. Es el peor caso de los cinco y el mas frecuente en 3PL dedicado",
    },
    "mix": {
        "delta": (0.05, 0.15),
        "desc": "nucleo propio + agencia en el margen",
        "mecanismo": "el eventual esta concentrado, no repartido: el delta aplica SOLO si "
        "el proyecto ataca el turno o la zona donde efectivamente esta el eventual",
    },
}


def flex_bounds(
    country: str, staffing_model: str = "planta_propia"
) -> tuple[float, float, float]:
    """(low, mode, high) de `labor_flex_share` para un pais y modelo de dotacion.

    El delta del modelo de dotacion se aplica asimetrico: el extremo bajo del
    delta al low y el alto al high, de modo que un contrato desconocido ensancha
    el rango en vez de moverlo.
    """
    if country not in REGIMES:
        raise KeyError(f"regimen laboral desconocido: {country}. Opciones: {sorted(REGIMES)}")
    if staffing_model not in STAFFING_MODELS:
        raise KeyError(
            f"modelo de dotacion desconocido: {staffing_model}. "
            f"Opciones: {sorted(STAFFING_MODELS)}"
        )
    r = REGIMES[country]
    dlo, dhi = STAFFING_MODELS[staffing_model]["delta"]
    lo = max(0.0, min(1.0, r.low + dlo))
    hi = max(0.0, min(1.0, r.high + dhi))
    mode = max(lo, min(hi, r.mode + (dlo + dhi) / 2))
    return (lo, mode, hi)


def apply_regime(archetype, country: str, staffing_model: str = "planta_propia"):
    """Devuelve una copia del arquetipo con `labor_flex_share` calibrado.

    Reemplaza la diferenciacion por arquetipo que traia el modelo. El estudio es
    claro: la institucion que manda es la clausula del contrato, no el rubro de
    la empresa. Un 3PL open-book en Chile puede tener mas flexibilidad de caja
    que planta propia en EE.UU.
    """
    lo, mode, hi = flex_bounds(country, staffing_model)
    return replace(
        archetype,
        labor_flex_share=mode,
        labor_flex_low=lo,
        labor_flex_high=hi,
        labor_regime=country,
        staffing_model=staffing_model,
    )


def regime_table() -> list[dict]:
    """Tabla comparable de los cuatro paises, ordenada por flexibilidad."""
    rows = [
        {
            "pais": r.name,
            "low": r.low,
            "mode": r.mode,
            "high": r.high,
            "run_rate_ref": r.run_rate_ref,
            "spread": round(r.spread, 1),
            "driver": r.driver.split(":")[0],
            "n_caveats": len(r.caveats),
        }
        for r in REGIMES.values()
    ]
    return sorted(rows, key=lambda d: -d["mode"])
