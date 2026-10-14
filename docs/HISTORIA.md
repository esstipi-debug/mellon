# Handoff — fde-field-kit

**Fecha:** 2026-08-02 · **Estado:** 852 tests verdes · **Repo:** `C:\fde\fde-field-kit`

```bash
cd C:\fde\fde-field-kit && python -m pytest -q      # 852 passed, 1 deselected
```

> **Rama actual: `harness/plan-1`**, no `feat/field-toolkit`. Otra sesión la
> creó desde ese trabajo y ahí siguen todos los commits. Verificar con
> `git merge-base --is-ancestor <hash> HEAD` antes de asumir dónde está algo.
>
> **Lo NO commiteado no sobrevive.** Se perdieron archivos completos dos veces
> por cambios de rama de otra sesión. Escribir fuera del repo (scratchpad) y
> copiar + testear + commitear en una sola operación.
>
> **Nunca `git checkout <archivo>` para deshacer un revert-check.** Me llevé
> puesto H6 entero de esa forma. Copia de respaldo y restaurar desde ahí.

El deseleccionado es el marcador `vision` (`pyproject.toml:39-40`): necesita
OpenCV y un video de muestra, y `addopts = "-m 'not vision'"` lo saca del corrido
por defecto. Correrlo aparte con `-m vision`.

> **Los hashes de este documento anteriores a `17b6901` sirven; los posteriores
> NO.** Otra sesión reescribió la historia de `feat/field-toolkit` para separar
> commits que habían levantado cambios ajenos con `git add -A`. El árbol final
> se verificó idéntico byte a byte. Rescate: `backup/historia-vieja` →
> `7282075`. **El único riesgo real es un `reset --hard` contra un hash viejo
> cacheado** — verificar con `git cat-file -e <hash>^{commit}` antes.
>
> Equivalencias de los commits que este documento nombra: `supersede` es
> `bc823b4` (no `b405442`), los `__all__` son `9d7ce06` (no `5acc584`), el
> fixture hermético y el guardia de higiene son `7444458` (no `0754957`). Los
> tres viejos siguen existiendo como objetos huérfanos, así que `git show` sobre
> ellos funciona y engaña: muestran contenido real que ya no está en la rama.
> `git merge-base --is-ancestor <hash> HEAD` es el chequeo que distingue.
>
> Los seis arreglos de procedencia son `4898ca9`, y **ese hash sí es de la
> historia actual** — nació ya separado.
>
> **Hay varias sesiones trabajando este repo a la vez.** Dos veces en una tarde
> se revirtieron ediciones a medio hacer, dejando el paquete llamando a una
> función inexistente. Verificar con `git status` después de editar, y no dar
> por hecho que un archivo quedó como se lo dejó.
>
> **El fixture de `test_value.py` está resuelto entero, no "parcial".** Un
> inventario de otra sesión lo listó como "sigue leyendo `out/hallazgos.json`":
> no. La única aparición de esa cadena en `tests/test_value.py` es un docstring
> (línea 404, sobre el guardia de formato viejo). El fixture vive en
> `tests/conftest.py`, de sesión, sobre `tmp_path_factory`. **No** se congeló un
> JSON en `tests/fixtures/` a propósito — eso testearía contra una foto en vez
> de contra lo que el demo produce hoy, y la cadena demo → value es justo donde
> vivió la anualización doble.
>
> Y `review_queue` "escrita dos veces" se evaluó y se deja: son dos funciones de
> tres líneas sobre tipos distintos (`Draft` y `DecisionDraft`), y unificarlas
> exige un protocolo genérico que no compra nada.

Python 3.11 en el venv de hermes-agent. Instalado con `pip install -e .`.
Dependencias del núcleo: numpy, pandas, matplotlib, scipy, simpy. `torch` vive
en el extra `audio` **a propósito** — el kit tiene que correr en el notebook
prestado de un CD, sin GPU y sin permisos de instalación. Esa restricción es
estructural, no una preferencia: hay decisiones de diseño (el front-matter
propio en vez de PyYAML, el grafo como `dict[str, list[str]]` en vez de
networkx) que existen sólo por eso.

---

## Qué es esto

Contexto: el usuario tiene un barrido de vacantes de Forward Deployed Engineer
(en su primer mensaje de la sesión) y perfil de supply chain con piso de centro
de distribución. El repo nació como respuesta a *"cómo desarrollar herramientas
para un FDE de operaciones en terreno"*.

Son **dos mitades** que comparten filosofía pero se usan distinto:

### Mitad 1 — el kit de diagnóstico de un CD

Nueve herramientas mapeadas a las fases de un despliegue, más el caso económico.

| módulo | qué hace |
|---|---|
| `gemba` | observación estructurada offline + Pareto; `transcribe` convierte audio de pasillo en borradores |
| `timestudy` | tiempos de ciclo, variación entre operadores, espagueti y mapa de calor desde el log del WMS |
| `processmining` | DFG, variantes, conformidad, cuellos por tiempo **total** perdido |
| `dataquality` | muestreo estratificado, IC de Wilson, y el vínculo χ² defecto→reproceso |
| `sim` | DES SimPy calibrado desde el log + Ley de Little + Erlang C |
| `baseline` | spec firmable, MDE con ICC, pre/post y diferencias-en-diferencias |
| `probe` | X12 940/945/214/856, contratos de API, husos horarios, idempotencia |
| `standardwork` | hojas TWI y runbook de traspaso |
| `spc` | XmR + 8 reglas de Nelson + monitor de degradación con límites congelados |
| `a3` | arma el A3 con los hallazgos ya insertados |
| `value` | caso económico: 5 arquetipos, 6 palancas, Monte Carlo, escalera de precio |
| `synth` | CD sintético con defectos **encadenados causalmente** |
| `stats` | `risk_ratio_2x2` compartido (extraído de `dataquality`) |

