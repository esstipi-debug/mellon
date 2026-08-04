# Mytra FDE

Kit de terreno para **Forward Deployed Engineers con perfil de supply chain**.

> **Para retomar el trabajo: [`docs/HANDOFF.md`](docs/HANDOFF.md).** Estado,
> montaje, las 9 reglas duras que no se rompen, y qué sigue.
>
> El paquete Python se llama `fdekit` y el directorio local `fde-field-kit`;
> Mytra FDE es el nombre del proyecto. No se renombró el paquete porque el
> import aparece en más de mil tests y en cada docstring, y un renombre masivo
> es exactamente el tipo de cambio que este repo trata de evitar: mucho diff,
> cero comportamiento nuevo.

Nueve herramientas que llevan un despliegue del log crudo del WMS a un A3 con
números, en un comando. Incluye un centro de distribución sintético con defectos
realistas ya encadenados, para poder mostrar el kit sin datos de un cliente.

La tesis: casi todo FDE instrumenta el software. Este kit instrumenta la
**operación** — que es lo que decide si el despliegue sobrevive al mes 3.

```bash
pip install -e .
fdekit demo --out out
```

5 segundos después, en `out/`: log de eventos, diagrama de espagueti, mapa de
calor, gráfico XmR, auditoría de maestros, barrido de dimensionamiento, spec de
línea base, hojas TWI, runbook y el A3 armado con los hallazgos.

---

## Las nueve herramientas

| # | Módulo | Qué hace | Cuándo se usa |
|---|---|---|---|
| 1 | `fdekit.gemba` | Observación estructurada offline → Pareto de desperdicio cuantificado. Incluye `transcribe`: audio del pasillo → borradores de observación | días 0-14 |
| 2 | `fdekit.timestudy` | Tiempos de ciclo, variación entre operadores, espagueti y mapa de calor desde el log del WMS | días 0-14 |
| 3 | `fdekit.processmining` | DFG, variantes, conformidad contra el flujo declarado, cuellos por tiempo total perdido | días 15-30 |
| 4 | `fdekit.dataquality` | Plan de muestreo, auditoría física de maestros, y el vínculo estadístico con el reproceso observado | días 0-14 |
| 5 | `fdekit.sim` | DES calibrado desde el log + Ley de Little + Erlang C | días 15-30 |
| 6 | `fdekit.baseline` | Spec firmable, MDE, tamaño de muestra con ICC, pre/post y diferencias-en-diferencias | días 30-45 |
| 7 | `fdekit.probe` | Validador X12 (940/945/214/856), contratos de API, auditoría de husos horarios, idempotencia | días 45+ |
| 8 | `fdekit.standardwork` | Hojas TWI Job Instruction y runbook de traspaso | días 45-75 |
| 9 | `fdekit.spc` | XmR con reglas de Nelson y monitor de degradación con límites congelados | días 75+ |

Más `fdekit.a3`, que arma el A3 con los hallazgos ya insertados, y
`fdekit.value`, que convierte los hallazgos en un caso económico con
distribución y en un modelo de precio defendible
([docs/mercado-y-monetizacion.md](docs/mercado-y-monetizacion.md)).

```bash
fdekit value --findings out/hallazgos.json --archetype todos --scale grande --sites 3 --control
```

Cinco arquetipos de empresa, seis palancas de valor trazadas a la herramienta
que las mide, Monte Carlo sobre atribución y realización, y una escalera de
precio que **se niega** a cotizar gainshare sin contrafactual medido. Ese "no"
es la función más valiosa del módulo.

`labor_flex_share` —la variable más importante del modelo— está calibrada para
**cuatro países** con investigación adversarial:
[docs/labor-flex-share-4-paises.md](docs/labor-flex-share-4-paises.md).

| país | low / mode / high | lo que produce la diferencia |
|---|---|---|
| Estados Unidos | 0,25 / **0,58** / 0,85 | at-will: costo de salida ≈ 0 |
| Argentina | 0,15 / **0,55** / 0,90 | ESE + reforma 27.742 (el más frágil) |
| Chile | 0,15 / **0,45** / 0,70 | restricción de precio, no de permiso |
| Australia | 0,18 / **0,42** / 0,78 | casual con 25% loading; salida barata |

Pero el hallazgo que reordena el modelo es que **la diferencia grande no la hace
el país: la hace el contrato.** Un 3PL open-book en Chile tiene más flexibilidad
de caja que planta propia en EE.UU. Por eso `staffing_model` va de −0,30
(volumen mínimo comprometido) a +0,25 (open-book), y la primera pregunta al
cliente es por el contrato, no por la estadística.

