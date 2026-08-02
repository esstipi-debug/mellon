# Toolkit de terreno con hardware — diseño

**Fecha:** 2026-08-02 · **Estado:** diseño aprobado, sin implementar
**Repo:** `fde-field-kit` · **Paquetes nuevos:** `fdekit.field`, `fdekit.groundtruth`

---

## 1. Qué es y por qué

El kit diagnostica un centro de distribución a partir del log del WMS. Eso tiene
un techo que el propio código confiesa en dos lugares:

> `timestudy/spaghetti.py`: *"No hace falta seguir a un picker con una tiza: las
> tareas del WMS ya traen ubicacion y orden. Reconstruir el recorrido es
> aritmetica sobre el layout."*

> `timestudy/cycles.py::operator_variation`: *"La duracion se atribuye como el
> delta contra el evento anterior del mismo caso, que es lo unico calculable
> cuando el WMS solo registra el termino."*

Las dos frases dicen lo mismo: **el kit infiere lo que no puede medir**, y lo
dice en voz alta, que es lo correcto. Pero mientras la inferencia no tenga
contraste, el modelo no es falsable — que es exactamente el hallazgo **H1** del
crítico de completitud sobre el proyecto entero.

Este toolkit agrega dos aparatos de terreno cuyo propósito **no es producir un
análisis nuevo, sino falsificar el que ya existe**. El entregable no es un
gráfico más lindo: es un residual medido.

> El modelo dice 8 km/día de caminata. La medición dice 11,3. El 41% de
> diferencia son viajes que el WMS no registra, y ahí está el hallazgo.

### Para qué sirve fuera del repo

El objetivo declarado es presentarse como FDE con un toolkit que incluye
hardware. La diferencia con un portafolio de software no es el sensor: es poder
decir *"mi modelo tenía 41% de error y lo sé porque lo medí"*. Un candidato que
trae el residual de su propio modelo está haciendo ingeniería; uno que trae el
modelo solo, está haciendo una demo.

---

## 2. Reglas que el diseño hereda y no negocia

Las ocho del `HANDOFF.md` aplican íntegras. Las que este diseño toca directo:

- **Regla 1** — lo no cuantificado va a una cola de revisión explícita, con
  dueño y fecha. Se aplica hasta a las decisiones abiertas de este mismo spec
  (sección 11).
- **Regla 2** — capa pesada separada de capa pura. `cv2` es a este toolkit lo
  que `torch` es a `transcribe()`: vive en un extra, nunca en el núcleo. Si el
  video ya viene procesado, todo corre en el notebook prestado del CD.
- **Regla 3** — no mentir en silencio. Toda medición de terreno devuelve su
  cobertura al lado. Una comparación modelo/medición que no dice qué fracción no
  pudo ver es peor que no medir.
- **Regla 4** — `today` como argumento, nunca `date.today()` adentro.
- **Regla 8** — una sola anualización, y va en `value/levers.py`. Ningún módulo
  de este toolkit devuelve un campo `*_annual`.

### Dos reglas nuevas que este diseño agrega

**9. La identidad no cruza el borde del dispositivo.** El sensor ve al operador;
el archivo que sale del sensor, no. No es una política escrita en un PDF: es una
propiedad del código, con un test que la verifica.

**10. Ningún agregado se emite bajo el umbral de anonimato.** Análoga a la
compuerta de volumen de la fase 4 de `decide`. Bajo *k* sujetos distintos, un
"agregado por zona" es un individuo con otro nombre.

---

## 3. Arquitectura

El movimiento central: **los dos aparatos emiten al contrato que el kit ya
come.** Un `EventLog` con `(case_id, activity, timestamp, resource, location)`.
Así `travel_report`, `operator_variation` y `standard_work_gap` funcionan sobre
datos de sensor sin tocar una línea.

```
fdekit/field/
  __init__.py
  vision.py      PESADA   cv2 + ArUco -> tracks crudos. Extra `vision`.
  station.py     LIVIANA  lee el CSV/serial del ESP32. Sólo stdlib.
  tracks.py      PURA     track -> EventLog. Testeable con tracks sintéticos.
  privacy.py     PURA     compuerta de anonimato + sal de sesión.
  homography.py  PURA     píxeles -> metros del sistema de `Layout`.

fdekit/groundtruth.py   PURA   modelo vs medición, devuelve Coverage.
```

**El corte importante está entre `vision.py` y `tracks.py`.** `vision.py` toma
un video y devuelve una lista de detecciones `(marker_id, frame, x_px, y_px)`.
Todo lo demás —homografía, remuestreo, asociación a ubicaciones, emisión de
eventos, agregación, comparación contra el modelo— es Python puro sobre esa
lista. Un CSV de detecciones grabado una vez permite desarrollar y testear el
100% de la lógica sin cámara, sin `cv2` y sin video.

