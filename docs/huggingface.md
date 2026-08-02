# Modelos y datasets de Hugging Face para el kit

Barrido del 1 de agosto de 2026, consultando la API de HF directamente
(`huggingface.co/api/models` y `/api/datasets`). Las cifras de descargas son
las devueltas por la API ese día, no de memoria.

Ninguno está integrado al paquete todavía — esta es la carpeta de candidatos.
Todos requieren `torch`, que deliberadamente **no** es dependencia de
`fde-field-kit`: el kit tiene que correr en el notebook prestado de un CD sin
GPU y sin permisos de instalación.

---

## Lo que sí sirve, por herramienta del kit

### Herramienta 1 — gemba → transcripción de entrevistas

| Modelo | Descargas | Para qué |
|---|---|---|
| `openai/whisper-large-v3-turbo` | 8.5M | transcripción multilingüe, ~8x más rápido que large-v3 |
| `openai/whisper-large-v3` | 5.6M | mejor calidad, más lento |
| `distil-whisper/distil-large-v3` | 1.6M | inglés, la mitad del peso |

**Este es el de mayor impacto real.** El cuello de la herramienta 1 no es
analizar observaciones: es capturarlas. En el pasillo no se escribe — se
escucha. Grabar 20 minutos por turno, transcribir localmente (Whisper corre
offline, requisito no negociable en un CD sin wifi) y extraer los campos de
`Observation` deja 15 observaciones estructuradas donde antes había tres
garabatos.

Chile/LATAM: `large-v3-turbo` maneja español rioplatense y chileno
razonablemente; el vocabulario de bodega (SKU, pallet, picking, ola, hueco)
necesita corrección posterior o un prompt inicial con los términos.

Caveat: transcribir a un operador es grabar a una persona. Consentimiento
explícito y anonimización antes de que el audio salga del sitio. No es un
detalle legal — es lo que decide si te vuelven a hablar en el segundo turno.

### Herramienta 4 — datos maestros

| Modelo | Descargas | Para qué |
|---|---|---|
| `intfloat/multilingual-e5-small` | 15.4M | embeddings multilingües, 118M params, corre en CPU |
| `intfloat/multilingual-e5-large` | 7.6M | misma familia, mejor calidad |

El kit hoy audita **dimensiones y ubicación**. El defecto que no cubre es el
**duplicado semántico**: `TORNILLO HEX 1/2 X 3` y `TORN HEXAG 12.7MM 76MM` son
el mismo SKU con dos códigos, comprado dos veces y contado dos veces. Es el
hallazgo que más plata devuelve en una auditoría de maestros y no se detecta
con `difflib` — los códigos no se parecen, los significados sí.

Embeddings + umbral de coseno + revisión humana de los pares candidatos. Corre
en CPU sobre 50k SKUs en minutos.

### Herramienta 5 — simulación

| Modelo | Descargas | Para qué |
|---|---|---|
| `amazon/chronos-2` | 25.7M | pronóstico de series de tiempo zero-shot |
| `autogluon/chronos-bolt-small` | 13.2M | variante rápida, CPU-friendly |

Hoy `SimConfig.arrival_rate_per_h` se calibra con la tasa histórica. Chronos
permite alimentar el simulador con la **demanda pronosticada** en vez de la
pasada, y responder "¿cuántos pickers necesito el 24 de diciembre?" en vez de
"¿cuántos necesitaba en marzo?".

Zero-shot: no hay que entrenar nada. Eso importa cuando el cliente te da 18
meses de historia y tres semanas de proyecto.

Caveat honesto: en horizontes cortos y series con calendario fuerte (peak,
promociones, día de pago), un modelo estadístico simple con regresores de
calendario suele empatarle o ganarle. Chronos gana cuando hay muchas series
(SKU por tienda) y ninguna merece atención individual.

### Herramienta 7 — sonda de integración / documentos

| Modelo | Descargas | Para qué |
|---|---|---|
| `docling-project/docling-models` | 2.8M | layout + estructura de documentos |
| `ibm-granite/granite-docling-258M` | 446k | doc → markdown estructurado, 258M params |
| `microsoft/table-transformer-structure-recognition` | 1.5M | extracción de tablas |
| `microsoft/table-transformer-detection` | 1.2M | detección de tablas en la página |

Para el proveedor que no tiene EDI y manda la guía de despacho en PDF —
que en LATAM es la mayoría. `granite-docling-258M` es chico de verdad: cabe en
un notebook sin GPU.

### Sub-área de robótica y visión de bodega

| Dataset | Descargas | Qué es |
|---|---|---|
| `nvidia/PhysicalAI-Spatial-Intelligence-Warehouse` | 3.6k | 95k pares RGB-D sintéticos de bodega + 499k QA de razonamiento espacial (distancias, conteo, relaciones). Omniverse. CC-BY-4.0 |
| `Voxel51/lidar-warehouse-dataset` | 6.8k | 3.287 escaneos LiDAR reales (Velodyne VLP-16), 6.381 cajas anotadas en 5 clases: Box, ELFplusplus, CargoBike, FTS, ForkLift. 3.4 GB. CC-BY-SA-4.0 |
| `nvidia/PhysicalAI-SimReady-Warehouse-01` | 6.0k | escenas de bodega listas para simulación |
| `nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes` | 30.5k | escenas sintéticas de operación de bodega |

| Modelo | Descargas | Para qué |
|---|---|---|
| `PekingU/rtdetr_r101vd_coco_o365` | 386k | detección de objetos en tiempo real |
| `PekingU/rtdetr_v2_r18vd` | 272k | versión liviana |

El dataset LiDAR de Voxel51 es **real, no sintético**, tiene licencia abierta y
sus cinco clases son exactamente el vocabulario de un CD. Es la base más limpia
que existe públicamente para un demo de conteo de inventario o detección de
grúas horquilla.

---

## Lo que Hugging Face NO tiene

Vale la pena decirlo porque ahorra medio día de búsqueda:

**Logs de eventos para process mining.** No están en HF. Están en
[4TU.ResearchData](https://data.4tu.nl) — los BPI Challenge (2012, 2017, 2019)
son el estándar de facto, con licencia abierta. El BPI 2019 es de
**purchase-to-pay** y es el único log público grande de un proceso de compras
real. Es el dataset que hay que usar para validar la herramienta 3 contra algo
que no salga del generador propio.

**Datos operativos de supply chain.** Los diez datasets que devuelve HF al
buscar "supply chain" tienen entre 50 y 600 descargas y son ejercicios de
Kaggle re-subidos. No hay nada de calidad. Es coherente con la realidad del
sector: esta data no se publica.

---

## Si hubiera que integrar uno solo

**Whisper para la herramienta 1.** Es el único que ataca un cuello real del
kit (capturar el gemba, no analizarlo), corre offline en CPU, no necesita
entrenamiento y su salida cae directo en el esquema `Observation` que ya
existe. Los demás son mejoras; este cambia lo que se puede hacer en un turno.

Extras propuestos para `pyproject.toml`, sin tocar el núcleo:

```toml
[project.optional-dependencies]
audio    = ["transformers>=4.44", "torch>=2.2", "librosa"]
docs     = ["docling"]
forecast = ["chronos-forecasting"]
embed    = ["sentence-transformers"]
```