Los parámetros económicos vienen calibrados para **Chile 2026** con fuente y
fecha por cada constante — jornada de 42 h desde abril 2026, costo cargado real
de un operario de bodega, tarifas públicas de 3PL, TPM y tipo de cambio del
Banco Central: [docs/calibracion-chile-2026.md](docs/calibracion-chile-2026.md).
`--calibration generico` vuelve a los priors sin validar y avisa que no sirven
para cotizar.

---

## Contrato de datos

Todo el kit corre sobre esto. Es deliberadamente pobre: cualquier WMS, TMS o ERP
puede exportarlo. Negociar un contrato más rico en el kickoff es la forma más
común de perder tres semanas.

```
case_id, activity, timestamp, resource, location
```

`resource` y `location` son opcionales — sin ellos se pierden el espagueti y el
análisis de variación entre operadores, nada más.

---

## CLI

```bash
fdekit demo                                   # diagnóstico completo
fdekit synth --out data/                      # genera el CD sintético
fdekit mine --log data/event_log.csv \
            --declared ORDER_RELEASED,PICK,CONSOLIDATE,PACK,QC,SHIP \
            --mermaid dfg.mmd
fdekit travel --log data/event_log.csv --plots figs/
fdekit dq --master data/master_wms.csv --plan-only --moe 0.04
fdekit dq --master data/master_wms.csv --measured data/truth_fisica.csv
fdekit sim --log data/event_log.csv --pickers 7 --packers 8
fdekit spc --values serie.csv --baseline 30 --plot xmr.png
fdekit probe --edi mensajes/
fdekit templates --out docs/                  # plantillas en blanco
```

---

## La maqueta de mesa — medir en vez de inferir

El espagueti de la herramienta 2 se **calcula** con aritmética sobre el layout.
`fdekit field` lo **mide**, y la diferencia entre los dos es el hallazgo.

Procedimiento completo, sobre un escritorio, en menos de dos minutos:

1. Imprimir un marcador ArUco del diccionario `DICT_4X4_50` (cualquier
   generador en línea; sirve papel común) y pegarlo a una taza, que hace de
   carro de picking.
2. Marcar cuatro esquinas del escritorio con cinta y medirlas con huincha.
   Escribir `refs.csv`:

   ```
   x_px,y_px,x_m,y_m
   0,0,0,0
   100,0,10,0
   100,100,10,10
   0,100,0,10
   ```

   Los `x_px,y_px` salen de mirar el primer cuadro del video; los `x_m,y_m` de
   la huincha. **Cuatro filas exactas, y que no queden alineadas** — cuatro
   puntos sobre una recta no definen un plano.
3. Grabar 30 segundos moviendo la taza y deteniéndola unos segundos en dos o
   tres "ubicaciones".
4. Convertir el video en detecciones (única parte que necesita OpenCV).
   `write_detections` ahora recibe el total de cuadros del video (`n`, el
   segundo valor que devuelve `detect_markers`) y lo graba como la primera
   línea del CSV — es el dato que sostiene la cobertura más abajo:

   ```bash
   pip install 'fde-field-kit[vision]'
   python -c "from fdekit.field.vision import detect_markers, write_detections; d,n=detect_markers('mesa.mp4'); write_detections(d,'det.csv',n); print(n,'frames')"
   ```