Es el mismo corte que ya existe entre `transcribe()` y `draft_observations()`,
y por la misma razón.

### Flujo

```
video ──vision.py──> detecciones.csv ──homography──> (t, x_m, y_m) por marcador
                                                            │
                                          tracks.py ────────┘
                                              │
                                              ├──> EventLog (medido)
                                              │
ESP32 ──> estacion.csv ──station.py──────────>┤
                                              │
log del WMS ─────────> EventLog (modelado) ───┤
                                              │
                                    groundtruth.py
                                              │
                                     residual + Coverage
```

---

## 4. Aparato A — espagueti por visión

### Hardware

| pieza | nota |
|---|---|
| cámara | teléfono viejo o webcam USB. Sin requisito de gama. |
| trípode | o abrazadera a una estructura del rack. |
| marcadores ArUco | impresos en papel, pegados al carro de picking. Costo cero. |
| 4 puntos de referencia | esquinas conocidas del piso, medidas con huincha. |

### Cómo funciona

1. La cámara mira una zona (idealmente desde altura, en diagonal).
2. Cuatro puntos del piso con coordenadas conocidas en metros dan la
   **homografía** que convierte píxeles en el mismo sistema de coordenadas que
   usa `Layout`. Ese es el punto de enchufe con lo que ya existe.
3. `vision.py` detecta marcadores cuadro a cuadro.
4. `homography.py` proyecta a metros; `tracks.py` remuestrea a intervalo fijo,
   suaviza, y asocia cada tramo a la ubicación más cercana del layout.
5. Se emiten eventos `PICK` con `location` y timestamp reales.

### Por qué marcadores y no detección de personas

Tres razones, en orden de importancia:

1. **Privacidad.** Se sigue el carro, no la cara. No hay biometría, no hay
   modelo de personas, no hay dataset de terceros. En una entrevista la objeción
   se termina en una frase.
2. **Sin modelos pesados.** ArUco es geometría, no aprendizaje. No hay `torch`,
   no hay pesos que descargar, no hay GPU.
3. **Precisión.** Un marcador da posición y orientación con error de
   centímetros; un detector de personas da una caja.

### Salida

`vision.py` devuelve **sólo detecciones crudas** — `(marker_id, frame, x_px,
y_px)` — y nada más. La cobertura, el hasheo de identidad y el paso a metros
ocurren aguas abajo, en la capa pura:

```python
# tracks.py, sobre las detecciones ya proyectadas a metros
{
  "tracks": [...],                  # (marker_hash, t, x_m, y_m)
  "coverage": Coverage(...),        # frames con marcador visible / frames totales
}
```

Mantener `vision.py` sin lógica es lo que permite testear todo lo demás contra
un CSV de detecciones grabado una vez, sin cámara y sin `cv2`.

---

## 5. Aparato B — contador de estación

### Hardware

| pieza | nota |
|---|---|
| ESP32 | MicroPython. ~US$8. |
| sensor | ToF (VL53L0X) o barrera infrarroja. Decisión diferida — sección 11. |
| alimentación | powerbank USB. Sin cablear nada del cliente. |

### Qué mide

Inicio y fin reales de una operación en una estación fija (packing, chequeo,
etiquetado). Emite `STATION_START` / `STATION_END` con timestamp.

Ataca directamente la inferencia que `operator_variation` confiesa: con B, el
delta contra el evento anterior deja de ser *lo único calculable*.

### Contrato de salida

CSV por líneas, escrito a serial o a SD:

```
ts_iso,event,sensor_id,seq
2026-09-14T10:32:11.482,START,EST-01,1041
```

`station.py` lo lee con stdlib y lo convierte a `EventLog`. Ese CSV es la
frontera: todo el análisis se desarrolla contra un archivo de ejemplo, sin
ESP32 conectado.

### Ordenamiento y reloj

El ESP32 no tiene reloj de tiempo real confiable. El firmware escribe un
contador monótono (`seq`) y un timestamp derivado de una sincronización al
arranque. `station.py` **detecta y reporta** saltos de reloj en vez de
corregirlos en silencio; un salto no reportado es un bug de la clase "no falla,
miente".

---

## 6. La capa de privacidad

`privacy.py` es una compuerta pura, del mismo espíritu que la compuerta de
volumen de la fase 4.

### Qué hace