```bash
fdekit demo --out out          # diagnóstico completo, ~6 s
fdekit value --findings out/hallazgos.json --archetype todos --control
```

### Mitad 2 — `fdekit.decide`, el canal DECIDIDA

Registro de decisiones de reuniones con semántica de Serena (símbolos,
referencias, refactor seguro) sobre la separación **decidida / hablada**.
5.190 líneas de código, 2.027 de tests, cinco fases implementadas.

```bash
fdekit decide pilot init --out piloto      # fase 0: 2 semanas, sin software en la sala
fdekit decide agenda --meeting <id>        # fase 1: puede decir "proponer cancelar"
fdekit decide draft --meeting <id> --file acta.txt   # fase 2: parser
fdekit decide resolve "lo del slotting" --meeting <id>  # fase 3: L0→L1→L2
fdekit decide metrics                      # fase 4: compuerta de volumen
```

---

## Las decisiones de diseño que hay que respetar

Si se rompe alguna de estas, se rompe la tesis del repo. Están todas
documentadas en el código con el porqué.

1. **Lo que no está cuantificado no entra al análisis: va a una cola de revisión
   explícita con dueño.** Atraviesa `gemba` (`unquantified()`), `decide`
   (`review_queue()`), `A3.validate`, `BaselineSpec.validate`. Un registro con
   huecos es peor que ninguno porque genera falsa confianza.

2. **Capa pesada (modelos) separada de capa pura (lógica testeable).**
   `transcribe()` necesita torch; `draft_observations()` es Python puro con 37
   tests. Si el audio ya viene transcrito, todo funciona sin instalar nada.

3. **No prometemos resolver siempre; prometemos no mentir nunca en silencio.**
   `referencing()` devuelve **siempre** `Coverage`. Empate en el resolutor =
   `AMBIGUOUS` reportado, nunca una elección. Serena puede prometer completitud
   porque tiene un compilador abajo; nosotros no, y callarlo sería el error más
   grave del diseño.

4. **`today` como argumento, nunca `date.today()` dentro de una función de
   análisis.** Una función que lee el reloj no se puede testear, y `tick()` es
   la que decide si algo entra a la agenda de mañana.

5. **Compuerta de volumen.** Nada de fase 4 se publica bajo 50 decisiones y 15
   reuniones. Bajo ese umbral el clustering re-descubre los títulos de la
   agenda — fue el consenso más fuerte del estudio de diseño.

6. **Límites de control congelados.** Recalcularlos hace que la degradación se
   vuelva la nueva normalidad.

7. **Presupuesto de 7 decisiones por reunión.** Va a haber presión permanente
   para levantarlo. No levantarlo.

8. **Una sola anualización, y va donde está `operating_days`.** Las herramientas
   de diagnóstico (`timestudy`, `processmining`) hablan **siempre en la ventana
   observada** y exponen su denominador al lado (`orders`, `cases_in_window`).
   La conversión a base anual ocurre una única vez, en
   `value/levers.py::_annualize`. Anualizar en las dos capas es el bug del
   2-ago-2026: se cancelaba casi entero y dejaba un residuo del 20% que nadie
   veía. Si un módulo nuevo tienta con devolver un `*_annual`, no.

   Extensión: la ventana de `gemba` es un **turno**, no una ventana de log, así
   que anualiza contra `annual_shifts`. Por eso `shifts_per_day` vive en el
   `Archetype`, al lado de `operating_days` — que sigue siendo el único lugar
   del repo donde los días se multiplican.

9. **Una observación de gemba entra al caso económico sólo si se declara fuera
   del log.** `Observation.in_event_log`. Casi todo lo que se ve en un pasillo
   ya está en el log bajo otro nombre: *"buscar un SKU que no está"* es
   `PICK_EXCEPTION_LOCATION`, *"rehacer el cartón"* es `CARTON_REWORK`,
   *"esperar la ola"* es la espera de `ORDER_RELEASED → PICK`. Sumar el Pareto
   completo a L1 duplica la palanca **y el resultado sigue pareciendo
   razonable**, que es la única forma en que un error de ese tamaño llega a una
   reunión. `None` significa "no se declaró" y va a la cola de revisión (regla
   1), nunca a un default: un default decide en silencio si la observación vale
   plata. En la demo, de 24,6 h/turno de Pareto entran 0,92.

10. **Agregar con el mismo diseño con que se muestreó.** `stratified_sample`
    sobre-representa la clase A 3:1 a propósito, así que `audit_summary`
    post-estratifica contra `population_by_class` y devuelve la tasa del
    catálogo, no la de la muestra. Cuando no se le pasan las clases, el campo
    `weighting` lo dice en voz alta. Es la regla 3 aplicada a estadística: las
    dos tasas se ven idénticas en una tabla y sólo una es la que el CFO cree
    estar leyendo. Efecto colateral que vale conocer: con corrección por
    población finita, auditar el catálogo entero colapsa el intervalo a cero —
    ése es el argumento económico de automatizar la medición dimensional.

11. **Separar "no encontré" de "no podía encontrar".** `parallel_trends_check`
    devuelve `parallel_trends_ok` **y** `conclusive`. Un chequeo sin poder de
    detección que contesta "ok" firma el supuesto sin haberlo mirado: es
    ausencia de evidencia vendida como evidencia de ausencia. Vale para
    cualquier chequeo que se agregue. El mismo criterio ya vive en
    `diff_in_diff` (`testable`) y en `risk_ratio_2x2` (`muestra_suficiente`).
    Corolario práctico: con pocos períodos, contrastar contra la **t** con sus
    grados de libertad, nunca contra la normal — con 3 días y `z=1,96` el ruido
    sale como "DiD sesgado" y se descarta el único estimador defendible.