5. Y el análisis, que **no** necesita OpenCV:

   ```bash
   fdekit field --detections det.csv --refs refs.csv --out out --fps 30 \
                --log data/event_log.csv --k 1 \
                --aisles 4 --bays 10 --aisle-pitch 3 --bay-pitch 1
   ```

   > **Sin cámara ni maqueta:** los tres CSV ya están en
   > [`examples/mesa/`](examples/mesa/README.md) con el comando exacto. Corre en
   > cinco minutos y el residual sale **`sospechoso`** a propósito — el caso que
   > enseña no es el que cierra. `tests/test_ejemplo_mesa.py` corre esos mismos
   > archivos, así que el ejemplo no se puede pudrir sin que la suite lo diga.

   **Por qué `--k 1`, y por qué el software no lo pone solo.** El umbral por
   defecto es `k=3`: bajo tres sujetos, un "agregado por zona" no es un
   agregado, es una persona con otro nombre. Sobre un escritorio hay **una sola
   taza** — un sujeto. Con el default, la lista de ubicaciones no se emite y el
   PNG del espagueti **no se escribe**, porque ese gráfico *es* el itinerario
   completo de esa persona, dibujado. Eso no es una limitación de la demo: es la
   compuerta funcionando exactamente como funcionaría en planta el día que
   alguien pida "el recorrido de la zona de picking" en un turno donde había un
   solo operario. Pasar `--k 1` es asumir esa decisión de forma explícita — "sé
   que este agregado puede ser un individuo y lo emito igual" — en vez de que el
   software la tome por vos en silencio. Queda registrada: la salida trae
   `anonymity_k` con el umbral usado, así que un JSON emitido con `--k 1` nunca
   se confunde con uno emitido con el default. `--k 0` no existe: no baja el
   umbral, apaga la compuerta, y el parser lo rechaza.

   Los cuatro flags de geometría describen la maqueta. Sin ellos se usa la del
   CD (12 pasillos × 50 módulos), y la taza sobre el escritorio quedaría
   reportada en el pasillo 2 módulo 2 — un número que sale, y que no quiere
   decir nada.

   `--log` es el log del WMS: **el modelo contra el que se mide, y sin él no hay
   hallazgo.** Con él, la salida trae un bloque `residual` completo:

   ```json
   "residual": {
     "modeled_m_per_order": 19.8,
     "measured_m_per_order": 3.2,
     "residual_pct": -84.0,
     "residual_flag": "sospechoso",
     "residual_flag_reason": "el residual es negativo o esta cerca de cero; ...",
     "dock_legs_pct_of_modeled": 62.6,
     "track_pct": 100.0
   }
   ```

   Sin `--log`, la salida dice `"residual": null` **y explica por qué** en
   `residual_reason` — que no se pasó el modelo contra el cual comparar. La
   ausencia silenciosa del campo se leería como "no hubo residual".

   El `residual_flag` importa tanto como el porcentaje: el modelo es un **piso**
   (no ve retrocesos, ni el tramo de la excepción, ni congestión), así que un
   residual chico o negativo no dice "el modelo es preciso" — dice que la
   medición es sospechosa. `dock_legs_pct_of_modeled` es lo primero que hay que
   mirar cuando eso pasa: sobre un escritorio, la cámara nunca ve los tramos al
   muelle que el modelo sí cuenta.

   Hay un tercer valor que gana sobre los otros dos: `medicion_contaminada`.
   Aparece cuando la cobertura descartó puntos por caer **fuera de planta**.
   Esos puntos salen de las paradas, pero sus metros **siguen contados** en
   `measured_m_in_window` — `track_distance_m` mide la pista cruda. Un salto de
   500 m por homografía mal calibrada da un residual enorme y *positivo*, que
   leído por el signo caería en `"esperado"`: el flag se daría vuelta justo por
   el defecto que `--max-distance` existe para detectar. Con puntos descartados,
   el residual no se lee hasta recalibrar la homografía, y el flag lo dice en vez
   de afirmar lo contrario.

   Otros dos flags con default deliberado:

   - `--max-distance` — metros máximos entre un punto medido y la ubicación más
     cercana antes de descartarlo por **caer fuera de planta**. Por defecto se
     deriva de la geometría declarada: `2 × max(aisle-pitch, bay-pitch)`. Es un
     límite y no un interruptor: sin él, un punto a 500 m —lo típico de una
     homografía mal calibrada— se pega en silencio a la esquina del layout,
     cuenta como parada real y la cobertura informa 100%.
   - `--k` — umbral de anonimato (default 3, mínimo 1). Con menos de *k* pistas
     reconstruidas no se emiten **ni la lista de ubicaciones ni el PNG del
     espagueti**: con un solo sujeto no son un agregado, son el itinerario
     completo de una persona identificable — el JSON trae
     `locations_withheld_reason` y `espagueti_withheld_reason` en su lugar, y
     `espagueti_path` queda en `null`. Ver arriba por qué la maqueta de mesa
     necesita `--k 1`.

   Si el CSV de detecciones no trae la línea `# frames_total=<int>` (por
   ejemplo, uno grabado antes de esta versión de `write_detections`), agregar
   `--frames <n>` con el total de cuadros del video. Sin ninguno de los dos,
   `fdekit field` falla en vez de adivinar el denominador de la cobertura.

En `out/espagueti_medido.png` queda el recorrido real —cuando el umbral de
anonimato lo permite; si no, `espagueti_path` es `null` y el motivo lo explica.
La salida en consola trae
los metros medidos, el residual contra el modelo y la nota de cobertura — qué
fracción de los cuadros vio efectivamente el marcador y, cuando hay `--log`, qué
fracción de los **pedidos** (`track_pct`). **Un recorrido sin cobertura no se
muestra a un cliente:** lo que la cámara no vio no está en el número, y callarlo
sería el error más caro que puede cometer este kit.

