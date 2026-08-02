"""Monetizacion: como se cobra el trabajo del FDE, y cuanto.

Cinco modelos, ordenados por cuanto riesgo toma el proveedor. El punto de este
modulo no es elegir uno: es mostrar que **el modelo de precio que podes ofrecer
depende de si mediste o no**.

Sin linea base con contrafactual (herramienta 6) solo podes vender horas. Con
ella podes vender resultado — que se paga entre 3 y 6 veces mas por el mismo
trabajo. Esa es, en una frase, la razon economica de existir del kit.

Critica que hay que tener presente al vender esto: Charlie Gottdiener (CEO de
Anaplan) sobre el modelo FDE — "es un buen modelo para vender, no es un gran
modelo para operar el software". Tiene razon cuando el FDE no deja trabajo
estandar ni runbook. Las herramientas 8 y 9 existen exactamente para poder
responder esa objecion con evidencia y no con promesas.
"""

from __future__ import annotations

import numpy as np

from .model import ValueResult

PRICING_MODELS = {
    "tiempo_materiales": {
        "riesgo_proveedor": "bajo",
        "requiere_medicion": False,
        "captura_tipica_pct": (0.0, 0.0),
        "cuando": "alcance incierto, cliente nuevo, primer proyecto. Es donde empieza todo.",
        "riesgo": "el cliente compra dias, no resultados: la renovacion depende de la simpatia.",
    },
    "precio_fijo": {
        "riesgo_proveedor": "medio",
        "requiere_medicion": False,
        "captura_tipica_pct": (0.0, 0.0),
        "cuando": "alcance cerrado y conocido; despliegues repetidos del mismo patron.",
        "riesgo": "todo el riesgo de estimacion es tuyo. Sin herramienta 3 estas adivinando.",
    },
    "suscripcion": {
        "riesgo_proveedor": "medio",
        "requiere_medicion": False,
        "captura_tipica_pct": (0.08, 0.15),
        "cuando": "el producto queda corriendo y hay que sostenerlo.",
        "riesgo": "churn silencioso: el sistema sigue prendido y dejo de mover la aguja. "
        "La herramienta 9 es lo que lo detecta antes de la no-renovacion.",
    },
    "hitos_por_resultado": {
        "riesgo_proveedor": "alto",
        "requiere_medicion": True,
        "captura_tipica_pct": (0.10, 0.20),
        "cuando": "hay linea base firmada y metrica acordada antes del go-live.",
        "riesgo": "si la metrica esta mal definida, la discusion del hito es un juicio.",
    },
    "gainshare": {
        "riesgo_proveedor": "muy alto",
        "requiere_medicion": True,
        "captura_tipica_pct": (0.15, 0.30),
        "cuando": "linea base con grupo de control, metrica auditable, y confianza de dos anos.",
        "riesgo": "sin contrafactual el cliente atribuye toda la mejora a la estacionalidad "
        "y no paga. Es literalmente imposible de cobrar sin la herramienta 6.",
    },
}


def cost_to_serve(
    fde_days: float,
    day_rate_usd: float = 900.0,
    travel_trips: int = 0,
    trip_cost_usd: float = 1_400.0,
    tooling_usd: float = 0.0,
    overhead_pct: float = 0.22,
) -> dict:
    """Costo de servir el proyecto. Es el piso absoluto del precio.

    `day_rate_usd` es costo, no tarifa: incluir el costo cargado del FDE, no lo
    que se le factura al cliente. Confundir los dos es como se llega a proyectos
    que facturan bien y pierden plata.
    """
    labor = fde_days * day_rate_usd
    travel = travel_trips * trip_cost_usd
    direct = labor + travel + tooling_usd
    return {
        "dias_fde": fde_days,
        "costo_trabajo_usd": round(labor),
        "costo_viajes_usd": round(travel),
        "herramientas_usd": round(tooling_usd),
        "overhead_usd": round(direct * overhead_pct),
        "costo_total_usd": round(direct * (1 + overhead_pct)),
    }