12. **Ningún parámetro de diseño de medición se hardcodea si el log lo puede
    dar.** El `icc` era `0.02` a mano y multiplica el tamaño de muestra por 36;
    `baseline.icc_from_log` lo estima del log histórico por ANOVA de una vía,
    con intervalo por la F y tamaño de grupo **efectivo** —no el promedio, que
    sesga hacia arriba justo cuando hay días de peak—. Tres reglas que vienen
    con él: un ICC negativo es ruido y se acota a 0 para el diseño (llevarlo
    daría un efecto de diseño bajo 1, o sea clustering que "ayuda"); sin días
    suficientes devuelve `usable=False` y el dimensionamiento corre con 0
    **diciéndolo**, porque un `days_per_group` calculado sobre un ICC ausente es
    lo que hace que un piloto significativo no se replique; y `strata` saca los
    cambios de nivel conocidos —un peak— que si no se cuelan como correlación
    intra-día. Medirlo **empeoró** el número en el papel: el MDE a 2 semanas
    pasó de 9,85 a 14,43. Eso es lo que pasa cuando un número deja de ser
    optimista, y es la señal de que el cambio fue en la dirección correcta.

13. **Si el kit infiere, la inferencia va etiquetada y se puede apagar.**
    `rework_summary` deduce que una actividad que sólo aparece después de un
    reproceso es parte de la cadena — así entró el `REPLENISH` de 8 minutos que
    no matcheaba ningún patrón de nombre — pero marca esas filas con
    `rework_kind="consecuencia"` para poder discutirlas en la sala, y pasar
    `rework_activities` explícito desactiva la deducción entera. Adivinar encima
    de un mapeo de taxonomía que el FDE ya hizo con el cliente es peor que no
    adivinar.

---

## Los bugs de clase "no falla, miente" que ya aparecieron

Vale conocerlos porque son el patrón de error dominante en este repo, y el
próximo va a parecerse.

| dónde | qué |
|---|---|
| `gemba/transcribe.py` `_RE_CADA` | *"cada 10 minutos"* alimentaba duración **y** frecuencia → impacto ×40 |
| `processmining/variants.py` | penalización de reproceso comparando casos con/sin → salía **negativa** |
| `value/archetypes.py` `cash_labor_bounds` | `flex × overtime_premium` aplicaba el recargo a horas que no eran extra → +33% |
| `value/model.py` | comparar beneficio contra ingresos cuando para un 3PL el ingreso es una tarifa |
| `decide/query.py` | `OpenQuestion` EXPIRADA **desaparecía** de la agenda — el bucle silenciado por el sistema |
| `decide/eventlog.py` | reusar `rework_summary` daba "2.268.000 horas anuales perdidas" |
| `decide/pilot.py` | agenda escrita medida por largo de body → el link de Teams contaba como agenda |
| `baseline/analysis.py` | `diff_in_diff` con varianza cero devolvía `p=0, significant=True` |
| `timestudy` + `processmining` + `value/levers.py` | anualización en dos capas: `× 250` abajo, `× annual_orders/(n × operating_days)` arriba. Se cancelaban salvo un residuo de `250/300` → L1 y L2 **20% bajas**, en silencio (2-ago-2026) |
| `timestudy` (al arreglar lo anterior) | `round(hours, 2)` era decorativo mientras el campo anualizado iba aparte; al volverse el insumo del cálculo, 0,0081 h → 0,01 h es +24% antes de multiplicar por los pedidos del año |
| `timestudy/spaghetti.py` `location_frequency` | filtraba sólo `PICK`, dejando fuera `PICK_EXCEPTION_LOCATION` y `SHORT_PICK`. El mapa de calor mostraba el CD que el WMS cree, no el que el picker camina — y el sesgo apuntaba **contra** el hallazgo |
| `processmining/variants.py` `rework_summary` | un `SHORT_PICK` de 50 s dispara un `REPLENISH` de 8 min que retiene al picker; el nombre no matchea el regex y esas horas se caían enteras de L2. Reproceso 20,97 → **28,88 h/ventana** |
| `dataquality/master_audit.py` `audit_summary` | `stratified_sample` sobre-representa clase A 3:1 y el agregado usaba `k/n` crudo: publicaba la tasa de la muestra sesgada como si fuera la del catálogo |
| `gemba/schema.py` | el cuarto `* 250`, en la columna que **ordenaba el Pareto** |
| `baseline/analysis.py` `parallel_trends_check` | no estaba exportada y el demo no la llamaba: **el supuesto que sostiene todo el DiD no se verificaba nunca**. Además ajustaba la recta sobre filas crudas (2.100 "puntos" donde había 3 días) y usaba `z` donde hacen falta 2 g.l. y una `t` |
| `decide/query.py` `supersede` | escribía `"SUPERADA por D-002: motivo"` y `eventlog._RE_HIST` exige el estado pegado a los dos puntos: **ninguna supersesión entraba al event log**. `safe_close` sí matcheaba, así que el log salía corto y creíble |
| `decide/metrics.py` `touches_xmr` | **la línea base del XmR nunca estuvo congelada** (regla dura 6). Recalculaba en cada llamada ordenando por fecha, así que una decisión fechada hacia atrás movía `center` 2,8333 → 2,5833. El docstring prometía "no se recalculan nunca" |
| `decide/transcript.py` `purge` | el reloj de retención era el **`mtime`**: un `git clone` lo resetea, así que la retención no vencía nunca. Y `hablada/` entraba a git por el `git add .`, así que borrar el archivo no destruía nada — `git show HEAD:hablada/m1.jsonl` lo devolvía entero |
| `decide/draft.py` los cuatro `_mk_*` | usaban `fecha.value` sin mirar `fecha.role`: **cualquier fecha del texto se volvía el plazo**. Con un export de chat, el timestamp del mensaje nacía como `due` en el pasado y `tick` lo marcaba VENCIDO el día uno |
| `decide/store.py` `add_decision` | el techo de 7 sólo se evalúa `if decision.meeting_id:`. Doce decisiones de pasillo con dueño fuera de todo roster se escriben las doce, y `volume_gate` las contaba |
| `decide/schema.py` `ANCHOR_SOURCE_STATE` | `CADUCADA` estaba declarado y **no lo escribía nadie**: `why()` mostraba `estado_fuente: VIVA` sobre un transcripto que ya no existe |
| `value/levers.py` | el Pareto de gemba no llegaba a ninguna palanca: `"gemba.pareto"` vivía sólo en el campo `source` del catálogo. La única herramienta con un humano y un cronómetro adentro, desconectada del caso económico |
| `baseline/design.py` + `demo.py` | el `icc` del dimensionamiento era una constante de `0.02` puesta a mano. Medido del log histórico da **0,0444**, y `days_per_group` pasa de 8 a **16**: el demo prometía una ventana de medición de la mitad de lo que hace falta. El parámetro multiplica la muestra por 36, y no necesitaba ningún sensor — necesitaba el log que el cliente ya tiene |