Ninguna identidad sale del proceso: el `marker_id` se hashea con una sal de
sesión que nunca se escribe a disco, y `tests/test_field_privacy.py` lo
verifica. Además, **toda** la salida pasa por un único borde
(`field.privacy.gate_output`) que corre la verificación de identidad sobre el
diccionario completo y aplica el umbral de anonimato antes de emitir. No es una
función disponible por si alguien se acuerda de llamarla: es el camino de salida.
El PNG del espagueti también: la decisión de la compuerta se calcula **antes** de
dibujar, así que bajo el umbral el archivo no llega a existir.
El sensor ve al operador; el archivo que sale, no.

---

## Qué encuentra la demo

Sobre el CD sintético, sin ajustar nada:

**El flujo declarado en el kickoff cubre el 54% de los casos.** Hay 31 variantes,
y cinco actividades ocurren todos los días sin estar en el discurso:
`CARTON_REWORK`, `PICK_EXCEPTION_LOCATION`, `REPACK`, `REPLENISH`, `SHORT_PICK`.

**El cuello no es una actividad lenta, es una cola.** `ORDER_RELEASED -> PICK`
concentra el 61% de toda la espera del proceso. La transición más lenta por
unidad no aparece ni en el top 3 por tiempo total — que es exactamente el error
que comete quien optimiza sin Teoría de Restricciones.

**La triangulación.** La auditoría de maestros y el process mining llegan al
mismo hallazgo por caminos independientes:

> Los pedidos que tocan un SKU con dimensiones erradas se reprocesan **2.3x más**
> (χ²=44.8, p=2e-11). Arreglar el maestro elimina ~14% del reproceso de cartón,
> sin tocar una línea de código del producto.

**El contrafactual.** El periodo post tiene 15% más volumen (peak). El pre/post
naive dice que el proyecto **empeoró** el tiempo de ciclo en 56%. Diferencias-en-
diferencias, con grupo de control, dice que lo **mejoró** 8.7% (IC95 [-8.5, -1.5]
min, p=0.006). Sin grupo de control esa reunión se pierde.

**El dimensionamiento.** El barrido muestra la rodilla exacta:

| pickers | util. | ciclo medio |
|---|---|---|
| 5 | 0.99 | 39.4 min |
| 6 | 0.89 | 12.0 min |
| **7** | **0.77** | **9.6 min** |
| 8 | 0.71 | 9.6 min |

Pasar de 6 a 7 pickers corta el ciclo un 20%; de 7 a 8 no compra nada. Ese es el
gráfico de la reunión de capex.

---

## El canal DECIDIDA — `fdekit decide`

**Fase 0 — el piloto, y en la sala no entra software.** Dos semanas con una
planilla y una hoja impresa. Es la fase más importante y la que se va a querer
saltear: si el marcador verbal no aguanta dos semanas con una planilla, no
aguanta con 4.500 líneas de Python, y descubrirlo cuesta dos semanas en vez de
tres meses.

```bash
fdekit decide pilot init --out piloto --control "ops-semanal"
fdekit decide pilot baseline --calendar calendario.csv   # la variable dependiente
fdekit decide pilot score --tally piloto/planilla.csv    # criterio de continuación
fdekit decide pilot verdict --calendar calendario.csv --cutoff 2026-07-27 \
      --treat "comite-supply" --control "ops-semanal"    # criterio de muerte
```

`init` escribe cinco artefactos, de los cuales **solo dos entran a la sala**:
la planilla y la hoja impresa. Los otros tres —spec de medición firmable,
encuesta de 3 preguntas, protocolo— son del FDE.

La planilla lleva **una fila por punto de agenda de decisión, escrita antes de
la reunión**. Esa es la diferencia que hace calculable la tasa de declaración:
si solo se anotaran las decisiones tomadas, el denominador sería autocumplido y
la tasa siempre 100%. La celda vacía no es un error — es la medición.

- **≥70%** → seguir a fase 1.
- Por debajo → no seguir, y el diagnóstico dice **qué campo falta**: si falta el
  *porqué*, la frase se dice a medias y se corrige al facilitador; si falta el
  *dueño*, el problema es político. En ninguno de los dos casos lo arregla el
  software.

El diagnóstico se calcula **sólo sobre los puntos que cerraron**, y publica
sobre cuántos. Un punto que no cerró no dice nada sobre cómo se dijo la frase —
dice que no cerró, y eso ya lo cuenta la tasa. Contarlo dos veces manda al FDE a
la conversación equivocada: medido en un ensayo, el dueño faltaba en 0% de los
puntos cerrados y el reporte decía 38%.

