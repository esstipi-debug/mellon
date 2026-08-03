"""Lexicos de la fase 2. Precision alta, recall bajo, por construccion.

El detector NO hace comprension de lenguaje abierto. Detecta formas verbales
altamente restringidas — las que un facilitador competente ya dice en voz alta
al cerrar un punto. Esa restriccion es lo que fabrica determinismo donde no hay
compilador: si la frase no esta, no hay captura, y eso es visible. Si el
detector adivinara, el error seria invisible.

    "Queda decidido: QUE. Dueno NOMBRE. Para FECHA. Porque RAZON."
    "Queda pendiente: QUE. Lo resuelve NOMBRE. Antes del FECHA."
    "Asumimos QUE. Lo verificamos antes del FECHA."
    "NOMBRE se compromete a QUE, para FECHA."

Costo del acto: seis segundos, cero clicks. Y produce un efecto que ningun
modelo produce — obliga al grupo a objetar en el momento en que objetar cuesta
treinta segundos en vez de una reunion entera.
"""

from __future__ import annotations

# Marcadores por tipo. Se comparan contra texto normalizado (sin acentos, en
# minusculas). El orden importa: se prueba de mas especifico a menos.
#
# **Bilingues por tipo** (H12). El equipo global tiene la reunion en ingles y el
# CD la tiene en espanol; un lexico monolingue captura la mitad del proyecto.
# Las formas en ingles son igual de restringidas que las castellanas y por la
# misma razon: "we agreed that" cierra un punto, "i agree with that" es una
# opinion. Ampliar el lexico es justo la operacion que puede romper la precision
# alta / recall bajo, y romperla es peor que el hueco — un falso positivo entra
# al registro con cara de decision.
MARKERS: dict[str, tuple[str, ...]] = {
    "decision": (
        "queda decidido",
        "queda decidida",
        "queda resuelto",
        "se decide que",
        "decidimos que",
        "quedamos en que",
        "it is decided",
        "it's decided",
        "we agreed that",
        "we have decided",
        "decision is",
    ),
    "question": (
        "queda pendiente",
        "queda abierto",
        "queda por definir",
        "queda por resolver",
        "lo dejamos pendiente",
        "remains open",
        "still open",
        "to be defined",
        "tbd",
    ),
    "assumption": (
        "asumimos que",
        "asumimos",
        "damos por supuesto",
        "partimos de la base de que",
        "el supuesto es que",
        "we assume that",
        "we assume",
        "the assumption is",
    ),
    # Adicion sobre las tres formas del diseno. Sin ella, el bloque 1 de la
    # agenda —compromisos vencidos, el mas usado— solo se puede alimentar a
    # mano, y eso hace imposible el objetivo de 90 segundos de revision.
    "commitment": (
        "se compromete a",
        "queda a cargo de",
        "se hace cargo de",
        "queda encargado de",
        "toma el compromiso de",
        "commits to",
        "will own",
        "takes ownership of",
    ),
}

# Pistas que designan al DUENO. Sin una de estas, un nombre suelto en la frase
# no se toma como dueno: puede ser un tercero mencionado, y convertir a un
# tercero en dueno es simultaneamente un error de datos y un problema de
# privacidad (ver hueco H14 del estudio de diseno).
#
# Van separadas por DIRECCION GRAMATICAL, y no es un detalle: "dueno Marcela"
# pone el nombre despues, "Marcela se encarga" lo pone antes. Buscar en ambas
# direcciones con una sola lista hace que en "reasignar la ruta de Fabian,
# dueno Marcela" el sistema tome a Fabian —un tercero mencionado— como dueno.
OWNER_CUES_BEFORE = (
    "dueno",
    "duena",
    "responsable",
    "lo resuelve",
    "la resuelve",
    "lo ve",
    "la ve",
    "queda con",
    "queda a cargo de",
    "a cargo de",
    "encargado de",
)
OWNER_CUES_AFTER = (
    "se encarga",
    "se compromete",
    "se hace cargo",
    "lo toma",
    "queda a cargo",
)
OWNER_CUES = OWNER_CUES_BEFORE + OWNER_CUES_AFTER

# Contextos que convierten una fecha en PLAZO.
DUE_CUES = (
    "para el",
    "para la",
    "para",
    "antes del",
    "antes de",
    "a mas tardar",
    "plazo",
    "con fecha",
    "limite",
    "vence",
)

# Contextos que convierten una fecha en FECHA DE REVISION, no en plazo.
#
# Es el analogo directo de la leccion mas cara del kit (`_RE_CADA` en
# transcribe.py): el mismo texto no puede alimentar dos campos. "Para el
# viernes" es un plazo; "lo vemos en dos semanas" es una revision. Meter la
# segunda en `due` produce compromisos con vencimiento inventado — el error que
# no falla, solo miente.
REVIEW_CUES = (
    "lo vemos",
    "lo revisamos",
    "lo miramos",
    "volvemos a ver",
    "nos juntamos",
    "lo retomamos",
    "seguimiento",
)

# Conectores que separan el enunciado de la razon.
RATIONALE_CUES = ("porque", "dado que", "ya que", "puesto que", "en razon de")

