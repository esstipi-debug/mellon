"""Arquetipos de empresa y escalas.

Cinco arquetipos porque el mismo hallazgo vale plata distinta segun quien lo
reciba. Una hora de picking recuperada en un 3PL es margen directo — le facturan
al cliente por unidad procesada. La misma hora en un retailer omnicanal es
capacidad que quizas ni se usa. Cobrar lo mismo por las dos es como no entender
a quien le estas vendiendo.

Los numeros son defaults defendibles para LATAM 2026, no verdades. Se reemplazan
con los del cliente en la primera semana; el punto del modulo es que la
estructura no cambie cuando cambien los numeros.

    labor_flex_share es la variable que decide todo. Es la fraccion de horas
    liberadas que se convierte en caja (sobretiempo que se deja de pagar,
    temporales que no se contratan). El resto es capacidad ociosa. En un CD
    estable con dotacion fija esa fraccion es 0.2-0.3, no 1.0, y el business
    case que asume 1.0 es exactamente el que el CFO rechaza.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


# Lineas procesadas por hora de FTE directo. Un picker mueve 60-80 lineas/hora
# incluyendo caminata; el resto de la dotacion directa (packing, recepcion,
# reposicion, control) suma ~2.5x la dotacion de picking, asi que la tasa
# efectiva por hora de dotacion directa baja a ~17,5.
#
# Se expresa por HORA y no por ano a proposito: las horas que rinde un FTE
# dependen de la ley laboral del pais (Chile va en 42 h/semana desde abril 2026,
# camino a 40 en 2028). Hardcodear 2.000 h/ano es importar un supuesto de EE.UU.
LINES_PER_DIRECT_HOUR = 17.5
DEFAULT_PRODUCTIVE_HOURS_YEAR = 2_000.0


@dataclass(frozen=True)
class Archetype:
    key: str
    name: str

    # Operacion
    orders_per_day: float
    lines_per_order: float
    operating_days: int = 300

    # Trabajo
    labor_usd_h: float = 11.0  # costo cargado, LATAM
    # Cuanto de la hora liberada es caja. Es la variable mas importante del
    # modelo y la que mas depende del pais: la fraccion es una consecuencia
    # directa del regimen laboral (casuales, agencias, costo de despido,
    # rotacion). `low`/`high` quedan opcionales; si no se dan se asume +-40%
    # relativo, que es un rango generoso a proposito para un dato sin fuente.
    labor_flex_share: float = 0.25
    labor_flex_low: float | None = None
    labor_flex_high: float | None = None
    # Procedencia de esos tres numeros. Sin esto no hay forma de saber si el
    # flex viene de un estudio o de un prior sin validar, y esa diferencia es
    # justamente la que decide si el caso se puede defender.
    labor_regime: str = "sin_calibrar"
    staffing_model: str = "planta_propia"
    overtime_premium: float = 1.5
    productive_hours_year: float = DEFAULT_PRODUCTIVE_HOURS_YEAR
    lines_per_direct_hour: float = LINES_PER_DIRECT_HOUR

    # Comercial
    revenue_per_order_usd: float = 60.0
    gross_margin_pct: float = 0.28
    late_order_cost_usd: float = 4.0  # penalidad SLA o costo de recuperacion
    stockout_margin_loss_usd: float = 18.0  # margen perdido por venta caida

    # Capital
    inventory_value_usd: float = 4_000_000.0
    carrying_cost_pct: float = 0.22
    capex_per_station_usd: float = 45_000.0  # estacion/robot/dotacion adicional
    wacc: float = 0.14  # costo de capital LATAM

    # Cuanto duele un incidente de integracion en produccion
    incident_cost_usd: float = 6_500.0

    @property
    def annual_orders(self) -> float:
        return self.orders_per_day * self.operating_days

    @property
    def annual_lines(self) -> float:
        return self.annual_orders * self.lines_per_order

    @property
    def annual_revenue_usd(self) -> float:
        return self.annual_orders * self.revenue_per_order_usd

    @property
    def direct_hours_year(self) -> float:
        """Horas de dotacion directa necesarias al ano. No depende de la ley
        laboral: el trabajo a hacer es el mismo, cambia entre cuantas personas
        se reparte."""
        return self.annual_lines / self.lines_per_direct_hour

    @property
    def direct_ftes(self) -> float:
        return self.direct_hours_year / self.productive_hours_year

    @property
    def annual_labor_cost_usd(self) -> float:
        """Base de costo laboral directo.

        Es el denominador correcto para un 3PL, cuyo 'ingreso' es una tarifa por
        pedido y no una venta. Medir un ahorro operacional contra el ingreso de
        un operador logistico da porcentajes absurdos y hunde el caso por un
        error de denominador, no de fondo.
        """
        # NO depende de las horas por FTE: reducir la jornada legal cambia
        # cuanta gente hace falta, no cuanto trabajo hay.
        return self.direct_hours_year * self.labor_usd_h

    def cash_labor_usd_h(self) -> float:
        """Valor de caja de una hora liberada. No es el costo cargado completo."""
        return self.labor_usd_h * self.overtime_premium * self.labor_flex_share

    def labor_flex_bounds(self) -> tuple[float, float, float]:
        """(low, mode, high) de `labor_flex_share`, acotado a [0, 1]."""
        lo = self.labor_flex_low if self.labor_flex_low is not None else self.labor_flex_share * 0.6
        hi = self.labor_flex_high if self.labor_flex_high is not None else self.labor_flex_share * 1.4
        return (max(0.0, lo), self.labor_flex_share, min(1.0, hi))

    def cash_labor_bounds(self) -> tuple[float, float, float]:
        """Fraccion del costo de una hora liberada que llega al resultado.

        NO multiplica por `overtime_premium`, y eso es una correccion, no un
        olvido. `labor_flex_share` esta calibrado **en horas**: es la fraccion de
        las horas liberadas que se apaga. El recargo de sobretiempo aplica solo
        a las horas que efectivamente eran extra, que son una porcion de esa
        fraccion — no a todas. Multiplicar la fraccion completa por 1,5x aplicaba
        el recargo tambien a las horas normales de eventuales y a las de
        permanentes que salen por atricion, donde no hay recargo que ahorrar.

        Efecto de la correccion: baja el beneficio de las palancas de horas ~33%
        y saca del modelo un `cash_share` que llegaba a toparse en 1,0 — o sea,
        una hora liberada valiendo mas que una hora trabajada.

        `overtime_premium` se conserva en el arquetipo porque lo usa
        `cash_labor_usd_h()` para la conversacion de servilleta, donde el
        interlocutor esta pensando en horas extra concretas.
        """
        return self.labor_flex_bounds()


ARCHETYPES: dict[str, Archetype] = {
    # Margen fino, cobra por unidad procesada: cada hora liberada es margen
    # directo y la fraccion flexible es alta (dotacion mayormente temporal).
    "3PL": Archetype(
        key="3PL",
        name="Operador logistico (3PL)",
        orders_per_day=4_200,
        lines_per_order=3.1,
        labor_usd_h=10.0,
        labor_flex_share=0.55,
        revenue_per_order_usd=4.8,  # tarifa por pedido, no venta
        gross_margin_pct=0.07,
        late_order_cost_usd=9.0,  # SLA con penalidad contractual real
        stockout_margin_loss_usd=0.0,  # el stock no es suyo
        inventory_value_usd=0.0,
        capex_per_station_usd=38_000.0,
        incident_cost_usd=11_000.0,
    ),
    # El valor no esta en la hora: esta en el pedido que no se despacho.
    "RETAIL_OMNI": Archetype(
        key="RETAIL_OMNI",
        name="Retailer omnicanal",
        orders_per_day=9_500,
        lines_per_order=2.4,
        labor_usd_h=12.0,
        labor_flex_share=0.25,
        revenue_per_order_usd=72.0,
        gross_margin_pct=0.31,
        late_order_cost_usd=6.5,
        stockout_margin_loss_usd=22.0,
        inventory_value_usd=48_000_000.0,
        carrying_cost_pct=0.24,
        capex_per_station_usd=55_000.0,
        incident_cost_usd=25_000.0,
    ),
    # Aca la unidad no es el pedido: es el minuto de linea detenida.
    "MANUFACTURA": Archetype(
        key="MANUFACTURA",
        name="Manufactura con CD de insumos",
        orders_per_day=850,
        lines_per_order=6.8,
        labor_usd_h=14.0,
        labor_flex_share=0.15,  # dotacion sindicalizada, poco flexible
        revenue_per_order_usd=1_400.0,
        gross_margin_pct=0.22,
        late_order_cost_usd=210.0,  # quiebre de insumo = paro de linea
        stockout_margin_loss_usd=900.0,
        inventory_value_usd=22_000_000.0,
        carrying_cost_pct=0.19,
        capex_per_station_usd=120_000.0,
        incident_cost_usd=40_000.0,
    ),
    # Volumen alto, margen por pedido chico, devolucion cara.
    "ECOMMERCE": Archetype(
        key="ECOMMERCE",
        name="E-commerce puro",
        orders_per_day=14_000,
        lines_per_order=1.7,
        labor_usd_h=11.0,
        labor_flex_share=0.60,  # picking mayormente temporal
        revenue_per_order_usd=41.0,
        gross_margin_pct=0.26,
        late_order_cost_usd=7.5,
        stockout_margin_loss_usd=11.0,
        inventory_value_usd=15_000_000.0,
        carrying_cost_pct=0.26,
        capex_per_station_usd=42_000.0,
        incident_cost_usd=18_000.0,
    ),
    # El valor dominante es capital de trabajo, no horas.
    "MAYORISTA": Archetype(
        key="MAYORISTA",
        name="Distribuidor mayorista",
        orders_per_day=1_900,
        lines_per_order=11.5,
        labor_usd_h=10.5,
        labor_flex_share=0.30,
        revenue_per_order_usd=980.0,
        gross_margin_pct=0.14,
        late_order_cost_usd=28.0,
        stockout_margin_loss_usd=140.0,
        inventory_value_usd=65_000_000.0,
        carrying_cost_pct=0.21,
        capex_per_station_usd=50_000.0,
        incident_cost_usd=22_000.0,
    ),
}


# Multiplicadores de volumen. El arquetipo define la economia unitaria; la
# escala define cuantas unidades. Separarlos evita el error de asumir que un
# 3PL grande se comporta como cinco 3PL chicos.
SCALES: dict[str, dict] = {
    "pyme": {"volume": 0.10, "sites": 1, "wacc_adj": +0.04},
    "media": {"volume": 0.35, "sites": 1, "wacc_adj": +0.01},
    "grande": {"volume": 1.00, "sites": 3, "wacc_adj": 0.0},
    "enterprise": {"volume": 3.20, "sites": 11, "wacc_adj": -0.02},
}


def build_archetype(
    key: str,
    scale: str = "grande",
    calibration: str = "generico",
    labor_regime: str | None = None,
    staffing_model: str = "planta_propia",
    **overrides,
) -> Archetype:
    """Arquetipo escalado.

    `calibration="chile"` reemplaza los parametros economicos por los
    verificados contra fuente en `chile.py`. El default `"generico"` son priors
    de LATAM **sin validar** — sirven para probar el modelo, no para cotizar.

    `labor_regime` y `calibration` son ejes distintos a proposito. El regimen
    laboral esta verificado para cuatro paises (`usa`, `australia`, `chile`,
    `argentina`); la calibracion economica completa —costo cargado, tipo de
    cambio, ticket, tarifas— solo existe para Chile. Fusionarlos daria a
    entender que hay datos de costo verificados para los otros tres, y no los hay.

    `staffing_model` es el ajuste mas grande y el peor documentado del estudio,
    y es JUICIO, no medicion. Tambien es la primera pregunta que hay que hacer:
    pedir el contrato antes que cualquier estadistica.
    """
    if key not in ARCHETYPES:
        raise KeyError(f"arquetipo desconocido: {key}. Opciones: {sorted(ARCHETYPES)}")
    if scale not in SCALES:
        raise KeyError(f"escala desconocida: {scale}. Opciones: {sorted(SCALES)}")

    if calibration == "chile":
        from .chile import chilean_archetypes

        base = chilean_archetypes()[key]
    elif calibration == "generico":
        base = ARCHETYPES[key]
    else:
        raise KeyError(f"calibracion desconocida: {calibration}. Opciones: chile, generico")
    # Si se calibra a Chile y no se pide otro regimen, se usa el chileno: sería
    # raro cotizar con costos chilenos y flexibilidad laboral de otro pais.
    if labor_regime is None and calibration == "chile":
        labor_regime = "chile"
    if labor_regime is not None:
        from .labor_regimes import apply_regime

        base = apply_regime(base, labor_regime, staffing_model)

    s = SCALES[scale]
    scaled = replace(
        base,
        orders_per_day=base.orders_per_day * s["volume"],
        inventory_value_usd=base.inventory_value_usd * s["volume"],
        wacc=max(0.05, base.wacc + s["wacc_adj"]),
    )
    return replace(scaled, **overrides) if overrides else scaled