Los seis últimos los encontró otra sesión (`4898ca9`), inventariando los ~252
números que produce el kit uno por uno con su procedencia —
`C:\fde\PROMPT-INVENTARIO-MEDICIONES.md`. **Ese método encontró seis que la
auditoría por lentes no vio**, y la razón es estructural: la auditoría siguió
consumidores, y estos seis eran números sin consumidor o con el consumidor
equivocado. Vale replicarlo.

Dos correcciones más de ese inventario, sobre cosas que se daban por ciertas:

- **`WALK_SPEED_MPS` y `VERTICAL_PENALTY_S` no tocan ningún número de cliente**
  — sólo los usa `synth/generator.py`. Son parámetros del laboratorio. La
  constante que sí convierte un conteo en horas de cliente es el `walk_speed=1.1`
  de `travel_stats`, con **±37% de sensibilidad sobre L1**. Y el comentario de
  `layout.py:19` dice "sobreescribibles por cliente" y es falso: son globales de
  módulo, no campos del dataclass.
- **`activity_durations` sobrecuenta 7,2×.** Sus `total_h` suman 1.155,5 h en
  una ventana con 159,9 horas-persona disponibles: son deltas de caso en
  paralelo, o sea **tiempo de WIP presentado como tiempo de operación**. Y el
  97,1% de lo que llama "duración de PICK" es la espera `ORDER_RELEASED → PICK`.

---

## Estado real por fase de `decide`

| fase | estado | archivos |
|---|---|---|
| 0 — piloto | ✅ | `pilot.py` (540) |
| 1 — registro | ✅ | `schema` (499), `store` (364), `query` (518), `frontmatter` (97) |
| 2 — parser | ✅ | `parse` (350), `lexicon` (208), `draft` (291) |
| 3 — ancla y resolutor | ✅ | `transcript` (175), `anchor` (99), `resolve` (452) |
| 4 — medición | ✅ | `eventlog` (191), `metrics` (397), `export` (157) |

**Desviaciones del diseño, todas documentadas en el código:**

- Se agregó `frontmatter.py` (no estaba en el plan) para evitar PyYAML. Formato
  `clave: <valor JSON>` — se parsea con `json.loads`, no a mano.
- Se agregó un cuarto marcador verbal (`se compromete a` → Commitment). El
  diseño especifica tres; sin el cuarto, el bloque más usado de la agenda sólo
  se alimenta a mano.
- `slot_coherence` implementa **choque de slots**, no la regla literal del
  diseño ("no comparte ningún slot"), porque la regla literal no atrapa el caso
  que dice atrapar ("mismo proceso, otro sitio").
- La fase 0 tiene código, aunque el diseño diga "cero líneas": el código mide el
  piloto, no participa en él.

---

## Lo que NO está hecho, y no es olvido

- **Correr la fase 0 con gente real.** Es lo único que valida todo lo demás.
  Criterio: ≥70% de los puntos de agenda terminan con fila escrita.
- **Servidor MCP.** Es la forma final del producto (ver
  `docs/mercado-y-monetizacion.md`) pero el estudio lo puso en "no construir en
  el MVP": optimiza cómo consulta el agente, no cómo trabaja el equipo.
- **Whisper probado de verdad.** `transcribe()` nunca corrió con torch
  instalado. La capa pura sí está testeada.
- **Los huecos del crítico** en `docs/reuniones-decide-huecos.md`: H4 (arranque
  en frío), H5 (canal asíncrono — donde se toma la mayoría de las decisiones
  operativas), H7 (modalidades de reunión no consideradas), H10 (superficie de
  lectura para el cliente), H15 (propiedad y uso punitivo del registro).
- **Parámetros económicos sin validar**, listados en
  `docs/calibracion-chile-2026.md`: costo de incidente de integración,
  `capex_per_station_usd`, volúmenes por arquetipo. Y el WACC, cuya instrucción
  es *pedir el que usa el cliente en su comité de inversiones*.

---

## Auditoría del repo — 58 hallazgos, 19 altos

Corrida con tres lentes independientes (cabos sueltos / drift doc-código /
huecos de test) al cerrar la sesión del 1-ago.

> **Advertencia de confiabilidad.** Se anotó como "todo verificado a mano" y no
> lo estaba: el hallazgo #2 (anualización doble) tenía el diagnóstico y la
> magnitud equivocados, y le faltaba un tercer sitio. Ver el detalle más abajo.
> Tratar el resto de los altos como plausibles, no como confirmados, hasta
> abrirlos.

### Arreglado antes de cerrar

| qué era | dónde |
|---|---|
| **`resolve_owner` devolvía un tercero mencionado como dueño, con confianza 1,0** | `decide/parse.py` |
| `Coverage` tenía `phase=1` hardcodeado: `refs` decía "no hay resolución automática" con el resolutor cableado | `decide/query.py:348` |
| Docstring del paquete y help del CLI decían "fase 1" con las cinco implementadas | `decide/__init__.py`, `decide/cli.py` |
| README decía "70 tests" (son 392) | `README.md:406` |
| `fdekit value` no exponía `--country` ni `--staffing-model`: el estudio de 4 países era inalcanzable desde la CLI | `cli.py` |
| El repo no estaba en git | — |

