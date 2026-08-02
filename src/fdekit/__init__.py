"""fde-field-kit — herramientas de terreno para Forward Deployed Engineers.

Nueve herramientas organizadas en tres bloques:

    Descubrimiento   gemba, timestudy, processmining
    Diseno           dataquality, sim, baseline
    Sostenimiento    probe, standardwork, spc

Todas operan sobre el mismo contrato de datos: un log de eventos con las
columnas (case_id, activity, timestamp, resource, location) y un maestro de
SKUs. Ese contrato es lo unico que hay que negociar con el cliente en el
kickoff — el resto del kit corre solo.
"""

__version__ = "0.1.0"

# Contrato de datos. Si el log del cliente tiene estas columnas, todo el kit
# funciona sobre el sin adaptadores.
EVENT_LOG_COLUMNS = ["case_id", "activity", "timestamp", "resource", "location"]

MASTER_COLUMNS = [
    "sku_id",
    "abc_class",
    "length_cm",
    "width_cm",
    "height_cm",
    "weight_kg",
    "home_location",
]