Y el **criterio de muerte se declara antes de empezar**: si a la semana 10 las
horas-persona del scope tratado no bajaron ≥15% **contra una serie de control**,
el proyecto se apaga. Declararlo antes es lo que lo hace falsable; declararlo
después es elegir el umbral que da bien. Sin control, el efecto es
indistinguible del efecto Hawthorne — que en este tipo de intervención es grande
y real.

### Fase 1 — el registro

Registro de decisiones direccionable y versionable en git. Sin audio, sin
resolutor de referencias, sin grafo: las referencias se enlazan a mano. Diseño
completo en [docs/reuniones-decide-diseno.md](docs/reuniones-decide-diseno.md).

```bash
fdekit decide --root decide meeting --id 2026-08-01-comite --date 2026-08-01 \
  --roster "Marcela,Fabian,Rodrigo" --facilitator Marcela --consent-by Marcela
fdekit decide --root decide agenda --meeting 2026-08-01-comite
```

Con el registro vacío, `agenda` imprime **PROPONER CANCELAR**. Es la operación
de mayor retorno del sistema y la única que ataca la causa en vez del efecto:
todo lo demás optimiza una reunión que quizá no debía existir.

Lo que el registro **se niega** a hacer:

- Aceptar `"que quede mejor"` como criterio — tiene que traer un número o un
  predicado verificable, regla heredada de `A3.validate`.
- Aceptar un dueño fuera del roster. El roster es el scope léxico del sistema:
  es lo que Serena obtiene del compilador y acá hay que declarar.
- Aceptar `"evaluar si conviene X"` como decisión. Eso es la intención de
  decidir, y registrarlo como decisión es como el registro empieza a mentir.
- Un compromiso sin `decision_id` — eso es una tarea, y las tareas viven en el
  gestor de tareas del cliente.
- Más de 7 decisiones por reunión. Va a haber presión permanente para levantar
  ese techo. No levantarlo.
- Cerrar una decisión que todavía tiene compromisos abiertos: `safe_close` falla
  y los lista.
- `Meeting` sin `consent` levanta excepción en el constructor. Es la única pieza
  de cumplimiento imposible de retrofitear, y la Ley 21.719 entra en vigencia en
  Chile el 1-dic-2026.

**Fase 2 — el parser.** Un transcripto en texto plano entra por
`fdekit decide draft` y sale como borradores; `review` promueve los completos y
lista lo que falta, ordenado para que la vuelta a preguntar sea una sola.

El detector reconoce cuatro formas verbales y **nada más** — `queda decidido`,
`queda pendiente`, `asumimos`, `se compromete a`. Precisión alta y recall bajo,
por construcción: una frase sin marcador no produce nada, y ese silencio mide
la disciplina del facilitador, que es la métrica de supervivencia del sistema.

Lo que el parser **se niega** a inventar:

- Un dueño que nadie nombró. Y las pistas tienen dirección gramatical: *"dueño
  Marcela"* pone el nombre después, *"Marcela se encarga"* lo pone antes. Sin
  esa distinción, en *"reasignar la ruta de Fabián, dueño Marcela"* el sistema
  convierte a **Fabián —un tercero mencionado— en obligado**: error de datos y
  problema de privacidad a la vez.
- Una fecha donde había una expresión ambigua. *"La otra semana"* devuelve nada
  con el motivo escrito.
- Un plazo a partir de una fecha de revisión. *"Para el viernes"* es `due`;
  *"lo vemos en dos semanas"* no lo es. Es la lección de `_RE_CADA`.
- La evidencia de cumplimiento o la decisión padre de un compromiso: sin la
  primera "hecho" es una opinión, sin la segunda es una tarea.

**Fase 3 — el puente y el resolutor.** El audio entra por `transcribe` (Whisper
local) o texto plano, y al confirmar un borrador la cita se **congela**: copia
literal ≤500 chars redactada, `mm:ss`, y `sha256` del transcripto. Se copia y no
se enlaza porque el canal HABLADA tiene fecha de vencimiento — un puntero a un
recurso con política de retención es un puntero colgante por diseño. Después
`why()` devuelve la cita verbatim con minuto, y dice si la fuente sigue intacta,
cambió, o caducó.

```bash
fdekit decide resolve "lo del slotting" --meeting m1      # L0 -> L1 -> L2
fdekit decide confirm "lo del slotting" --symbol D-001 --meeting m1 --by "Marcela Perez"
fdekit decide unalias "lo del slotting" --reason "..."     # revierte y reprocesa
fdekit decide supersede D-001 --by D-002 --reason "..."     # lista lo que hay que retriar
fdekit decide head D-001                                   # cual rige hoy
```