El primero merece detalle porque **yo lo declaré arreglado en la fase 2 y no lo
estaba**. La regla 1 hacía match de nombre completo y cortaba antes de mirar las
pistas direccionales; mis tests sólo usaban nombres de pila, así que pasaban.
Con `"reasignar la ruta de Fabian Soto, dueño Marcela Perez"` devolvía a Fabián.
Es el agujero H14 de privacidad y un error de datos a la vez. Ahora hay un test
parametrizado con el roster invertido, que es el caso que lo destapa.

### Cerrado el 2-ago-2026

Eran los puntos 1 y 2 de la lista de pendientes. 388 → 422 tests.

| qué era | dónde |
|---|---|
| **Anualización doble** — detalle abajo, porque el diagnóstico original estaba mal | `timestudy/*`, `processmining/variants.py`, `value/levers.py` |
| `fdekit.timestudy` tenía CERO tests | `tests/test_timestudy.py`, 30 tests, módulo al 100% |
| `takt_analysis` reventaba con `ZeroDivisionError` si todos los eventos compartían timestamp | ahora devuelve `takt_s: None` + `warning` (regla 1) |
| `__all__` de `timestudy` no exportaba `travel_stats`, `standard_work_gap` ni `cycle_time_stats` — los tres que consumen `demo.py` y `value/levers.py` | `timestudy/__init__.py` |

#### La anualización doble — diagnóstico corregido

**Vale leerlo entero porque el hallazgo original de la auditoría estaba mal, y
se anotó como verificado a mano.** Decía: *"`spaghetti.py:54` y `cycles.py:122`
multiplican por 250 hardcodeado, y `value/levers.py:180` vuelve a escalar ese
valor ya anualizado. Un log de 30 días infla ~30×."*

**No infla 30×.** Los dos factores casi se cancelan:

```
timestudy:  h_anual = h_ventana × 250
levers:     unidades = h_anual × annual_orders / (pedidos_observados × operating_days)
          = (h_ventana / pedidos_observados) × annual_orders × (250 / operating_days)
```

Las horas de la ventana y los pedidos observados escalan juntos, así que **el
largo del log se cancela**: 30 días no inflan nada. Lo que quedaba era un
residuo constante `250 / operating_days`, y `operating_days` por defecto es
**300** (`archetypes.py:45`), no 250. O sea: **L1 y L2 salían 20% bajas**, en
silencio, y el error se movía si el arquetipo cambiaba sus días de operación.

Subestimadas, no infladas. Nada de lo que se le mostró a alguien estaba
sobredimensionado.

**Y un CUARTO sitio, que esta sección no capturó** (encontrado por otra sesión,
commit `4898ca9`): `gemba/schema.py` tenía su propio `* 250` en
`impact_h_per_year`, **y era la columna que ordenaba el Pareto**. Sobrevivió a
la revisión porque nadie aguas abajo lo leía — y no lo leía nadie porque
`levers_from_findings` **nunca leía `findings["gemba"]`**: el string
`"gemba.pareto"` vivía sólo en el campo `source` del catálogo de palancas. O
sea: la única herramienta del kit con un humano y un cronómetro adentro estaba
desconectada del caso económico, y el guardia de gemba en
`_reject_preannualized` protegía un camino que no alimentaba nada. Las dos cosas
están arregladas; hoy `levers.py:249` sí consume `gemba.value_input`.

La lección se repite: **la revisión encontró tres sitios porque siguió los
consumidores, y el cuarto no tenía consumidor.** Buscar por el patrón (`* 250`)
lo habría encontrado; buscar por el efecto, no.

**Había un tercer sitio que la auditoría no vio:** `processmining/variants.py:96`
hacía lo mismo con `annual_hours_lost`, que alimenta L2. Arreglar sólo dos de
tres habría dejado L2 mal mientras L1 quedaba bien — peor que el error parejo.

**Delta medido** sobre `hallazgos.json` regenerado, comparando ambas fórmulas:

| arquetipo | días | L1 viejo | L1 nuevo | Δ | L2 viejo | L2 nuevo | Δ |
|---|---|---|---|---|---|---|---|
| RETAIL_OMNI | 300 | 34.219 | 41.063 | +20,0% | 62.248 | 74.697 | +20,0% |
| 3PL | 300 | 15.128 | 18.154 | +20,0% | 27.520 | 33.024 | +20,0% |
| ECOMMERCE | 300 | 50.428 | 60.514 | +20,0% | 91.734 | 110.080 | +20,0% |
| MANUFACTURA | 300 | 3.062 | 3.674 | +20,0% | 5.570 | 6.683 | +20,0% |
| MAYORISTA | 300 | 6.844 | 8.213 | +20,0% | 12.450 | 14.939 | +20,0% |

**El contrato nuevo, que es la regla a respetar:** `timestudy` y
`processmining` hablan **siempre en la ventana observada**, y exponen su propio
denominador al lado (`orders`, `cases_in_window`). La anualización ocurre **una
sola vez**, en `value/levers.py::_annualize`, que es donde vive
`operating_days`. Es lo que el docstring de `levers_from_findings` ya decía que
pasaba: el código de `timestudy` era la desviación, no el docstring.

Dos cosas más salieron de ahí:

- **`travel` anualiza con su propio denominador.** `travel.orders` cuenta los
  pedidos *con líneas de picking*, que no son todos los casos del log. Antes los
  dos bloques compartían `cycle_times.n_cases`. En el CD sintético coinciden
  (800/800) y hoy no cambia nada, pero con un log real que traiga recepciones o
  devoluciones, sí.
