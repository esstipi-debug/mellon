"""Calibracion Chile 2026 — parametros economicos verificados contra fuente.

Los arquetipos de `archetypes.py` son priors razonables para LATAM, pero no
estaban validados. Este modulo los reemplaza por parametros trazables: cada
constante trae su fuente y la fecha en que se verifico.

Regla: si un numero no tiene fuente, se marca `VERIFICADO=False` y el modelo lo
dice en voz alta. Un parametro sin origen no deja de ser un supuesto por estar
escrito en Python.

Las tres correcciones que mas mueven la aguja frente a los defaults originales:

  1. La jornada legal chilena es de 42 h/semana desde el 26-abr-2026, no 45. Con
     vacaciones, feriados y ausentismo, un FTE rinde ~1.870 horas productivas al
     ano, no 2.000. El default estaba 7% alto.
  2. El costo cargado de un operario de bodega es ~USD 6,3/hora, no USD 10-14.
     El default estaba 60-120% alto — eran cifras de EE.UU./frontera, no de
     Santiago. Todas las palancas de horas caian por casi la mitad.
  3. El ingreso por pedido de un 3PL, excluyendo flete de traspaso, es ~USD 2,2,
     no USD 4,8. Incluir el flete infla el denominador y hace ver chico un
     beneficio que en realidad es grande respecto del negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .archetypes import ARCHETYPES, Archetype

VERIFICADO_AL = "2026-08-01"


@dataclass(frozen=True)
class Param:
    """Un parametro con su procedencia. `verificado=False` = sigue siendo un supuesto."""

    valor: float
    unidad: str
    fuente: str
    verificado: bool = True
    nota: str = ""


# --------------------------------------------------------------------- macro

FX_CLP_USD = Param(
    915.0,
    "CLP/USD",
    "Banco Central de Chile, dolar observado: 905,36 (12-jul-2026) y 922 (30-jun-2026); "
    "rango 2026 entre 854 y 932",
    nota="se usa el punto medio del rango observado, no el spot: el spot mueve el caso "
    "10% de un mes a otro y eso no es informacion sobre el proyecto",
)

IMM = Param(
    539_000.0,
    "CLP/mes",
    "Ley 21.751 — Ingreso Minimo Mensual vigente desde 01-ene-2026 para 18-65 anos",
    nota="sube a 553.553 desde el 01-may-2026",
)

TPM = Param(
    0.045, "anual", "Banco Central de Chile, TPM mantenida en 4,5% desde marzo 2026"
)

JORNADA_SEMANAL_H = Param(
    42.0,
    "h/semana",
    "Ley 21.561 — segunda etapa vigente desde el 26-abr-2026 (de 44 a 42 h). "
    "Llega a 40 h el 26-abr-2028",
)

# --------------------------------------------------------- estructura laboral

VACACIONES_DIAS_HABILES = Param(15.0, "dias/ano", "Codigo del Trabajo, art. 67")
FERIADOS_HABILES = Param(
    11.0,
    "dias/ano",
    "feriados legales que caen en dia habil, promedio",
    verificado=False,
    nota="depende del calendario del ano y de si el CD opera en feriado (retail y "
    "ecommerce suelen operar). Contarlos del calendario del ano en curso y cruzarlos "
    "con el reglamento interno del cliente",
)
AUSENTISMO = Param(
    0.05,
    "fraccion",
    "ausentismo tipico en logistica chilena",
    verificado=False,
    nota="rango observado 4-8%; usar el dato del cliente, sale de su planilla de asistencia",
)

GRATIFICACION_PCT = Param(0.25, "del imponible", "Codigo del Trabajo, art. 50")
GRATIFICACION_TOPE = Param(
    213_354.0, "CLP/mes", "4,75 IMM anuales / 12, con IMM = 539.000"
)

AFC_EMPLEADOR = Param(0.024, "del imponible", "Seguro de Cesantia, contrato indefinido")
MUTUAL = Param(
    0.0175,
    "del imponible",
    "Ley 16.744: cotizacion basica 0,90% + adicional por riesgo",
    verificado=False,
    nota="el adicional depende de la siniestralidad de la empresa; pedir la tasa real",
)
PREVISIONAL_PATRONAL = Param(
    0.035,
    "del imponible",
    "reforma previsional 2025, componente de cargo del empleador vigente a ago-2026 "
    "(incluye SIS)",
)

PROVISION_VACACIONES = Param(0.060, "del imponible", "15 dias habiles sobre ~250 habiles/ano")
PROVISION_INDEMNIZACION = Param(
    0.040,
    "del imponible",
    "provision efectiva con la rotacion tipica de bodega",
    verificado=False,
    nota="el teorico es 8,33% (un mes por ano); en logistica la rotacion hace que la "
    "provision efectiva sea menor. Pedir el dato historico de finiquitos",
)

# ----------------------------------------------------------------- comercial

TICKET_ECOMMERCE = Param(
    80_000.0,
    "CLP/pedido",
    "CCS — ticket promedio de compra online, primer trimestre 2026 (+2,8% vs 77.000 en 2025)",
)
TICKET_CYBERDAY = Param(
    93_000.0, "CLP/pedido", "CCS — CyberDay 2026, USD 104 por compra, 5M de transacciones"
)
TARIFA_3PL_PICKPACK = Param(
    850.0, "CLP/pedido", "Stocka.cl, tarifario publico 2026 — pick & packing"
)
TARIFA_3PL_ALMACENAJE = Param(
    26_500.0, "CLP/m3/mes", "Stocka.cl, tarifario publico 2026 — almacenamiento"
)
TARIFA_3PL_DESPACHO = Param(
    3_200.0, "CLP/pedido", "Stocka.cl, tarifario publico 2026 — despacho RM"
)

WACC_USD_GRANDE = Param(
    0.085,
    "anual",
    "derivado: Kd 7,5% pre-impuesto x (1-27%) al 40% de deuda + Ke ~12% al 60%, "
    "convertido a USD descontando el diferencial de inflacion CLP-USD",
    verificado=False,
    nota="es una derivacion, no un dato observado. Pedir el WACC que usa el cliente en "
    "su comite de inversiones: siempre tienen uno y siempre es distinto al que uno calcula",
)


# ------------------------------------------------------------------ calculos


def horas_productivas_ano(
    jornada_semanal: float | None = None, ausentismo: float | None = None
) -> dict:
    """Horas que rinde un FTE al ano bajo la ley chilena vigente.

    El default de 2.000 h del modulo generico es de EE.UU. Con 42 h/semana,
    15 dias habiles de vacaciones y ~11 feriados habiles, el numero chileno es
    ~1.870 productivas. Parece un detalle y mueve el caso 7%.
    """
    jornada = jornada_semanal if jornada_semanal is not None else JORNADA_SEMANAL_H.valor
    aus = ausentismo if ausentismo is not None else AUSENTISMO.valor

    h_dia = jornada / 5
    brutas = jornada * 52.14
    menos_vacaciones = VACACIONES_DIAS_HABILES.valor * h_dia
    menos_feriados = FERIADOS_HABILES.valor * h_dia
    contratadas = brutas - menos_vacaciones - menos_feriados

    return {
        "jornada_semanal_h": jornada,
        "horas_brutas": round(brutas),
        "descuento_vacaciones_h": round(menos_vacaciones),
        "descuento_feriados_h": round(menos_feriados),
        "horas_contratadas": round(contratadas),
        "horas_productivas": round(contratadas * (1 - aus)),
        "vs_default_2000h": round(contratadas * (1 - aus) / 2000 - 1, 3),
    }


def costo_operario_bodega(
    sueldo_base_clp: float = 560_000.0,
    bonos_clp: float = 60_000.0,
    fx: float | None = None,
    incluir_provisiones: bool = True,
) -> dict:
    """Costo empresa de un operario de bodega, construido desde la estructura legal.

    Se parte del sueldo base y se suma gratificacion legal (25% con tope), bonos,
    cargas del empleador y provisiones. Los agregadores de sueldos publican
    numeros por debajo del IMM vigente —Computrabajo e Indeed muestran $445k a
    $520k contra un minimo legal de $539k— porque mezclan periodos y jornadas
    parciales. No se usan como ancla: se usa la estructura legal.
    """
    fx = fx or FX_CLP_USD.valor

    gratificacion = min(sueldo_base_clp * GRATIFICACION_PCT.valor, GRATIFICACION_TOPE.valor)
    imponible = sueldo_base_clp + gratificacion + bonos_clp

    cargas_pct = AFC_EMPLEADOR.valor + MUTUAL.valor + PREVISIONAL_PATRONAL.valor
    cargas = imponible * cargas_pct

    prov_pct = (
        PROVISION_VACACIONES.valor + PROVISION_INDEMNIZACION.valor if incluir_provisiones else 0.0
    )
    provisiones = imponible * prov_pct

    mensual = imponible + cargas + provisiones
    horas = horas_productivas_ano()

    return {
        "sueldo_base_clp": sueldo_base_clp,
        "gratificacion_clp": round(gratificacion),
        "gratificacion_topeada": gratificacion >= GRATIFICACION_TOPE.valor,
        "bonos_clp": bonos_clp,
        "imponible_clp": round(imponible),
        "cargas_empleador_pct": round(cargas_pct, 4),
        "cargas_empleador_clp": round(cargas),
        "provisiones_pct": round(prov_pct, 4),
        "provisiones_clp": round(provisiones),
        "costo_empresa_mensual_clp": round(mensual),
        "costo_empresa_anual_clp": round(mensual * 12),
        "horas_productivas_ano": horas["horas_productivas"],
        "costo_hora_productiva_clp": round(mensual * 12 / horas["horas_productivas"]),
        "costo_hora_productiva_usd": round(
            mensual * 12 / horas["horas_productivas"] / fx, 2
        ),
        "factor_sobre_sueldo_base": round(mensual / sueldo_base_clp, 3),
    }


def ingreso_3pl_por_pedido_usd(incluir_flete: bool = False, fx: float | None = None) -> dict:
    """Ingreso de fulfillment por pedido de un 3PL chileno.

    El flete es traspaso con margen fino: incluirlo en el ingreso duplica el
    denominador y hace parecer chico un beneficio que respecto del negocio real
    es grande. Se reporta por separado y por defecto queda fuera.
    """
    fx = fx or FX_CLP_USD.valor
    pickpack = TARIFA_3PL_PICKPACK.valor
    # Asignacion de almacenaje y servicios de valor agregado por pedido. Es el
    # numero mas blando de toda la calibracion.
    almacenaje_vas = 1_150.0
    base = pickpack + almacenaje_vas
    total = base + (TARIFA_3PL_DESPACHO.valor if incluir_flete else 0.0)

    return {
        "pickpack_clp": pickpack,
        "almacenaje_y_vas_clp": almacenaje_vas,
        "flete_clp": TARIFA_3PL_DESPACHO.valor if incluir_flete else 0,
        "total_clp": round(total),
        "total_usd": round(total / fx, 2),
        "confianza": "media-baja: la asignacion de almacenaje/VAS no es publica",
    }


# --------------------------------------------------------------- arquetipos


def chilean_archetypes() -> dict[str, Archetype]:
    """Los cinco arquetipos recalibrados con parametros chilenos verificados."""
    labor = costo_operario_bodega()
    usd_h = labor["costo_hora_productiva_usd"]
    ticket_usd = TICKET_ECOMMERCE.valor / FX_CLP_USD.valor
    tres_pl_usd = ingreso_3pl_por_pedido_usd()["total_usd"]
    wacc = WACC_USD_GRANDE.valor

    horas = horas_productivas_ano()["horas_productivas"]
    comun = dict(productive_hours_year=float(horas))

    ajustes = {
        # El 3PL paga algo mas que el minimo por retener gente en turnos de noche.
        "3PL": dict(labor_usd_h=usd_h * 1.05, revenue_per_order_usd=tres_pl_usd, wacc=wacc + 0.02),
        "RETAIL_OMNI": dict(labor_usd_h=usd_h * 1.15, revenue_per_order_usd=ticket_usd, wacc=wacc),
        "ECOMMERCE": dict(labor_usd_h=usd_h, revenue_per_order_usd=ticket_usd, wacc=wacc + 0.015),
        # Manufactura paga sobre mercado y tiene dotacion menos flexible.
        "MANUFACTURA": dict(labor_usd_h=usd_h * 1.45, wacc=wacc + 0.005),
        "MAYORISTA": dict(labor_usd_h=usd_h * 1.05, wacc=wacc + 0.01),
    }

    out = {}
    for key, arch in ARCHETYPES.items():
        out[key] = replace(arch, **{**comun, **ajustes.get(key, {})})
    return out


def comparacion_defaults() -> list[dict]:
    """Default original vs Chile verificado. Lo que cambia y cuanto."""
    ch = chilean_archetypes()
    filas = []
    for key, base in ARCHETYPES.items():
        v = ch[key]
        for campo in ("labor_usd_h", "revenue_per_order_usd", "wacc"):
            a, b = getattr(base, campo), getattr(v, campo)
            if abs(a - b) > 1e-9:
                filas.append(
                    {
                        "arquetipo": key,
                        "parametro": campo,
                        "default": round(a, 2),
                        "chile_2026": round(b, 2),
                        "delta_pct": round((b / a - 1) * 100, 1) if a else None,
                    }
                )
    return filas


def parametros_sin_verificar() -> list[dict]:
    """Los que siguen siendo supuestos. Se preguntan en la semana 1, no en el mes 9."""
    todos = {
        "FERIADOS_HABILES": FERIADOS_HABILES,
        "AUSENTISMO": AUSENTISMO,
        "MUTUAL": MUTUAL,
        "PROVISION_INDEMNIZACION": PROVISION_INDEMNIZACION,
        "WACC_USD_GRANDE": WACC_USD_GRANDE,
    }
    return [
        {"parametro": k, "valor": p.valor, "unidad": p.unidad, "como_conseguirlo": p.nota}
        for k, p in todos.items()
        if not p.verificado
    ]