Tres capas con cortocircuito: **L0** ID literal o herencia del punto de agenda
(EXTRACTED); **L1** tabla de alias filtrada por scope y vigencia (EXTRACTED);
**L2** slots tipados con Jaccard (INFERRED). **No hay L3** — ni BM25 ni
embeddings, porque generan candidatos plausibles y equivocados justo cuando
todavía no hay nada que los desmienta.

Si dos candidatos empatan dentro del mismo scope, el resultado es `AMBIGUOUS` y
es un **error reportado, no una elección**. Igual que un compilador.

Y contra el envenenamiento de alias —una confirmación humana equivocada que
después resuelve mal con EXTRACTED 1,0 para siempre— las cuatro contramedidas:
scope y vigencia obligatorios, colisión detectada **por creación** en `tick()`,
`unalias()` que revierte las menciones que ese alias decidió, y el chequeo de
coherencia de slots que frena la confirmación antes de escribirla.

**Fase 4 — medición.** Con **compuerta de volumen**: nada se publica antes de
50 decisiones y 15 reuniones. Bajo ese umbral la detección de comunidades
re-descubre los títulos de la agenda, y prometer el gráfico bonito el día 1 es
la forma más rápida de quemar la credibilidad del sistema. `export` se **niega**
a escribir bajo el mínimo; `metrics` calcula igual pero encabeza con la
advertencia.

```bash
fdekit decide mine       # ciclo de vida como EventLog: variantes, toques, reproceso
fdekit decide metrics    # la hoja imprimible
fdekit decide export     # vista derivada a graphify
```

El registro es un log de eventos: `case_id` = decisión, `activity` = estado
(DISCUTIDA → DECIDIDA → REABIERTA → REVERTIDA), `resource` = reunión. Eso
desbloquea `variants`, `directly_follows` y `bottlenecks` del kit sin escribir
análisis nuevo, y da **toques-para-decidir**: cuántas reuniones pasó un tema
antes de cerrarse.

Dos métricas que ninguna herramienta actual distingue:

- **Reapertura por ignorancia** vs. legítima — una decisión que se reabre sin
  que nadie haya consultado `why()` antes es desperdicio puro; con dato nuevo es
  aprendizaje.
- **Minutos-persona circulares** — reuniones que no movieron ningún estado, con
  el tiempo **medido** desde los offsets del transcripto. Sin audio no se
  estima: se declara que falta.

Y `QueryLog` mide la **lectura**, no solo la escritura: lectores únicos,
consultas fuera de la sala, tasa de consulta fallida. El registro que nadie
consulta es un pasivo, y es el modo de falla dominante de los sistemas de
gestión de conocimiento.

`tick(today)` cierra el lazo solo: vence compromisos y supuestos, pasa la
decisión a EN_RIESGO, detecta zombis (compromiso abierto colgando de una
decisión revertida) y todo eso aparece en la agenda de la próxima reunión sin
que nadie se acuerde de nada. Toma `today` como argumento y no lee el reloj —
una función que lee el reloj no se puede testear.

`referencing()` devuelve **siempre** `Coverage`. Serena puede prometer que
`find_referencing_symbols` devuelve todo porque abajo tiene un compilador;
nosotros no. Heredar la interfaz de esa promesa sin heredar la garantía —y
callarlo— sería el error más grave del diseño.

### Los huecos que matan el sistema entre el mes 2 y el mes 6

Un crítico adversarial encontró 16 huecos en el diseño de `decide`. Los cuatro
primeros eran de arranque; los que siguen son los que no se ven hasta que ya es
tarde. Todos están cerrados, cada uno con el test que lo fija.

**El día 1 el registro está vacío** y compite contra tres años de historial:
`why()` y `referencing()` devuelven vacío justo en las cuatro semanas donde se
juega la adopción.

```bash
fdekit decide seed --meeting kickoff --file planilla.csv --by "Marcela Perez"
fdekit decide minutes --meeting kickoff --dir actas/
```

La siembra **no relaja `validate()`** —lo que no pasa sale nombrado con el
motivo exacto— y no usa `force` nunca: hay un test que lee el archivo fuente y
falla si aparece. Las sembradas van con `origen=SIEMBRA`, así que **no abren la
compuerta de volumen**: 30 sembradas + 20 reales no son las 50 de la regla 5.
Las actas históricas sacan su fecha del **nombre del archivo** —procesarlas
contra hoy inventa plazos— y ninguna sale `ready`: todas llevan `sigue_vigente`
en lo que falta, que es la única pregunta del ejercicio.