- **`_reject_preannualized()`**: un `hallazgos.json` anterior al cambio revienta
  con instrucción de regenerar, en vez de dejar que `.get(k, 0.0)` haga
  desaparecer L1 y L2 sin aviso. Un caso económico al que se le cayó una palanca
  entera imprime un VAN perfectamente creíble — es exactamente el modo de falla
  dominante del repo.

**Lección de método, que es lo que hay que llevarse:** el hallazgo estaba
anotado como "verificado a mano" y no lo estaba. Vale releer los otros altos con
esa duda encima. Y la aritmética de unidades hay que hacerla escrita, no de
cabeza — el que la escribió vio dos `×250` y concluyó "doble", sin seguir el
álgebra hasta el final.

**`hallazgos.json` era JSON inválido** (`aae4231`). Salía con `NaN` literal,
del `duration_s=None` de las observaciones de gemba sin cuantificar que pandas
vuelve NaN al pasar por un DataFrame. Python lo escribía y lo releía igual, así
que el kit nunca se enteró; cualquier parser estricto de afuera sí, y
`fdekit value --findings` consume ese archivo. `_json_safe` convierte los
no-finitos a `null` y `allow_nan=False` prohíbe que se cuele otro por un camino
distinto — convertir acá y prohibir allá significa que el próximo revienta en
vez de escribir un archivo inválido en silencio.

### Releídos uno por uno con reproducción (`17b6901`)

Después de descubrir que la "anualización doble" estaba mal fundada, se
reverificó cada hallazgo alto restante ejecutando código, no leyendo. Resultado:
**dos eran bugs invisibles y reales, cuatro eran ciertos como hecho, uno estaba
sobredimensionado.**

**Bug 1 — el acento desactivaba la validación.** Había dos `_norm` con el mismo
nombre y semántica distinta; el de `decide/schema.py` colapsaba espacios pero no
quitaba acentos. Cortaba en las dos direcciones:

```
"quizas reslotear la clase A"   → RECHAZA   (correcto)
"quizás reslotear la clase A"   → ACEPTA    ← el hedge pasa
criterio "a mas tardar el cierre"  → aceptado  (correcto)
criterio "a más tardar el cierre"  → RECHAZADO ← el predicado válido no pasa
```

Ningún test lo veía porque todas sus cadenas estaban sin tildes. Resuelto con
una sola `normalize()` canónica en `gemba.transcribe`, que `decide/schema`
importa.

**Bug 2 — un `meeting_id` con typo apagaba la validación de dueño.**
`roster_of` atrapaba el `KeyError` y devolvía `None`, y `_check_roster` lo leía
como "no hay roster". Reproducido: una decisión con `meeting_id="reunion-que-no-existe"`
y `owner="ALGUIEN QUE NO ESTA EN NINGUN ROSTER"` se persistía sin chistar. El
roster es el scope léxico —la única pieza de determinismo que el diseño
fabrica— y un typo no puede apagarla calladamente. Ahora se distinguen los tres
casos: sin `meeting_id` → no aplica; existe → valida; no existe → **falla**.

**Ciertos, ya cubiertos:** CLI sin tests (1.077 LOC → `tests/test_cli_smoke.py`,
que verifica el `--help` de los 35 subcomandos y que **los ejemplos del README
parseen** — atrapó el de `decide confirm`, que omitía `--meeting`);
`calibrate_from_log` sin cobertura; `TranscriptStore.purge` sin cobertura.

**Sobredimensionado:** la "duplicación real" de `review_queue`. Son dos
funciones de tres líneas sobre tipos distintos (`Draft` y `DecisionDraft`);
unificarlas exigiría un protocolo genérico y no compra nada. Se deja.

### Tres reglas escritas dos veces (`b11ab00`)

Salieron del mapeo previo a implementar los huecos, no de buscarlas. Las tres
son **la misma familia**: una regla implementada en dos archivos, sostenida por
una convención, y la convención se rompió sin que nada fallara. Las tres se
reprodujeron ejecutando antes de tocar nada, y cada test nuevo se verificó
revirtiendo el arreglo y confirmando que cae.

| qué | efecto |
|---|---|
| `supersede` escribía `"SUPERADA por D-002: motivo"` y `eventlog._RE_HIST` exige el estado pegado a los dos puntos | **ninguna supersesión entraba al event log**: `variants`, `rework_summary`, `touches_to_decide` y `lifecycle_rework` ciegos a la operación central del diseño. `safe_close` sí matcheaba, así que el log salía corto y creíble |
| `tick` promovía sólo `ABIERTO→ZOMBI`; `orphans_and_zombies` contaba también los `VENCIDO` | un compromiso que venció **antes** de que su decisión fuera superada quedaba VENCIDO para siempre en el registro mientras el tablero lo reportaba zombi. Dos números para la misma pregunta |
| `add_meeting` usaba `save()` = `write_text`, sin el modo exclusivo de `_write_new` | registrar dos veces el mismo id **pisaba el roster en silencio**. El roster es el scope léxico: pisarlo invalida retroactivamente la validación de dueño de todo lo ya colgado de esa reunión |

Los arreglos atacan la causa, no el síntoma: `hist_line()` + `HIST_RE` ahora
viven juntos en `schema.py` —escritor y lector en el mismo lugar— y `hist_line`
**rechaza** un estado que el lector no vería, así que el próximo escritor no
puede repetirlo. `es_zombi()` es una sola definición usada por `tick` y por el
tablero. `add_meeting` exige `overwrite=True` explícito.

El test del event log es parametrizado a propósito: la regla no es "supersede
funciona", es que **toda** operación que cambia el estado de una decisión quede
visible. El próximo estado que se agregue tiene que sumarse ahí.

### Diseño de los huecos H6/H7/H5/H4, listo y con reparos