# Slots tipados: canonico -> variantes de superficie.
#
# La estructura importa. Si "reslotear" y "slotting" produjeran valores
# distintos, dos menciones del mismo proceso no se reconocerian como el mismo
# slot y la desambiguacion de fase 3 fallaria justo en los casos que tiene que
# resolver. El slot que se persiste es siempre el canonico.
#
# En fase 2 se extraen y se guardan aunque todavia no se usen: hacerlo despues,
# sobre transcriptos viejos, cuesta mucho mas.
#
# **Bilingue POR TERMINO, no por lista** (H12). En supply chain el
# code-switching es la norma: "el slotting del picking de fast movers". Las dos
# lenguas van bajo el MISMO canonico, y esa es la propiedad que importa: si
# "reslotear" y "slotting" produjeran canonicos distintos, dos menciones del
# mismo proceso no se reconocerian como el mismo slot y `_l2` fallaria justo en
# los casos que existe para resolver.
SLOT_LEXICON: dict[str, dict[str, tuple[str, ...]]] = {
    "proceso": {
        "picking": ("picking", "pickear", "preparacion de pedidos", "surtido"),
        "packing": ("packing", "empaque", "embalaje"),
        "recepcion": ("recepcion", "receiving", "inbound"),
        "despacho": ("despacho", "despachar", "shipping", "outbound"),
        "reposicion": ("reposicion", "reponer", "replenishment", "replen"),
        # La lista que se amplia en el kickoff con la jerga del cliente.
        "slotting": (
            "slotting", "reslotting", "reslotear", "reslotea",
            "reubicar", "reubicacion", "acomodo",
        ),
        "inventario": ("inventario", "conteo ciclico", "cycle count", "stock take"),
        "cross_docking": ("cross docking", "crossdocking"),
        "devoluciones": ("devoluciones", "logistica inversa", "reverse logistics"),
        "ruteo": ("ruteo", "rutear", "routing"),
    },
    # Los hitos de un despliegue. Nadie los traduce y no tenian slot: "el
    # cutover es el viernes" era una frase sin ningun asidero para el resolutor,
    # y es de las que mas se repiten en las cuatro semanas que deciden todo.
    "hito": {
        "cutover": ("cutover", "go live", "golive", "salida a produccion"),
        "piloto": ("piloto", "pilot", "prueba de concepto", "poc"),
        "arranque": ("arranque", "kickoff", "kick off"),
        "estabilizacion": ("estabilizacion", "hypercare", "hyper care"),
        "cierre": ("cierre del proyecto", "handover", "traspaso"),
    },
    "sitio": {
        "pudahuel": ("pudahuel",),
        "quilicura": ("quilicura",),
        "san_bernardo": ("san bernardo",),
        "cd": ("centro de distribucion", "cd"),
        "bodega": ("bodega",),
        "sucursal": ("sucursal",),
        "planta": ("planta",),
    },
    "sistema": {
        "wms": ("wms",), "tms": ("tms",), "erp": ("erp", "sap"),
        "rf": ("terminal rf", "rf"), "edi": ("edi",), "api": ("api",),
    },
    "metrica": {
        "tiempo_ciclo": ("tiempo de ciclo",),
        "productividad": ("lineas por hora", "productividad"),
        "fill_rate": ("fill rate", "otif"),
        "exactitud": ("exactitud", "precision de inventario"),
        "sla": ("sla",),
        "costo_linea": ("costo por linea",),
        "distancia": ("distancia", "caminata"),
    },
    "turno": {
        "manana": ("turno manana", "turno de manana"),
        "tarde": ("turno tarde", "turno de tarde"),
        "noche": ("turno noche", "turno de noche"),
        "fin_de_semana": ("fin de semana",),
    },
}

# Vocabulario para el prompt inicial de Whisper en fase 3. Se amplia con la
# jerga del cliente en el kickoff: cada CD tiene la suya y es lo primero que
# hay que anotar.
#
# Lleva los terminos en INGLES a proposito (H12): Whisper con `language="es"`
# degrada notoriamente en frases mixtas, y el prompt inicial es la contramedida
# que el modelo ya soporta. Solo sirve si ahi estan los terminos que va a tener
# que reconocer — y en un CD chileno el hito, el proceso y el sistema se dicen
# casi siempre en ingles aunque la frase sea castellana.
DECISION_VOCAB = [
    "queda decidido", "queda pendiente", "asumimos", "se compromete",
    "dueno", "plazo", "criterio", "supuesto", "compromiso",
    "SKU", "pallet", "picking", "slotting", "ola", "WMS", "SLA",
    "cutover", "go live", "fast movers", "replenishment", "cycle count",
    "cross docking", "hypercare", "backlog", "lead time", "fill rate",
    "it is decided", "we agreed that", "commits to",
]

WEEKDAYS = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Expresiones de tiempo que NO producen una fecha absoluta. Se detectan a
# proposito para poder decir por que no se resolvio, en vez de devolver un
# silencio que parece un descuido.
AMBIGUOUS_TIME = {
    "la proxima semana": "semana sin dia: preguntar que dia",
    "la otra semana": "'la otra semana' significa cosas distintas segun quien habla",
    "la semana que viene": "semana sin dia: preguntar que dia",
    "el proximo mes": "mes sin dia",
    "mas adelante": "no es una fecha",
    "pronto": "no es una fecha",
    "cuando se pueda": "no es una fecha",
    "en unos dias": "cantidad indefinida",
}