**El compromiso renegociado en privado** es la muerte más común de estos
sistemas. Dueño y solicitante acuerdan una fecha nueva por chat, el tablero
sigue mostrando VENCIDO, y a la tercera vez el dueño concluye que el registro
está mal y deja de mirarlo.

```bash
fdekit decide slip C-001 --nueva-fecha 2026-09-05 --motivo "el proveedor movió la entrega" --por "Rodrigo Munoz"
```

Es a propósito el comando más corto del CLI: **si renegociar cuesta más que
incumplir en silencio, la gente elige el silencio.** La fecha se mueve pero la
anterior queda al lado. A las tres corridas hacia adelante deja de ser un atraso
y pasa a ser una decisión que no se tomó; la cuarta **no se rechaza** —eso
mandaría al dueño al silencio— se aplica y abre la pregunta.

**El actor que no estuvo:** el que llega en la semana 10, el que se va, y el que
ejecuta en el piso y no leyó ningún correo.

```bash
fdekit decide brief --scope pudahuel          # qué está decidido, en qué orden
fdekit decide reassign --sale "Ana Rojas" --entra "Luis Vera" --apply
fdekit decide orphans --activos "Marcela Perez,Rodrigo Munoz"
fdekit decide card C-001                      # tres líneas, para un WhatsApp
```

El brief va ordenado **por dependencia y no por fecha**: una lista plana obliga
al recién llegado a reconstruir solo por qué existe cada decisión. La tarjeta de
piso **sólo nombra al dueño**: sale hacia un canal sin ningún control, así que
es el punto exacto donde un tercero mencionado deja de ser reversible.

**El cliente no lee markdown en git.** El jefe de operaciones del CD es el
consumidor más importante del canal DECIDIDA y su herramienta es Teams o
SharePoint.

```bash
fdekit decide publish --out registro.html --scope pudahuel
fdekit decide transcript --meeting 2026-08-10-comite --out transcripto.md
fdekit decide handover --out entrega/ --por "Marcela Perez" --apply
```

Un archivo HTML sin red, sin login y sin herramienta nueva. Va **agrupado por
decisión, nunca por persona**, y lo dice en la página: un registro leído como
tablero de desempeño individual mata el sistema en dos semanas sin ninguna señal
técnica. Nunca señala nada sólo con color — la mitad de las veces se imprime en
blanco y negro.

`handover` ejecuta la cláusula de entrega al cierre: escribe, **verifica que
quedó escrito**, y recién ahí destruye el canal HABLADA dejando constancia. El
orden es la garantía entera; al revés no se vuelve.

**Dos FDE trabajando sin red** asignan `D-041` los dos, y el conflicto no
aparece hasta el merge:

```bash
fdekit decide --autor JM add decision --statement "Bajar el corte de pedidos a las 14:00" \
      --owner "Marcela Perez" --criteria "100% cortados antes de las 14:00" \
      --rationale "el transporte sale 15:00" --date 2026-08-10 --meeting kickoff
```

Cada autor lleva su propia serie. Sin `--autor` los ids son los de siempre.

Y el léxico es **bilingüe por término**: "reslotear" y "slotting" producen el
mismo valor canónico. Si produjeran distintos, dos menciones del mismo proceso
no se reconocerían como la misma cosa — que es justo lo que el resolutor existe
para resolver.

La página de política de datos que se firma en el kickoff está en
[docs/politica-de-datos.md](docs/politica-de-datos.md): base de licitud,
retención, terceros mencionados, la norma de uso no punitivo y qué pasa al
cierre.

## Audio del pasillo → observaciones

`fdekit.gemba.transcribe` cierra el cuello real de la herramienta 1: en el
pasillo no se escribe.

```python
from fdekit.gemba import GembaSession, transcribe_to_session

s = GembaSession("gemba.jsonl", site="CD Pudahuel", observer="FDE")
agregadas, por_revisar, avisos, cobertura = transcribe_to_session(
    "turno1.m4a", s, area="Picking", shift="mañana", anonymize=("Rodrigo",)
)
print(cobertura["nota"])
# 9 de 14 enunciado(s) produjeron borrador, **4 SIN CLASIFICAR**, 1 muy corto(s).
```

Dos capas separadas a propósito. `transcribe()` necesita el extra `audio`
(torch + transformers, Whisper local). `draft_observations()` es Python puro: si
el audio ya viene transcrito, funciona sin instalar nada. Toda la lógica —
clasificación de desperdicio, parseo de duración y frecuencia, anonimización —
vive en la capa pura, que es por lo que tiene 81 tests.