Workflow de 16 agentes: 4 lectores mapearon los clusters afectados, 4 diseñaron,
y 8 refutaron con dos lentes (colisión con las reglas duras / el bug que miente).
Los cuatro diseños volvieron **CON_REPAROS** — ninguno sólido, ninguno roto —
con 14 defectos CRÍTICOS y 35 ALTOS entre todos. **No implementar sin resolverlos.**

Salida completa en **`C:\fde\huecos-diseno.json`** (438 KB: mapa de símbolos con
firmas literales, los 4 diseños con firmas propuestas e invariantes, y los 84
defectos de las refutaciones). El script se re-corre desde
`workflows/scripts/huecos-decide-mapa-diseno-*.js`.

**El hallazgo transversal, que es lo que más importa:** los cuatro huecos chocan
con la **regla 5** por la misma razón. `volume_gate` cuenta `len(store.meetings())`,
y los cuatro agregan "reuniones" que no son reuniones de decisión — una ventana
de chat (H5), una sesión sembrada (H4), un daily de traspaso (H7), una sesión
registrada como SIN_AUDIO (H6). Quince dailies en tres semanas abren la compuerta
sin una sola métrica real detrás. Cualquier implementación tiene que decidir
primero **qué cuenta como reunión para la compuerta**, y esa decisión es una sola
para los cuatro.

Otras trampas del mapa que hay que conocer antes de tocar el paquete:

- `_to_fm` **no recorre** los campos de `Anchor` ni de `Consent`: los aplana con
  tuplas escritas a mano (`store.py:82` y `:84`). Hoy están completas —lo
  verifiqué contra `dataclasses.fields()`— pero un campo nuevo en cualquiera de
  las dos se pierde al escribir y vuelve a su default al leer, sin error.
- **Dos relojes.** `agenda()` hace `today or meeting.date`; `tick` recibe el día
  real desde el CLI. Todo bloque nuevo con fecha tiene que elegir cuál usa.
- `Meeting.__post_init__` **levanta** por roster vacío, y eso no lo esquiva
  `--force`. El perfil TERRENO de H7 ("roster = quien esté") no se puede
  construir hoy.
- No existe confianza de ASR en **ninguna** capa. La `mediana_confianza_asr` que
  pide H6 hay que fabricarla de punta a punta; derivarla del texto sería
  producir el número plausible y falso que la regla 3 prohíbe.
- Los borradores expiran a las 24 h. Cualquier ingesta masiva (actas históricas
  de H4, export de chat de H5) revisada al día siguiente desaparece.

### Los huecos del crítico: fundación + H7, H6, H5 (falta H4)

Los 14 críticos del diseño colapsaron en **7 decisiones estructurales**
(`C:\fde\fundacion-huecos.md`, con la resolución de los 11 críticos que la
refutación encontró contra la propia fundación). Orden construido:

| paso | qué |
|---|---|
| `bf1c449` | **`save()` valida**, con semántica de *no empeorar el registro*. Era un `write_text` desnudo y es lo que usan `supersede`, `safe_close` y `tick`: toda regla en un `validate()` era código muerto ahí |
| `aab3719` | **el Corpus.** `Meeting.clase`/`canal`, `Decision.origen`, dos predicados y un join. Contesta una vez qué cuenta como reunión y qué decisión es medible |
| `a596cf3` | **dos columnas de toques.** La afirmación central del diseño era falsa: el `+1` sí deflacta un caso al piso |
| `9e32632` | **la retención tiene ejecutor**, reloj correcto y destruye de verdad |
| `69d6bc4` | **H7** — el perfil gobierna grabación y gate |
| `42516c8` | **H6** — el estado de captura se DERIVA |
| `10b5bdf` + `99617ee` | **H5** — ingesta de chat, CONFLICTO y NO_DECISION |

**Falta H4** (siembra). Sus cuatro críticos ya están resueltos en la fundación,
y el principal —`origen` sin ruta de escritura— dejó de existir cuando el campo
aterrizó con el Corpus.

Dos decisiones de diseño que resolví **al revés** de lo que pedía el documento
de huecos, y hay que respetar:

- **El presupuesto de INCIDENTE NO se suspende.** El documento lo pide
  literalmente y es la regla dura 7 de frente. El perfil sólo puede BAJAR el 7.
  `_check_profile_ceilings()` falla el import si alguno declara más.
- **`cuenta_minutos_circulares` no existe como campo.** Se deriva del techo.
  Y `circular_minutes` filtra por `canal`, no por el Corpus: filtrar los dailies
  por ahí borraba 2.400 minutos-persona de desperdicio real.

### Cómo trabajaron los refutadores, y cuánto creerles

Los workflows adversariales encontraron **bugs reales que yo no habría visto**,
y a la vez reportaron **cifras que no reproducen**. Tres casos medidos:

| reportaron | reprodujo |
|---|---|
| "5 de 16 casos deflacionados al piso" | 0 de 16 con vueltas alternadas. El **mecanismo** sí es real |
| "tres comportamientos distintos en el orden día/mes" | `parse_due_date` es consistente en dd/mm. El defecto real era otro y más preciso |
| "el veredicto del XmR se da vuelta a DEGRADACIÓN" | no se da vuelta: las preguntas de chat quedan fechadas después de la decisión |

**Regla para quien siga: los mecanismos que reportan son reales, los conteos no.
Implementar por el mecanismo, nunca por la cifra** — y reproducir antes de creer,
que es cómo se encontraron los tres.

### Pendiente, en orden de importancia

**El fixture que dependía del cwd, resuelto** (`0754957`). Eran cuatro problemas
encadenados que terminaban en el peor: la suite tenía dos comportamientos según
su propio historial, así que "verde" significaba cosas distintas en esta máquina
y en un clon limpio.

