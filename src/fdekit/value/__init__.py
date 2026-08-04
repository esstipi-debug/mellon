"""Cuantificacion y monetizacion del trabajo del FDE.

El 95% de los pilotos de IA generativa no entrega valor medible (MIT Media Lab,
2025, sobre 300+ despliegues). La causa dominante no es tecnica: es que nadie
definio la unidad economica antes de empezar, y al mes 9 la discusion de
renovacion es opinion contra opinion.

Este modulo convierte los hallazgos del kit en un caso economico con tres
propiedades que el business case tipico de vendor no tiene:

  1. Separa **caja** de **evitacion**. Horas liberadas que no se despiden ni se
     dejan de pagar en sobretiempo no son ahorro: son capacidad. El CFO lo sabe.
  2. Castiga la **atribucion** cuando no hay contrafactual medido. Sin grupo de
     control no se puede atribuir; se puede estimar, con descuento.
  3. Entrega una **distribucion**, no un numero. p10/p50/p90 y probabilidad de
     VAN positivo.

Y detecta el humo: `ValueCase.warnings()` marca los supuestos que hacen que un
caso se caiga en la primera revision seria.
"""

from .labor_regimes import REGIMES, STAFFING_MODELS, regime_table
from .archetypes import ARCHETYPES, SCALES, Archetype, build_archetype
from .contract import CONTRACT_VERSION, FINDINGS_CONTRACT, findings_contract
from .levers import LEVER_CATALOG, Lever, Range, levers_from_findings
from .model import ValueCase, ValueResult
from .pricing import PRICING_MODELS, cost_to_serve, gainshare_terms, model_ladder, price_band

__all__ = [
    "ARCHETYPES",
    "SCALES",
    "Archetype",
    "build_archetype",
    "LEVER_CATALOG",
    "Lever",
    "Range",
    "levers_from_findings",
    "findings_contract",
    "FINDINGS_CONTRACT",
    "CONTRACT_VERSION",
    "ValueCase",
    "ValueResult",
    "PRICING_MODELS",
    "cost_to_serve",
    "gainshare_terms",
    "price_band",
    "REGIMES",
    "STAFFING_MODELS",
    "model_ladder",
    "regime_table",
]