Las cuatro cosas se desempacan a la fuerza porque las cuatro hay que mirarlas.
`avisos` dice si el vocabulario de bodega no se aplicó (entonces *todos* los
borradores salieron de un texto degradado). `cobertura` dice cuántos enunciados
del audio **no** produjeron nada: sin ese denominador, "se agregaron 9
observaciones" se lee como "el audio tenía 9 observaciones", que es una
afirmación que la función no puede hacer. La suma tiene que cerrar — si no
cierra, `cobertura["cuadra"]` es `False` y hay un enunciado perdido por un
camino que nadie previó.

Lo que **no** hace: decidir. Un borrador sin duración o sin frecuencia no entra
al Pareto, va a `review_queue()` ordenada para que la vuelta al pasillo sea una
sola. El modelo no entiende la operación; solo evita que pierdas el hallazgo
porque tenías las manos ocupadas.

Y tampoco decide cuando el desperdicio es de dos tipos a la vez. "Mueve el
pallet dos veces" es transporte **y** es reproceso; el borrador sale con
`waste_type` en `missing` y los dos candidatos en `tied_wastes`, en vez de
quedarse con el que estuviera escrito más arriba en el léxico.

Consentimiento explícito antes de grabar, y `anonymize=` antes de que nada se
persista. No es un trámite legal: decide si te vuelven a hablar en el segundo
turno.

## Decisiones de diseño que valen la pena

**Los defectos del CD sintético están encadenados causalmente.** Maestro con
dimensiones erradas → reproceso de cartón. Maestro con ubicación vencida →
excepción de picking + viaje extra. Slotting aleatorio → clase A lejos del dock.
No es un dataset de juguete: es el que permite demostrar que dos herramientas
independientes convergen.

**El costo del reproceso se mide directo, no comparando grupos.** La tentación es
comparar el tiempo de ciclo de los casos con y sin reproceso. Esa comparación
está confundida por la hora de liberación y la cantidad de líneas, y en un CD
saturado llega a dar penalizaciones negativas — "el reproceso acelera el pedido".
Cuando un número contradice la física, el número está mal.

**Los límites de control se congelan.** Recalcularlos cada semana hace que la
degradación se vuelva la nueva normalidad. Es el error más común al implementar
SPC por primera vez, y `degradation_alarm` no lo permite.

**La distancia no es euclidiana.** Cambiar de pasillo obliga a salir por una
transversal. Si el cálculo diera la distancia recta, el espagueti subestimaría el
recorrido entre 30% y 200% y todo el caso de reslotting se caería.

**Los separadores de X12 se leen del sobre ISA, no se asumen.** El socio comercial
que usa `|` y `\n` existe, y rompe a todo el que asumió asteriscos.

**El tiempo de servicio se reconstruye desde el recurso.** Cuando el WMS solo
registra el término de cada tarea — que es el 90% de los casos — el tiempo de
servicio de un caso es el delta contra el término del caso anterior *del mismo
operador*. Exacto mientras el operador trabaje encadenado; por eso se calibra con
la ventana de mayor carga.

**El experimento de línea base usa varios días por celda.** Con una sola corrida
la mediana del tiempo de ciclo varía 30% entre turnos y el estimador queda
dominado por el ruido. Es la razón por la que la ventana de línea base son
semanas y no días.

---

## Secuencia de un despliegue

| Fase | Días | Herramientas | Entregable |
|---|---|---|---|
| Gemba | 0-14 | 1, 2, 4 | A3 con el problema en números y la lista de excepciones que el kickoff no mencionó |
| Diagnóstico | 15-30 | 3, 5 | VSM real vs declarado, cuello identificado, número prometido **con intervalo** |
| Línea base | 30-45 | 6 | spec firmado por el sponsor operativo |
| Piloto | 45-75 | 7, 8 | una zona, una ola, un turno. Kata semanal con el supervisor, no con el sponsor |
| Traspaso | 75-90+ | 9 | monitor encendido, trabajo estándar entregado, A3 cerrado contra la línea base |

Metodologías detrás: gemba walk, VSM, Teoría de Restricciones, 5 porqués, A3/PDCA,
poka-yoke, TWI Job Instruction, Toyota Kata, SPC, MSA, DMAIC.

---

## Tests

```bash
pytest -q
```

1.061 tests. No verifican que el código corra: verifican las propiedades que hacen
que los números sean defendibles frente a un cliente — que el DFG no una casos
distintos, que DiD recupere el efecto cuando la estacionalidad esconde el signo,
que la tasa de falsa alarma del gráfico de control esté bajo 2%, que la auditoría
detecte los defectos inyectados con más de 97% de acuerdo, y que la cifra anual
del caso económico no dependa de cuántos días de log mandó el área de TI.

## Licencia

MIT.