No se congeló un JSON en `tests/fixtures/`: eso testearía contra una foto y no
contra lo que el demo produce hoy, y la cadena demo → value es justamente lo que
hay que cubrir. Fixture de sesión al temporal de pytest, determinista por
semilla, ~3 s una sola vez.

Y `tests/conftest.py` trae el guardia de la clase: `pytest_sessionfinish`
compara el árbol antes y después y falla si la suite escribió algo. Acotado a
propósito —mtime dentro de `src/`, `tests/`, `docs/`, y sólo entradas **nuevas**
en la raíz— para que no salte porque otra herramienta dejó un log al lado
mientras corría. Un guardia que salta por ruido se desactiva a la semana.

Verificado: 581 tests idénticos corriendo desde `C:/tmp` y desde el repo, y el
mtime de `out/hallazgos.json` no cambia tras una corrida completa.
**`__all__` invertidos, resuelto** (`5acc584`). El criterio no fue "exportar
todo lo que alguien importa" —eso vuelve inútil el espacio de nombres— sino la
inversión real: **un módulo que cruza el límite de paquete para buscar un nombre
público adentro de otro.** Análisis con AST: 15 inversiones en 7 paquetes.

La más reveladora: `gemba` no exportaba `normalize` ni `strip_accents`, que son
la normalización canónica de todo el kit. Esa omisión es lo que hizo natural
escribir un segundo `_norm` en `decide/schema.py` —mismo nombre, semántica
distinta— que fue el bug de acentos. El `__all__` invertido no era cosmético:
fue la causa de un bug de validación.

Y los consumidores ahora importan del paquete: exportar sin cambiar el import
deja la inversión viva con otro nombre.

`tests/test_api_publica.py` fija las dos invariantes, y la segunda —ningún
paquete alcanza el submódulo de otro— es la que importa: la inversión se produjo
sola por acumulación y se vuelve a producir sola. **El guardia no tiene lista de
excepciones a propósito.** Cuando falle, la respuesta correcta casi siempre es
exportar el nombre en el `__init__` de destino.

**`supersede()` implementado** (`b405442`). Era la última operación núcleo del
diseño que faltaba. Las cuatro reglas duras, cada una con test: escribe punteros
en ambos sentidos y no borra nada; **no propaga** —devuelve la lista de triage
con la acción por tipo, porque cambiar el alcance de una decisión no arregla los
compromisos sino que los invalida—; **no escribe un alias con el statement
viejo**, que fabricaría colisiones a propósito; y `head_of()` sigue la cadena
hasta la que rige hoy, que ataca directamente la fricción que el diseño nombra:
*"las dos personas citando versiones distintas"*.

Se complementa con `tick()`: `supersede` pregunta, `tick` denuncia los
compromisos que quedaron colgando marcándolos ZOMBI. Y la detección de ciclo
sólo es alcanzable por edición a mano del archivo — escenario legítimo, porque
el diseño los hace editables a propósito, y tiene su test.

El informe completo está en
`C:\Users\Gamer\AppData\Local\Temp\claude\...\tasks\w79bwp5cz.output`, y el
workflow se puede re-correr con `scratchpad/audit-handoff.mjs`.

### Otros

- **`transcribe()` nunca corrió con torch instalado.** El `ImportError` sí está
  testeado; la ruta feliz no.
- Hay una carpeta `C:\fde\out` fuera del repo, basura de correr `fdekit demo`
  con el cwd en la raíz. Se puede borrar; es síntoma del punto 3.

## Fechas y datos con vencimiento

- **Ley 21.719** (protección de datos, Chile) entra en vigencia el **1-dic-2026**
  — cuatro meses después de esta sesión. La política de retención del canal
  HABLADA hay que escribirla antes, no retrofitearla. PyMEs: 12 meses de
  amonestación en vez de multa.
- **IMM Chile** sube a $553.553 el 1-may-2026 (la calibración usa $539.000).
- **Ley 21.561**: 42 h/semana desde abr-2026, **40 h desde abr-2028**. Hay un
  test que falla a propósito cuando eso cambie.
- Las vacantes del barrido del usuario son de julio 2026 — re-verificar antes de
  postular.

---

## Documentos

| archivo | qué contiene |
|---|---|
| `README.md` | entrada; las cuatro mitades del kit |
| `docs/reuniones-decide-diseno.md` | el diseño de `decide`, 4 enfoques + 3 jueces + síntesis |
| `docs/reuniones-decide-huecos.md` | 16 huecos del crítico de completitud, priorizados |
| `docs/labor-flex-share-4-paises.md` | estudio de 4 países con refutación adversarial |
| `docs/calibracion-chile-2026.md` | costo laboral, jornada, FX, TPM, tarifas 3PL, con fuente |
| `docs/mercado-y-monetizacion.md` | Palantir/Anaplan/Kinaxis, GitHub, y el modelo de precio |
| `docs/huggingface.md` | modelos y datasets candidatos, con lo que HF **no** tiene |
| `docs/gemba-walk.md` | la doctrina del gemba walk: protocolo, desperdicios, anti-patrones, y dónde el kit se aparta de la certificación |

---

## Cómo trabajó esta sesión

Vale replicarlo porque produjo los mejores resultados:

- **Workflows con refutación adversarial.** El estudio de `labor_flex_share`
  usó 1 investigador + 1 refutador por país. El refutador bajó 3 de 4
  estimaciones, y en Chile a la mitad. Sin esa capa, el número de Chile habría
  sido 0,88 en vez de 0,45.
- **Panel de jueces con lentes distintas** para diseño. En `decide`, el enfoque
  que ganó en fricción y construibilidad perdió en solidez de la analogía, y la
  síntesis injertó del perdedor exactamente la pieza que faltaba.
- **Un crítico de completitud** al final, que preguntó "¿qué falta?" y encontró
  que el proyecto entero era infalsable (H1).
- **Verificar contra la fuente, no contra la memoria.** Las cifras de los
  estudios salieron de abrir el archivo primario.