- **Sal de sesión no persistida.** El `marker_id` o el `sensor_id` se hashea con
  una sal generada al inicio de la sesión y nunca escrita a disco. Ni el propio
  operador del kit puede revertir el mapeo mañana.
- **Umbral de anonimato.** No se emite ningún agregado que cubra menos de *k*
  sujetos distintos. Default `k = 3`.
- **Borde único.** Toda salida a disco pasa por una sola función. No hay dos
  caminos por donde algo pueda escaparse.

### Cómo se verifica

Un test recorre la salida completa y asserta que ningún campo de identidad
—`marker_id` crudo, `resource` sin hashear, `sensor_id` original— sobrevive el
borde. La privacidad deja de ser una intención y pasa a ser una propiedad
testeada.

Es también la pieza que se demuestra en una entrevista: se dice la frase, y
después se muestra el test.

### Lo que esto NO resuelve

La agregación protege al individuo dentro de una zona; no impide que un cliente
con dos operadores por zona deduzca quién es quién. El umbral *k* lo mitiga, no
lo elimina. Y no cubre la obligación de informar del artículo correspondiente de
la Ley 21.719: eso es un documento, no un test. Ver sección 11.

---

## 7. `groundtruth.py` — el hallazgo

La razón de ser del toolkit.

```python
def compare_travel(
    modeled: EventLog,      # del log del WMS
    measured: EventLog,     # de la cámara
    layout: Layout,
    today: date,            # regla 4
) -> dict
```

Devuelve el residual entre el recorrido calculado y el medido, descompuesto:

| campo | qué es |
|---|---|
| `modeled_m_in_window` | lo que dice la aritmética sobre el layout |
| `measured_m_in_window` | lo que midió la cámara |
| `residual_pct` | la diferencia, que es el hallazgo |
| `unmodeled_trips` | viajes medidos sin evento correspondiente en el WMS |
| `coverage` | `Coverage` — regla 3, siempre presente |

`coverage` reporta: fracción de pedidos con marcador visible, frames perdidos
por oclusión, y tramos descartados por baja confianza. **Un residual sin
cobertura no se publica.**

### Unidades

Todo en la ventana observada, con su denominador al lado (regla 8). Ningún campo
`*_annual`. Si esto alimenta el caso económico, la anualización ocurre en
`value/levers.py::_annualize` como todo lo demás.

---

## 8. Estrategia de test

Coherente con el resto del repo: los tests no verifican que el código corra,
verifican las propiedades que hacen que los números sean defendibles.

| capa | cómo se testea |
|---|---|
| `homography.py` | puntos sintéticos con transformación conocida; error < 5 cm |
| `tracks.py` | tracks sintéticos con recorrido conocido; la distancia reconstruida coincide con la verdad ±2% |
| `privacy.py` | ninguna identidad cruza el borde; el umbral *k* bloquea |
| `groundtruth.py` | con `measured == modeled` el residual es 0; con un desvío inyectado, lo recupera |
| `station.py` | salto de reloj detectado y reportado, no corregido en silencio |
| `vision.py` | smoke test contra un video corto versionado; marcado `@pytest.mark.vision` y excluido por defecto |

**Invariantes prioritarios**, del mismo tipo que el de anualización:

- La distancia medida no depende de la tasa de cuadros de la cámara.
- Un marcador ocluido baja la cobertura; **nunca** baja la distancia en silencio.
- Duplicar la ventana de medición no cambia las tasas por pedido.

---

## 9. Etapas y criterio de éxito

| etapa | entregable | criterio de éxito |
|---|---|---|
| **1 · mesa** | A completo: `vision`, `homography`, `tracks`, `privacy`, con tests | espagueti real en pantalla en < 2 min, sobre un escritorio, sin red |
| **2 · banco** | B: firmware ESP32 + `station.py` | tiempo de ciclo medido coincide con cronómetro ±5% |
| **3 · CD real** | A (y B si llegó) instalado unos días; `groundtruth` con datos reales | residual reportado **con cobertura**; ≥ 60% de los pedidos de la ventana con marcador visible en ≥ 80% de su recorrido, o se declara el fracaso |
| **4 · video + repo** | 3 min de video, firmware, análisis, datos versionados | un tercero lo reproduce desde el repo |

**Cada etapa sirve sola.** Si B se atasca en la etapa 2, las etapas 3 y 4 salen
igual con A. Ese es el motivo del orden: A primero, completo, antes de tocar el
ESP32.

**Alcance del plan de implementación:** este spec cubre las cuatro etapas, pero
el plan que sale de acá cubre **sólo la etapa 1**. Las etapas 2, 3 y 4 dependen
de decisiones que hoy no están tomadas (D2, D5) y de hardware que no está
comprado; planificarlas ahora sería inventar. Cada una recibe su propio plan
cuando su cola de revisión esté vacía.