def price_band(
    result: ValueResult,
    model: str = "gainshare",
    has_control_group: bool = False,
    min_margin_pct: float = 0.35,
) -> dict:
    """Banda de precio defendible para el modelo elegido.

    Se ancla en el beneficio de **caja p50** — nunca en el total, y nunca en el
    p90. Cobrar contra el p90 es cobrar contra el mejor escenario del cliente y
    es como se pierde una cuenta en la primera revision trimestral.
    """
    if model not in PRICING_MODELS:
        raise KeyError(f"modelo desconocido: {model}. Opciones: {sorted(PRICING_MODELS)}")

    spec = PRICING_MODELS[model]
    if spec["requiere_medicion"] and not has_control_group:
        return {
            "modelo": model,
            "viable": False,
            "motivo": (
                "este modelo requiere linea base con contrafactual medido. Sin grupo de "
                "control el cliente puede atribuir la mejora a la estacionalidad, y tiene "
                "razon. Vender tiempo_materiales o precio_fijo hasta tener la medicion."
            ),
            "alternativa": "tiempo_materiales",
        }

    cash_p50 = float(np.percentile(result.annual_cash_usd, 50))
    cash_p10 = float(np.percentile(result.annual_cash_usd, 10))
    lo_pct, hi_pct = spec["captura_tipica_pct"]

    floor = result.cost_total_usd / max(1 - min_margin_pct, 0.05)

    # Si el piso por margen supera la captura maxima tipica, el proyecto no
    # soporta este modelo a esta escala. Emitir igual una "banda" degenerada
    # —piso = techo, capturando el 90% del beneficio del cliente— es como se
    # firma un contrato que se cae en la primera revision trimestral.
    if hi_pct > 0 and floor > cash_p50 * hi_pct:
        return {
            "modelo": model,
            "viable": False,
            "motivo": (
                f"el piso por margen (USD {floor:,.0f}) supera la captura maxima tipica de "
                f"este modelo ({hi_pct:.0%} de USD {cash_p50:,.0f} = USD {cash_p50*hi_pct:,.0f}). "
                "El costo de servir es demasiado alto para el beneficio que genera."
            ),
            "salidas": [
                "reducir alcance (menos dias de FDE) hasta que el piso entre en la banda",
                "subir la escala: mas sitios amortizan el mismo descubrimiento",
                "ampliar palancas: si solo mediste horas, falta capital de trabajo y servicio",
                "cobrar tiempo_materiales y volver a evaluar con la linea base ya medida",
            ],
            "captura_requerida_pct": round(floor / cash_p50 * 100, 1) if cash_p50 else None,
            "alternativa": "tiempo_materiales",
        }

    band_low = max(floor, cash_p50 * lo_pct)
    band_high = max(band_low, cash_p50 * hi_pct)

    return {
        "modelo": model,
        "viable": True,
        "riesgo_proveedor": spec["riesgo_proveedor"],
        "beneficio_caja_p50_usd": round(cash_p50),
        "costo_de_servir_usd": round(result.cost_total_usd),
        "piso_por_margen_usd": round(floor),
        "banda_precio_anual_usd": (round(band_low), round(band_high)),
        "captura_de_valor_pct": (
            round(band_low / cash_p50 * 100, 1) if cash_p50 else None,
            round(band_high / cash_p50 * 100, 1) if cash_p50 else None,
        ),
        # Si el precio supera el p10 del beneficio, hay un escenario realista en
        # que el cliente paga mas de lo que gana. Ahi es donde nacen las
        # renovaciones perdidas.
        "riesgo_de_sobreprecio": band_high > cash_p10,
        "cuando_usar": spec["cuando"],
        "riesgo_del_modelo": spec["riesgo"],
    }


def gainshare_terms(
    result: ValueResult,
    share_pct: float = 0.20,
    cap_multiple: float = 2.5,
    floor_usd: float | None = None,
    verification: str = "diferencias-en-diferencias contra zona de control, auditado trimestral",
) -> dict:
    """Terminos de un contrato de gainshare, con las clausulas que evitan el
    juicio.

    Las tres que nunca hay que omitir:
      - **piso**: cubre el costo de servir aunque el beneficio sea cero. Sin
        piso, un peak mal medido te deja trabajando gratis un ano.
      - **techo**: protege al cliente de pagar un multiplo absurdo si el
        beneficio explota por razones ajenas. Sin techo, no firman.
      - **verificacion**: el metodo exacto, escrito. Si dice "de comun acuerdo",
        el acuerdo se rompe el primer trimestre malo.
    """
    cash_p10 = float(np.percentile(result.annual_cash_usd, 10))
    cash_p50 = float(np.percentile(result.annual_cash_usd, 50))
    cash_p90 = float(np.percentile(result.annual_cash_usd, 90))
    floor = floor_usd if floor_usd is not None else result.cost_total_usd * 0.6
    cap = max(floor, cash_p50 * share_pct * cap_multiple)

    # Un solo techo, el mismo que se reporta. Tener dos —uno para calcular y
    # otro para mostrar— es como se llega a una clausula que nadie puede
    # liquidar sin discutir.
    def pay(benefit: float) -> float:
        return float(np.clip(benefit * share_pct, floor, cap))

    p10, p50, p90 = pay(cash_p10), pay(cash_p50), pay(cash_p90)
    # Si los tres escenarios pagan igual, el contrato dice gainshare y se
    # comporta como precio fijo. El cliente lo va a notar, mejor decirlo primero.
    degenerado = abs(p90 - p10) < max(floor * 0.02, 1.0)

    return {
        "share_pct": share_pct,
        "share_pct_minimo_para_cubrir_costo": (
            round(result.cost_total_usd / cash_p50, 3) if cash_p50 else None
        ),
        "piso_anual_usd": round(floor),
        "techo_anual_usd": round(cap),
        "metodo_de_verificacion": verification,
        "pago_escenario_p10_usd": round(p10),
        "pago_escenario_p50_usd": round(p50),
        "pago_escenario_p90_usd": round(p90),
        "es_precio_fijo_disfrazado": bool(degenerado),
        "advertencia": (
            "el piso domina los tres escenarios: esto es un precio fijo con otro nombre. "
            "O baja el piso, o sube el share, o vende precio_fijo y se acabo."
            if degenerado
            else ""
        ),
        "cobertura_de_costo_en_p10": round(p10 / max(result.cost_total_usd, 1), 2),
        "clausulas_obligatorias": [
            "Metrica, formula y fuente de datos definidas y congeladas antes del go-live.",
            "Grupo de control o ventana contrafactual explicita en el contrato.",
            "Reglas de exclusion por eventos extraordinarios (peak, huelga, cambio de layout).",
            "Derecho de auditoria del cliente sobre el calculo, con datos reproducibles.",
            "Que pasa si el cliente no implementa las contramedidas acordadas.",
        ],
    }


def model_ladder(has_control_group: bool, months_of_relationship: int) -> str:
    """Que modelo corresponde hoy. La escalera se sube, no se salta."""
    if not has_control_group:
        return "tiempo_materiales" if months_of_relationship < 6 else "precio_fijo"
    if months_of_relationship < 12:
        return "hitos_por_resultado"
    return "gainshare"