El criterio de la etapa 3 está escrito para poder fallar. Si la cobertura da
40%, el entregable es *"la visión no sirve en este CD y acá está por qué"*, que
sigue siendo un resultado honesto y publicable.

---

## 10. Riesgos

| riesgo | mitigación |
|---|---|
| Dos tecnologías nuevas a la vez, sin experiencia previa en ninguna | orden estricto: A completo antes de B. El corte `vision`/`tracks` permite avanzar sin cámara. |
| Un CD real tiene mala luz, oclusión y montacargas | por eso `Coverage` no es opcional; y por eso el criterio de la etapa 3 admite fracaso |
| Ley 21.719 (1-dic-2026) | la política de retención de este canal se escribe junto con la del canal HABLADA, antes de esa fecha |
| Alcance comparable a una fase entera de `decide` | etapas independientes; ninguna depende de la siguiente |
| Tentación de rankear operadores cuando el cliente lo pida | reglas 9 y 10; presión permanente, igual que el presupuesto de 7 decisiones |

---

## 11. Decisiones abiertas — cola de revisión

Por la regla 1: lo no cuantificado no entra al análisis, va a una cola explícita
con dueño y fecha. Aplica a este spec también.

**Dueño:** único mientras el proyecto sea de una persona. La columna aparece
cuando deje de serlo. **Fechas:** expresadas como dependencia de etapa porque no
hay fecha de arranque comprometida; se convierten a fecha absoluta el día que
empieza la etapa 1, y esa conversión es parte de arrancarla.

| # | qué falta | antes de | bloquea |
|---|---|---|---|
| D1 | **Resuelta (2026-08-02).** ArUco vive en `opencv-contrib-python`, confirmado abriendo el paquete en un venv descartable (no en el del kit). La API nueva (`cv2.aruco.getPredefinedDictionary` + `cv2.aruco.DetectorParameters` + `cv2.aruco.ArucoDetector` + `detector.detectMarkers(frame)`) reemplaza a la vieja (`Dictionary_get` + `detectMarkers` de módulo) desde la serie 4.7, y se probó funcionando de punta a punta. La rueda en sí instala sin conflicto de versión de numpy en toda la serie 4.6–5.0 (el metadato no fija techo hasta la 4.12), pero eso no basta: la extensión compilada de las series 4.6.x a 4.8.x quedó enlazada contra la ABI de numpy 1.x y revienta en tiempo de ejecución contra numpy 2.4.6 (`AttributeError: _ARRAY_API not found`). Recién desde `opencv-contrib-python==4.10.0.84` la extensión es binariamente compatible con numpy 2.x — se importó, se detectó `aruco` y se corrió `detectMarkers` sobre un frame real sin error. Línea para el extra `vision` de la tarea 7: `opencv-contrib-python>=4.10.0.84`. Detalle completo, versión por versión, en `task-1-report.md`. | etapa 1 | tarea 7 (desbloqueada) |
| D2 | Sensor de B: ToF (VL53L0X) vs barrera infrarroja. Se decide en el banco con ambos, no en el papel. | etapa 2 | etapa 2 |
| D3 | Valor de *k* en la compuerta de anonimato. `k = 3` es un default sin evidencia; el número defendible depende de la dotación por zona. | etapa 3 | etapa 3 |
| D4 | ¿Existe el modo identificado detrás de bandera explícita? Quedó sin responder en el diseño. Default actual: **no existe**. | etapa 3 | regla 9 |
| D5 | Acceso a un CD real. Sin esto, el toolkit se queda en maqueta y las etapas 3 y 4 no ocurren. | etapa 3 | etapas 3 y 4 |
| D6 | Política de retención y documento de información al titular (Ley 21.719). | 1-dic-2026 | etapa 3 en producción |

---

## 12. Fuera de alcance, a propósito

- **Beacons BLE / trilateración por RSSI.** Suena a lo más "de verdad" y es una
  trampa: ruido alto, muchos nodos, calibración por sitio. Tres semanas de
  radiofrecuencia en vez de operaciones. Evaluado y descartado.
- **Detección de personas por visión.** Resuelto con marcadores, sin biometría.
- **Tiempo real / dashboard en vivo.** El kit es de diagnóstico, no de
  monitoreo. Un dashboard invita al ranking, que es lo que las reglas 9 y 10
  existen para evitar.
- **Integración al WMS del cliente.** El toolkit lee y compara; no escribe.
- **Servidor MCP.** Sigue en "no construir en el MVP", igual que en el kit.
