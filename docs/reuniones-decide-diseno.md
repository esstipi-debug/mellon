> Estudio de diseno del 1-ago-2026. Cuatro enfoques independientes, tres jueces
> con lentes distintas, un critico de completitud y una sintesis. 9 agentes.
>
> Puntajes (0-10): friccion real / construibilidad / solidez de la analogia Serena
>
> | enfoque | friccion | construible | analogia | |
> |---|---:|---:|---:|---|
> | 3 - Esceptico operativo | **8.0** | **9.0** | 7.0 | base del diseno |
> | 1 - Meeting language server | 6.5 | 6.5 | **8.0** | injerto: resolutor y alias |
> | 4 - Separacion radical de canales | 7.0 | 5.0 | 7.5 | injerto: cita congelada, consentimiento |
> | 2 - Grafo temporal / process mining | 5.5 | 7.0 | 6.0 | injerto: gate de agenda, EventLog |
>
> **Correccion verificada despues del estudio:** la Ley 21.719 de proteccion de
> datos personales de Chile fue publicada el 13-dic-2024 y entra en vigencia el
> **1 de diciembre de 2026** — cuatro meses despues de este estudio, no "en ~24
> meses". Las PyMEs tienen 12 meses de amonestacion en vez de multa (hasta
> 1-dic-2027). La politica de retencion del canal HABLADA hay que escribirla
> ahora, no retrofitearla. Ver hueco H13.
>
> Companion: [reuniones-decide-huecos.md](reuniones-decide-huecos.md)

# Sistema de canales DECIDIDA / HABLADA para reuniones de FDE
## Diseño final — `fdekit.decide`

Base: enfoque 3 (escéptico operativo), ganador 2 de 3 jueces. Injertos: tabla de alias + regla de empate (enfoque 1), gate de agenda + adaptador `EventLog` (enfoque 2), cita congelada + presupuesto duro + consentimiento en el constructor (enfoque 4). Correcciones propias donde los tres jueces coincidieron en un agujero.

Verificado contra el repo antes de escribir: `C:/fde/fde-field-kit/pyproject.toml` (núcleo = numpy, pandas, matplotlib, scipy, simpy; `torch` vive en el extra `audio` con un comentario explícito de que el kit tiene que correr en el notebook prestado de un CD; **networkx no está declarado**) y `src/fdekit/gemba/transcribe.py` (`strip_accents` L98, `_norm` L104, `_number` L108, `_RE_CADA` L128, `parse_duration_s` L132, `classify_waste` L194, `Draft` L214, `split_utterances` L242, `draft_observations` L249, `_redact` L301, `review_queue` L308, `transcribe` L327).

---

## 1. La tesis en tres frases

Serena funciona porque debajo tiene un LSP determinista: declaraciones explícitas, reglas de scope y un índice de referencias verificado por el compilador; en una reunión no existe ninguna de las tres, así que el sistema no las simula con un modelo — las **fabrica** con tres conjuntos cerrados declarados (el roster del invite, la agenda atada a símbolos, y una tabla de alias que solo escribe un humano) y **reporta como error** todo lo que caiga fuera.

El acto de captura no es tipear ni etiquetar: es que alguien diga en voz alta *"queda decidido X, dueño Y, para Z, porque W"* — seis segundos, costo marginal cero en la sala, y con un efecto que ningún modelo produce: obliga al grupo a objetar en el momento en que objetar cuesta treinta segundos en vez de una reunión entera.

Y el entregable de mayor orden no es una minuta mejor sino una consulta que puede salir vacía: `agenda()` se calcula sobre el estado del registro, y cuando no hay compromisos vencidos, ni supuestos caídos, ni preguntas con dueño, imprime *"proponer cancelar"* — todo lo demás optimiza una reunión que quizá no debía existir.

---

## 2. El modelo de datos

Siete entidades. El techo es siete: una entidad más solo entra si hay una operación que la lee y un diagnóstico que la usa. Todo persiste como Markdown con front-matter YAML en `decisions/`, versionado en git (mismo patrón que `fdekit.a3.A3.to_markdown`). El índice es derivado y regenerable, como un `.tsbuildinfo`.

| Entidad | Campos | Análogo Serena | Canal |
|---|---|---|---|
| **Decision** (`D-###`) | `id` inmutable · `statement` (una oración imperativa) · `owner` (del roster, lista cerrada) · `date_decided` · `criteria` (definición de hecho; debe contener un número o un predicado verificable — regla heredada de `A3.validate`) · `rationale` · `status` VIGENTE/SUPERADA/REVERTIDA/EN_RIESGO · `supersedes[]` / `superseded_by` · `depends_on[]` · `meeting_id` · `anchor` (ver Anchor) · `aliases[]` · `slots{}` · `historial_statements[]` · `version` · `validate() -> list[str]` | El **símbolo**. `id` es el nombre calificado; `statement + owner + criteria` es la firma. Nunca se navega por "número de línea" (el minuto del audio), siempre por lo que significa. | decidida |
| **Commitment** (`C-###`) | `id` · `decision_id` **obligatorio** (un compromiso huérfano es una tarea, no un compromiso) · `what` · `owner` (del roster) · `due` (fecha absoluta, resuelta desde habla relativa) · `evidence_of_done` · `status` ABIERTO/CUMPLIDO/VENCIDO/CANCELADO/ZOMBI · `owner_presente_al_decidir: bool` · `validate()` | `find_implementations`. Es una relación 1:N real y verificable, no una metáfora: `safe_close` se apoya en esto. | decidida |
| **Assumption** (`A-###`) | `id` · `decision_id` · `statement` · `source` (dato, persona, o `sin_fuente`) · `check_by` (**fecha de vencimiento**) · `status` VIGENTE/VENCIDO/VIOLADO | No tiene análogo directo, y **es la entidad más importante del sistema**. Es lo más parecido a un test que falla: cuando `check_by` vence, la Decision pasa sola a EN_RIESGO y aparece sola en la agenda. Es el mecanismo causal contra la reversión por ignorancia — no la memoria, un vencimiento con fecha. | ambos |
| **OpenQuestion** (`Q-###`) | `id` · `question` · `resolver` (quién la responde, no quién la hizo) · `resolve_by` · `blocks[]` (IDs que no se pueden decidir sin esto) · `status` ABIERTA/RESUELTA/EXPIRADA · `answer_ref` | Un símbolo no resuelto: **build rojo**. Es el análogo exacto de `GembaSession.unquantified()` — lo no decidido va a una cola con dueño y fecha. Alimenta el gate de agenda. | ambos |
| **Meeting** | `id` (`YYYY-MM-DD-slug`) · `date` · `roster: tuple[str]` (del invite del calendario) · `facilitator` · `agenda_generada` · `transcript_ref` · `audio_ref \| None` · `consent: Consent` (**argumento obligatorio del constructor, levanta excepción si falta**) | El archivo fuente. El `roster` cumple el rol del **scope léxico**: es la lista cerrada contra la que se resuelven dueños de forma determinista. | ambos |
| **Anchor** | `meeting_id` · `t_start` / `t_end` · `cita_congelada` (copia literal, ≤500 chars, pasada por `_redact`) · `transcript_sha256` · `estado_fuente` VIVA/CADUCADA | `find_declaration`, con una diferencia deliberada: **la definición se copia al punto de uso**, no se enlaza, porque la fuente tiene fecha de vencimiento. Un puntero a un recurso con política de retención es un puntero colgante por diseño. | ambos |
| **Alias** | `surface_norm` (`_norm` de transcribe.py) · `symbol_id` · `scope` · `valido_desde` / `valido_hasta` · `confirmado_por` · `confirmado_en` · `mentions_resueltas[]` · `estado` VIGENTE/EN_DISPUTA/RETIRADO | La entrada del índice de referencias del LSP. Es el único activo que se acumula y el único mecanismo que hace que el sistema **mejore** con el uso en vez de degradarse. También es el único que puede envenenarse — ver §4. | ambos |

**Utterance no es una entidad navegable, a propósito.** Es un ancla. La navegación es siempre DECIDIDA → HABLADA, nunca al revés. Hacer navegable la transcripción produce un grafo de miles de conceptos vagos que nadie consulta dos veces, y es la minuta híbrida otra vez en forma de grafo.

**`DecisionDraft`** es un clon estructural de `Draft` (transcribe.py L214): `missing: tuple[str,...]`, `confidence: float`, `ready = not missing and confidence >= 0.5`, `start_s`, `expires_at = T+24h`. No es una entidad del registro: es el objeto que sostiene la incertidumbre hasta que un humano la colapsa.

---

## 3. Las operaciones

Once herramientas. Cada una es una función pura sobre el store, sin modelos, con presupuesto de tokens declarado en la firma.

| Operación | Análogo Serena | Qué hace | Fricción que elimina |
|---|---|---|---|
| `agenda(meeting_id)` | `get_symbols_overview` del scope | Consulta pura, sin IA. Cuatro bloques: compromisos vencidos por dueño; OpenQuestions cuyo `resolver` está en el roster; decisiones EN_RIESGO por supuesto vencido; solicitudes de reapertura. **Aplica el gate de tres condiciones** (§5). Si los cuatro bloques quedan vacíos: `sin decisiones pendientes: proponer cancelar`. | La agenda deja de salir de la cabeza de alguien a las 23:40. Y es la única operación de todo el sistema capaz de recomendar que la reunión no ocurra. |
| `why(D-###)` | `find_declaration` extendido | Devuelve `rationale` + `criteria` + supuestos con su estado + la **cita congelada literal** con `mm:ss` y hash del transcripto. Presupuesto: ≤15 utterances, nunca la sesión. | "¿Por qué decidimos esto?" pasa de arqueología social de 40 minutos a una cita verbatim en 40 segundos. Es la única razón por la que vale la pena guardar el transcripto. |
| `referencing(D-###, depth=1)` | `find_referencing_symbols` | Todo lo que cuelga: decisiones con `depends_on`, compromisos abiertos, supuestos vigentes, OpenQuestions bloqueadas. **Devuelve siempre `Coverage`** (resueltas / ambiguas pendientes / menciones sin resolver) — nunca un número desnudo. | "¿Quién más depende de esto?" — la pregunta que hoy no se hace porque no es contestable, y por eso la decisión se revierte y rompe cosas. |
| `implementations(D-###)` | `find_implementations` | Los Commitment que la implementan, con estado, días de atraso y flag `owner_presente_al_decidir`. | "¿Quién debe qué?" deja de preguntarse en voz alta en la reunión. Sale antes, en la agenda, por dueño. |
| `resolve(mención, meeting_id)` | `find_symbol` + go-to-definition | Corre L0→L1→L2 con cortocircuito (§4). Devuelve `Resolution(symbol_id \| None, tier, candidatos, evidencia, capa)`. Empate dentro del mismo scope = **AMBIGUOUS reportado**, nunca elección. | La re-discusión que arranca porque nadie ata la frase de hoy a la decisión de hace seis semanas. |
| `supersede(D-old, D-new, reason)` | `rename` | Marca SUPERADA, escribe punteros en ambos sentidos, y **lista las referencias que ahora apuntan a una decisión superada para que se resuelvan explícitamente**. No borra nada. No propaga automáticamente. | La decisión zombie que sigue circulando en un slide viejo, y las dos personas citando versiones distintas. |
| `safe_close(D-###)` | `safe_delete` | Cierra solo si no hay compromisos abiertos, supuestos vigentes sin verificar, ni OpenQuestions bloqueadas. Si los hay, **falla y los lista** (patrón `BaselineSpec.validate`). | El cierre administrativo de decisiones que en la práctica siguen abiertas — el momento en que el registro empieza a mentir y la gente deja de consultarlo. |
| `draft_decisions(texto \| segments, roster, meeting_date)` | El parser — el único componente probabilístico | Clon estructural de `draft_observations` (L249). Léxico de marcadores + `parse_due_date` + `resolve_owner` contra roster + `missing` + `review_queue()`. Precisión alta, recall bajo **por diseño**. | Que capturar la decisión compita con participar en la reunión. |
| `review()` | El diff que se revisa antes de commitear | CLI sobre `review_queue()` ordenada por `(len(missing), -confidence)`. Enter confirma, un carácter corrige, `p` reproduce 10 s desde el ancla. **Cada confirmación escribe un alias.** Lo no revisado en 24 h expira. | Concentra todo el costo humano en 90 segundos, una persona, una vez. Y la expiración impide acumular borradores no revisados hasta que nadie confía en el registro. |
| `unalias(surface, motivo)` | `safe_delete` sobre el índice | Retira un alias y **reprocesa las `mentions_resueltas` que ese alias generó**: revierte las aristas y las devuelve a la cola. | El envenenamiento de alias — la falla silenciosa a los seis meses. Ningún enfoque original lo tenía; sin esto, el determinismo ganado es determinismo del error. |
| `tick()` | Los `diagnostics` del LSP | Cron diario: vence compromisos y supuestos, pasa decisiones a EN_RIESGO, detecta zombis (compromiso abierto colgando de decisión REVERTIDA/SUPERADA), marca alias EN_DISPUTA por colisión. Alimenta `agenda()`. | El ciclo se cierra solo. Nadie tiene que acordarse de nada, que es exactamente lo que nunca pasa a los seis meses. |

---

## 4. Cómo se resuelven las referencias sin compilador

**Esta es la sección donde el diseño se gana o se pierde.**

Serena promete completitud porque el LSP se la garantiza: una referencia está *verificada por el compilador*. Nosotros no tenemos eso. La regla de diseño que gobierna todo lo demás:

> **No prometemos resolver siempre. Prometemos no mentir nunca en silencio.**

### 4.1 Fabricar determinismo donde se puede

Donde exista un **conjunto cerrado declarado**, la resolución se fuerza ahí y no se gasta un modelo. Hay tres:

1. **Roster del invite** → resuelve dueños. `resolve_owner("que lo vea Marcela", roster)` es un lookup contra seis nombres con desambiguación por apellido. Esto convierte el problema más caro del dominio (NER + diarización) en un diccionario. **Consecuencia dura: pyannote sale del camino crítico.** Si nadie nombra al dueño, el draft queda en `missing` y va a la cola — nunca se infiere.
2. **Agenda atada a símbolos** → resuelve el scope. Un punto de agenda declara qué símbolo toca; toda mención no resuelta dentro de ese punto hereda ese símbolo como candidato de peso alto. Es el análogo del nombre totalmente calificado.
3. **Léxico de marcadores verbales** → resuelve *qué es* un enunciado. El detector no hace comprensión de lenguaje abierto: detecta tres formas altamente restringidas (`queda decidido` / `queda pendiente` / `asumimos`). Precisión alta por construcción, recall bajo por construcción.

### 4.2 Las tres capas, con cortocircuito

Entrada: una mención (span) + `(meeting_id, agenda_item_id)`. Salida: `Resolution(symbol_id | None, tier, candidatos, evidencia, capa)`.

- **L0 — Anclas duras.** Regex de IDs (`D-034`, `D34`) + herencia del símbolo del punto de agenda + roster. Determinista. `tier = EXTRACTED`, confianza 1.0.
- **L1 — Tabla de alias.** Match exacto de `_norm(surface)` contra el índice invertido, **filtrado por scope y por vigencia en `meeting.date`**. Determinista una vez aprendido. `tier = EXTRACTED`.
- **L2 — Slots tipados.** Léxico por slot (`proceso`, `sitio`, `sistema`, `métrica`, `turno`) construido con el mismo patrón que `WASTE_LEXICON` (transcribe.py L48). Score = Jaccard de slots + proximidad de scope. `tier = INFERRED`. **Mata el falso positivo más caro y más frecuente: dos decisiones de slotting en sitios distintos.**
- **No hay L3.** Ni BM25, ni embeddings. Generan candidatos plausibles y equivocados justo cuando todavía no hay nada que los desmienta, y esas confirmaciones tempranas son las que envenenan la tabla para siempre. Además meterían una dependencia que el `pyproject` no tiene.

**Regla de empate, literal:** si dos o más candidatos empatan dentro del mismo nivel de scope, el resultado es `AMBIGUOUS` y es un **error reportado**, no una elección. Igual que un compilador ante una referencia ambigua. Un sistema que adivina en silencio contamina el índice y es peor que no tener sistema.

### 4.3 Los tres modos de error, y cómo se detecta cada uno

**(a) Falso negativo — no resuelve.** Modo dominante por diseño. Es visible: cae en `review_queue()`, cuesta 5 segundos de humano y produce un alias que evita la próxima. Coste asimétrico deliberado, heredado de `only_ready=True` en `transcribe_to_session`: perder una decisión es recuperable; inventar una es catastrófico.

**(b) Falso positivo de una mención — creyó D-034 y era D-041.** Tres detectores:
- El escriba, en la cola: toda resolución `INFERRED` se muestra **con la cita literal al lado**, no con el ID solo.
- **Chequeo de coherencia de slots contra la cita congelada:** si la cita no comparte ningún slot con el símbolo al que resolvió, la arista se marca `SOSPECHOSA` y vuelve a la cola. Es barato (comparación de dos sets) y atrapa el caso "mismo proceso, otro sitio".
- `Mention` persiste `capa_resolutora`, `confidence`, `confirmado_por` y `candidatos_descartados`. El error queda **escrito y reauditable**, no desaparece dentro del índice.

**(c) Alias envenenado — la falla que mata al sistema a los seis meses.** Una única confirmación humana equivocada escribe `"lo del slotting" → D-041`, y desde ahí *todas* las menciones futuras resuelven mal con `EXTRACTED 1.0`, por L1, sin volver a pasar por L2 ni por la cola. El error deja de ser detectable **justo porque se volvió determinista**. Cuatro contramedidas, todas obligatorias:

1. **Alias con scope y vigencia.** Nunca global, nunca eterno. `(surface_norm, scope, valido_desde, valido_hasta)`. Los alias de reunión son ambiguos *en el tiempo* — "lo del slotting" es D-034 en marzo y D-051 en junio porque el tema recurre; la colisión no es un accidente, es el caso normal.
2. **Resolución de colisión por creación, no por uso.** Al crear un símbolo nuevo con el mismo `scope` y slots solapados, `tick()` marca `EN_DISPUTA` todo alias del símbolo viejo cuyos slots colisionen. Un alias EN_DISPUTA no resuelve en L1: cae a L2 y vuelve a la cola **una vez**, y el humano decide si se cierra la vigencia del viejo.
3. **Procedencia y reproceso.** Cada alias guarda `mentions_resueltas[]`. `unalias(surface, motivo)` revierte esa lista completa y la devuelve a cola. Es el `safe_delete` del índice y es la operación que ningún enfoque original tenía.
4. **`supersede` NO agrega el statement viejo como alias.** El enfoque 1 lo proponía; fabrica colisiones a propósito. El statement viejo va a `historial_statements`, que es consultable pero **no es índice de resolución**.

### 4.4 Dónde se rompe la analogía Serena — exactamente

Cuatro puntos. No son matices; son límites duros que hay que decirle al cliente en el kickoff.

1. **No hay parser.** Un LSP resuelve por gramática. Acá la resolución es probabilística y la única garantía es la disciplina de reportar la ambigüedad. La analogía aguanta en la **forma** (símbolo, referencia, impacto, refactor seguro) y se rompe en el **mecanismo**.
2. **`rename` no propaga.** En código, renombrar arregla las referencias. Acá, cambiar el alcance de una decisión **no arregla los compromisos: los invalida.** Lo máximo honesto que hace `supersede` es enumerarlos y forzar triage humano. Prometer propagación automática se descubre la primera vez que se usa y quema la confianza en todo el sistema.
3. **No hay type checker, entonces las contradicciones no son demostrables.** Solo son detectables mecánicamente en el subconjunto cuantificado: misma métrica + mismo scope + direcciones opuestas, o rangos numéricos que no se intersecan. Fuera de eso es una heurística que produce candidatos. Aceptable porque ese subconjunto es donde más duele, pero no se vende detección general.
4. **El índice no es completo y hay que declararlo.** Serena puede prometer que `find_referencing_symbols` devuelve todo. Nosotros no. Por eso `referencing()` devuelve `Coverage` junto al resultado, siempre. Heredar la interfaz de esa promesa sin heredar la garantía —y callarlo— es el error más grave que puede cometer este diseño, porque la gente revierte con confianza fundada en un índice mudo.

---

## 5. El flujo completo

### ANTES

- **T-24 h, automático.** Un cron corre `fdekit decide agenda --meeting <id>`. Es una consulta, no un modelo.
- **El gate de tres condiciones** (injerto del enfoque 2, la única operación del set que ataca la causa y no el efecto). Un punto entra a la agenda de decisión solo si: **(a)** tiene decisor nombrado del roster, **(b)** está enunciado como pregunta cerrable, **(c)** su `blocked_on` está resuelto. Si falta el dato que bloquea, **no se agenda el tema: se agenda la obtención del dato**, con dueño y fecha, como OpenQuestion. El bucle no se mide después — no se produce.
- **Si los cuatro bloques salen vacíos:** `proponer cancelar`. Ésta es la funcionalidad de mayor retorno de todo el sistema.
- **La pre-lectura no se escribe.** Es `git log --since=<reunión anterior> -p decisions/`. Costo de producción: cero.
- **Si algún punto es un cambio a una decisión existente**, `referencing()` se corre y se adjunta. La gente llega sabiendo el costo del cambio.
- **Regla de proceso, no de software:** lo que no está en la agenda generada no se discute. Si alguien lo trae, se registra como OpenQuestion con dueño y fecha. Sin esta regla el resto es decoración.

### DURANTE

- **Costo humano de captura: cero clicks, cero tipeo, cero etiquetado.** Grabadora en el centro de la mesa, o el transcript nativo de Teams/Meet. En pantalla solo la agenda.
- **Consentimiento explícito al inicio**, dicho y registrado. Si el cliente no autoriza, el sistema **degrada limpio a solo-DECIDIDA** y sigue entregando ~60% del valor. Esto se diseña el día 1, no se parcha.
- **El único acto**, cuando algo se resuelve: *"Queda decidido: **qué**. Dueño **nombre**. Para **fecha**. Porque **razón**."* Seis segundos. Los cuatro campos son exactamente los que hace pasar `Decision.validate()`. Un facilitador competente ya hace esto.
- **Segundo marcador:** *"Queda pendiente: qué. Lo resuelve nombre. Antes del fecha."* → OpenQuestion. **Tercero:** *"Asumimos X, lo verificamos antes del fecha."* → Assumption con vencimiento.
- **Presupuesto duro: 7 promociones por reunión** (injerto del enfoque 4). Treinta decisiones vuelven el registro ilegible: es la minuta híbrida otra vez, ahora en git y con más ceremonia. Misma doctrina que `A3.validate` rechazando más de 5 contramedidas y `JobBreakdown` más de 12 pasos. **Va a haber presión permanente para levantarlo. No levantarlo.**
- **Antes de votar un cambio a algo existente se corre `referencing()` en voz alta.** *"D-007 tiene 14 referencias y 3 compromisos abiertos"* convierte una discusión de 40 minutos en una de 4. Cuesta cero líneas de código: es *cuándo* se corre.
- **Para reabrir una decisión que está en la pre-lectura hay que traer un dato nuevo, y dato nuevo es un número, no una opinión.** También cuesta cero líneas.
- El efecto de segundo orden que ningún modelo produce: decir la decisión en voz alta obliga al grupo a escucharla y objetarla ahí. Ese es el mecanismo. El software solo lo persiste. *(Especulativo: estimo este efecto en ~60% del total; no está medido y es lo primero que el piloto de planilla debe verificar.)*

### DESPUÉS

- **T+30 min — transcripción.** Ruta A: transcript nativo del proveedor de videollamada (instantáneo, mejor en audio multi-micrófono). Ruta B: `fdekit.gemba.transcribe.transcribe()` con Whisper local cuando el audio no puede salir del sitio. Honestidad de costo: 1 h de audio de sala en CPU con `large-v3-turbo` son 25-45 minutos reales, no 5.
- **T+90 min — `fdekit decide review`.** Una persona, cola ordenada por `(len(missing), -confidence)`. Objetivo duro: **90 segundos para una reunión de una hora**. Si toma más de 3 minutos, el detector está mal calibrado, no el usuario.
- **Al confirmar**, se congela la cita literal (≤500 chars, `_redact`) + `t_start/t_end` + `sha256` del transcripto, y se escribe el alias. La cita se **copia**, no se enlaza: el canal DECIDIDA tiene que sobrevivir a la caducidad del HABLADA.
- **Commit a git** con el `meeting_id` en el mensaje. Lo no revisado a las 24 h **expira**: la decisión no existe. Nada de "el sistema lo capturó igual".
- **No se genera minuta.** Ése es el punto entero. Lo que se distribuye es (a) el diff, 6-15 líneas, y (b) un mensaje por dueño con **sus** compromisos y sus fechas. Nadie lee cuatro páginas; todos leen un diff.
- **Continuo — `tick()` diario.** Vence compromisos y supuestos, pasa decisiones a EN_RIESGO, detecta zombis, marca alias en disputa. Todo eso alimenta la agenda de la próxima reunión sin que nadie haga nada.

---

## 6. Qué se reutiliza y qué hay que escribir

### Se reutiliza de `fdekit` (verificado en el repo)

| Pieza | Ruta | Uso |
|---|---|---|
| `transcribe()` | `gemba/transcribe.py:327` | Whisper local offline, `vocabulary=` para jerga del cliente, `anonymize=`. Se cambia `WAREHOUSE_VOCAB` (L38) por vocabulario de la cuenta. |
| `Draft` / `missing` / `ready` / `review_queue()` | `gemba/transcribe.py:214, 308` | Contrato completo de captura, testeado. `DecisionDraft` es un clon estructural. |
| `classify_waste()` | `gemba/transcribe.py:194` | Plantilla exacta de `classify_marker()`: score por keywords, confianza = margen del ganador sobre el segundo, corte 0.5. |
| `strip_accents()` / `_norm()` / `_number()` | `gemba/transcribe.py:98-108` | Normalización del índice de alias. Ya resuelve que Whisper escriba "dia" y la persona diga "día". |
| `parse_duration_s` y la lección de `_RE_CADA` | `gemba/transcribe.py:128-132` | Precedente de parseo de habla española con `WORD_NUMBERS`. **Y la lección más cara del kit:** el mismo texto no puede alimentar dos campos. Análogo directo: *"para el viernes"* es `due`; *"lo vemos en dos semanas"* es fecha de revisión, no `due`. Es el error que no falla, solo miente. |
| `_redact()` | `gemba/transcribe.py:301` | Anonimización antes de persistir. En reunión con cliente es más crítico que en el pasillo. |
| `split_utterances()` | `gemba/transcribe.py:242` | Segmentación de entrada. |
| `A3.validate()` / `A3.to_markdown()` | `a3/report.py` | Plantilla de `Decision.validate()` (devolver lista de faltantes, no booleano) y de persistencia versionable. `A3` pasa a ser artefacto **derivado**: `countermeasures` ← Commitments, `current_condition` ← criterios con número. |
| `BaselineSpec.validate()` | `baseline/design.py` | **No se adapta: se adopta.** Un BaselineSpec ya es una decisión con fórmula, `data_source` y dueño del lado del cliente. Es el gold standard de qué debe tener un `criteria`. Y su patrón "lista vacía = listo para firmar" **es** el gate de agenda. |
| `GembaSession` | `gemba/capture.py` | JSONL append-only offline para la cola de drafts antes de la revisión. |
| `cli.py` | `fdekit/cli.py` | Patrón argparse con subcomandos + `_print()`. Se agrega `fdekit decide`. |
| `processmining.EventLog` | `processmining/` | **Solo en fase 4.** Adaptador de ~30 líneas (`case_id=decision_id`, `activity=estado`, `timestamp=fecha`, `resource=meeting_id`) desbloquea `variants(collapse_repeats=False)`, `rework_summary(rework_activities=['DISCUTIDA','REABIERTA'])`, `directly_follows`, `bottlenecks`, `to_mermaid` — todo ya testeado. Mejor ratio valor/código del set. |
| `spc.xmr` | `spc/xmr.py` | **Solo desde la reunión ~15.** `compute_limits`, `nelson_rules`, `degradation_alarm`, `plot_xmr` para el XmR de toques-para-decidir. Límites congelados sobre 8-12 puntos de línea base; no se recalculan. |
| `dataquality.link_defects_to_rework` | `dataquality/master_audit.py:163` | Contiene el 2x2 (`risk_ratio`, `chi2`, `p`, PAF) que necesita la métrica de presencia decisor-ejecutor. Requiere extraer `risk_ratio_2x2(a,b,c,d)` a `fdekit/stats.py` y hacer que la original lo llame: ~30 líneas, los 164 tests quedan verdes. |
| `graphify` | externo | **Export unidireccional, fase 4, después de ~50 decisiones.** Nodos/aristas con `confidence` EXTRACTED/INFERRED/AMBIGUOUS, que calza 1:1 con nuestro tier. Nunca fuente de verdad, nunca motor de extracción, **nunca corrido sobre el transcripto crudo**. |

**Restricción de dependencias, no negociable:** `networkx` no está en `pyproject.toml` y `torch` está deliberadamente fuera del núcleo. El grafo de referencias a esta escala (cientos de nodos) es un `dict[str, list[str]]`. `draft_decisions()` acepta texto plano, así que todo el sistema funciona sin instalar nada cuando el transcript viene de Teams.

### Hay que escribir

```
fdekit/decide/
  schema.py     ~220 líneas  Decision, Commitment, Assumption, OpenQuestion,
                             Meeting, Anchor, Alias + validate() cada una.
                             Clon estructural de gemba/schema.py + a3/report.py.
  lexicon.py    ~120 líneas  DECISION_LEXICON con las tres formas de marcador,
                             SLOT_LEXICON (proceso/sitio/sistema/métrica/turno),
                             DECISION_VOCAB para el prompt inicial de Whisper.
  parse.py      ~250 líneas  parse_due_date(text, meeting_date) en habla española
                             ("el viernes", "fin de mes", "en dos semanas",
                             "antes del 15"), resolve_owner(text, roster) con
                             desambiguación por apellido, classify_marker().
                             *** ES EL ÚNICO TRABAJO GENUINAMENTE NUEVO ***
  draft.py      ~180 líneas  draft_decisions(), DecisionDraft, review_queue(),
                             expire(). Clon de transcribe.py L214-317.
  resolve.py    ~160 líneas  L0/L1/L2 con cortocircuito, índice invertido de
                             alias con scope+vigencia, regla de empate,
                             chequeo de coherencia de slots, unalias().
  anchor.py      ~60 líneas  Cita congelada + sha256 + t0/t1. El archivo más
                             corto y el más importante: es el puente entero.
  store.py      ~200 líneas  decisions/D-###.md con front-matter, IDs monótonos
                             con lock, decisions/index.json regenerable,
                             decisions/aliases.json, wrapper de git.
  query.py      ~240 líneas  agenda() con gate, why(), referencing() con
                             Coverage, implementations(), supersede(),
                             safe_close(), at_risk(), tick().
  export.py      ~80 líneas  JSON de graphify con tier por arista. Fase 4.
  eventlog.py    ~30 líneas  Adaptador a processmining.EventLog. Fase 4.
fdekit/stats.py  ~40 líneas  risk_ratio_2x2 extraído de master_audit.
```

CLI: `fdekit decide agenda|review|why|refs|impl|supersede|close|add|unalias|tick`. `add` es la escotilla para decisiones de pasillo o WhatsApp: una línea desde terminal. Tiene que funcionar sin red y en el notebook prestado.

Tests al 80%, estándar del repo. Lo crítico: parseo de fechas relativas ambiguas, `resolve_owner` con empate → `missing`, orden de la cola, `safe_close` rechazando con dependencias, cadena de `supersede`, **vigencia de alias en dos fechas distintas**, y `unalias` reprocesando menciones.

---

## 7. Plan de implementación por fases

### Fase 0 — Piloto de proceso, 2 semanas, cero líneas de código

Una planilla compartida con cinco columnas: `qué / dueño / fecha / porqué / supuesto+vence`. El facilitador dice la frase-marcador. La agenda se arma leyendo la planilla.

**Es la fase más importante y la que se va a querer saltear.** Si el marcador verbal no aguanta dos semanas con una planilla, no va a aguantar con software, y descubrirlo cuesta dos semanas en vez de tres meses. **Criterio de continuación: ≥70% de los puntos de agenda de decisión terminan con una fila escrita.** Por debajo de eso, el problema no es el software y el software no lo va a arreglar.

### Fase 1 — 5 días-persona, entrega valor sola, sin audio ni Whisper ni grafo

- `schema.py` completo con `validate()` (1.5 d)
- `store.py`: markdown + front-matter + IDs + índice (1 d)
- `query.py`: `agenda()` **con el gate de tres condiciones y la salida "proponer cancelar"**, `why()` con rationale tipeado, `referencing()` con `Coverage`, `safe_close()`, `tick()` (2 d)
- CLI `agenda|add|why|refs|close|tick` (0.5 d)

Las referencias se linkean a mano en esta fase (`--depends-on D-012`). No hay resolutor, no hay transcripción, no hay cita de audio. **Y aun así ya corta la re-discusión, ya cierra el lazo de supuestos vencidos → EN_RIESGO → agenda, y ya puede recomendar cancelar la reunión.** Sirve desde la segunda reunión.

### Fase 2 — +4 días: el parser y la cola

`lexicon.py`, `parse.py`, `draft.py`, subcomando `review`. Entrada: texto plano (Teams). El costo humano baja de "escribir cinco filas" a "confirmar en 90 segundos".

### Fase 3 — +3 días: audio, ancla y alias

`transcribe()` con Whisper local, `anchor.py` (cita congelada + hash), `resolve.py` con L0/L1/L2 + `unalias`. Acá `why()` empieza a devolver la cita verbatim con minuto, que es el diferencial real contra una minuta común.

### Fase 4 — +2 días, y **no antes de 50 decisiones y 15 reuniones**

`eventlog.py` (desbloquea `variants`, `rework_summary`, `to_mermaid`), `export.py` a graphify, XmR de toques-para-decidir con límites congelados. Minutos circulares y split de reapertura.

**Total: 14 días-persona de ingeniería, más 2 semanas de calendario de Fase 0.** Servidor MCP y detección de comunidades: después de seis reuniones reales, no antes. Casi todo lo que uno quiere agregar en la semana 4 son cosas que esas seis reuniones van a descartar.

---

## 8. Las métricas del sistema

Todas se calculan con el propio registro. Ninguna necesita instrumentación aparte. Se publican en una hoja imprimible que se lleva a la reunión de operaciones — **no en un dashboard**, doctrina explícita del kit (`a3/report.py`: "gráfico XmR en la reunión de operaciones, no en un dashboard que nadie abre").

**Métricas de supervivencia (si fallan, se mata el proyecto)**

| Métrica | Fórmula | Meta | Acción si falla |
|---|---|---|---|
| Tasa de declaración | decisiones registradas / puntos de agenda de decisión | ≥ 0.70 a las 3 semanas | **Matar el proyecto.** No agregarle features. |
| Duración de la cola de revisión | minutos de `review()` por reunión de 1 h | ≤ 3 min | El detector está mal calibrado, no el usuario. |
| % drafts en `missing` | drafts con campos faltantes / total | < 30% | `parse_due_date` / `resolve_owner` no están listos. |

**Métricas de fricción (el efecto que buscamos)**

| Métrica | Fórmula | Lectura |
|---|---|---|
| **Reuniones canceladas por agenda vacía** | `agenda()` vacías / reuniones agendadas | La única reducción de primer orden. Meta especulativa: ≥1 de cada 8 al mes 3. |
| **Reapertura por ignorancia** | reaperturas con cero referencias al `decision_id` o su rationale / total de reaperturas | Separa desperdicio puro de aprendizaje legítimo. Ninguna herramienta actual distingue esto. Meta: < 20% al mes 3. |
| **Minutos circulares** | Σ sobre reuniones sin avance de estado de `(seg_habla(tema)/60 × asistentes)` | El único número en pesos. `seg_habla` se **mide** desde los offsets de Whisper, no se estima. Requiere Fase 3. |
| **Compromisos huérfanos y zombis** | huérfanos: sin dueño ∧ sin fecha ∧ sin `decision_id` · zombis: abiertos colgando de decisión REVERTIDA/SUPERADA | Meta: **cero**. Un zombi es gente ejecutando algo que ya se revirtió: es un bug real, silencioso, y hoy estructuralmente invisible. |
| **Latencia de `why()`** | segundos desde que se hace la pregunta hasta que aparece la cita | Es la desigualdad de costos que hace que re-discutir sea más barato que buscar. Objetivo: < 40 s contra ~20 min de baseline. |
| **Toques-para-decidir** | reuniones en que un tema apareció hasta su primer DECIDIDA | Solo desde la reunión ~15, en XmR con límites congelados. Antes es ruido. |

**Métricas de calidad del índice (anti-autoengaño)**

- **Tasa de resolución automática (L0+L1)** por sesión — tiene que **subir** sesión a sesión. Si no sube, la tabla de alias no está aprendiendo y hay que revisar L1 antes que cualquier otra cosa.
- **Tasa de corrección en cola** — se publica **siempre junto** a la anterior, para que "menos cola" no se logre confirmando más rápido y peor.
- **`Coverage` de `referencing()`** — menciones sin resolver / menciones totales. Se muestra al lado de cada resultado, nunca se oculta.
- **Alias retirados por `unalias`** — si crece, el criterio de confirmación en la cola es demasiado laxo.

**Regla dura sobre métricas derivadas:** ninguna métrica agregada se computa sobre aristas no confirmadas. Si se quiere el número, se calcula **solo sobre el subconjunto EXTRACTED** y se reporta la cobertura al lado. Un tablero construido sobre resolución probabilística miente con cara de rigor, y un gerente actúa sobre él el lunes.

---

## 9. Lo que NO hay que construir

Esta sección es la que sostiene el presupuesto. Cada punto duele porque cada uno parece obviamente bueno.

**1. El escriba tipeando un CLI durante la discusión.** Es la disciplina en vivo que mata a esta categoría de producto. A las 17:00 el escriba está participando, no tipeando, y a la tercera semana el registro tiene huecos — **y un registro con huecos es peor que ninguno, porque genera falsa confianza.** Duele porque es la propuesta más elegante del set (enfoque 1) y la que hace que la analogía Serena sea más limpia. No importa: el acto de captura tiene que ser hablar.

**2. El resolutor de cuatro capas con BM25/embeddings y su corpus fixture anotado a mano.** Ocho de veinticinco días-persona para resolver automáticamente "lo del slotting" → D-034, un problema que un humano en la sala resuelve gratis diciendo el ID. Y las 18 sesiones sintéticas anotadas no calibran habla real. **El corpus se gana corriendo el sistema en seis reuniones reales y anotando ésas, no se fabrica.** Se conserva L0/L1/L2 y la regla de empate; se descarta L3 y el corpus sintético.

**3. Diarización (pyannote), en cualquier versión del MVP.** Token de HuggingFace, licencia aceptada a mano, modelo pesado, CPU sin GPU, y rinde mal en audio de sala en español chileno. Duele porque sin ella `why()` pierde el "quién lo argumentó", que es media potencia de la operación. Se acepta la pérdida: el dueño se resuelve contra el roster, y si nadie lo nombra el draft va a la cola. **Y aun con diarización perfecta, "quién habló" no resuelve "a qué se refiere"** — que es el problema real.

**4. Detección de comunidades, god nodes y surprising connections antes de ~50-100 decisiones.** Los cuatro enfoques llegaron a esta conclusión por separado, lo que la vuelve el consenso más fuerte del análisis: bajo ese volumen el clustering **re-descubre los títulos de la agenda**. Prometer el grafo bonito el día 1 es la forma más rápida de quemar la credibilidad del sistema. Hasta el mes 3, una tabla ordenada por dueño y fecha es estrictamente mejor. Corolario: nada de Neo4j, nada de export HTML interactivo, nada de embeddings.

**5. La batería de ocho métricas temporales con Kaplan-Meier.** Medir el bucle no rompe el bucle. Y ninguna de esas métricas dice algo antes de la semana 8 — un sistema que no sirve hasta la semana 8 no llega a la semana 8. Se salvan exactamente dos (minutos circulares, split de reapertura) y se descarta el resto, incluido el KM hand-rolled, que responde una pregunta que nadie hizo y es exactamente el tipo de rigor decorativo que hace que un tablero se vea serio y no se use.

**6. El almacén hablado con SQLite+FTS5, audio cifrado en reposo, TTL, lápidas y hook pre-commit de PII.** Cinco de veinte días-persona de infraestructura de cumplimiento —sin custodia de claves definida— construida antes de que exista la primera decisión registrada. Reduce **riesgo**, no fricción: es otro eje. Se conservan del día 1 solo las dos piezas imposibles de retrofitear: **el consentimiento como argumento obligatorio del constructor** (que levanta excepción, no un flag de config) y **la cita congelada con hash**. El borrado por TTL es un cron de 20 líneas cuando un cliente lo exija.

**7. La generación de minuta, en cualquier forma, incluido el "resumen ejecutivo por LLM".** Es literalmente el híbrido que el proyecto existe para eliminar. Duele porque es lo primero que va a pedir el cliente y lo más fácil de demostrar. Lo que se distribuye es un diff de 6-15 líneas y un mensaje por dueño con sus compromisos.

**8. Hacer navegable la transcripción como grafo de conceptos.** Produce miles de nodos vagos, ninguno direccionable, y multiplica por diez la superficie donde el sistema puede resolver mal. La navegación es siempre DECIDIDA → HABLADA por ancla, **nunca al revés**.

**9. El agente conversacional en vivo:** sugerencias durante la reunión, cronómetro en pantalla, análisis de sentimiento, visualización en tiempo real. Agrega ruido a lo único que requiere sincronía. Va a aparecer como presión de demo; hay que mantenerlo rechazado.

**10. Toda promesa de propagación automática en refactors.** En código, renombrar arregla las referencias. Acá, cambiar el alcance de una decisión **invalida** los compromisos. Enumerarlos y forzar triage es lo máximo honesto. Prometer lo otro se descubre la primera vez que se usa.

**11. Gestión de tareas.** Un `Commitment` es más chico y más raro que un ticket: es lo que se prometió en la reunión, no el trabajo. Si un compromiso vive en dos lugares, muere en los dos. El export a Jira/Asana es unidireccional o no existe.

**12. El servidor MCP en el MVP.** El argumento de economía de contexto es real pero de tercer orden: optimiza cómo consulta el **agente**, no cómo trabaja el equipo. Se expone cuando las operaciones existan y alguien las esté usando por CLI. Antes es una interfaz sobre un vacío.

**13. Modelar "confirmado = verdad permanente".** No es una feature que se descarta: es un supuesto que se prohíbe. Ninguno de los cuatro enfoques originales tenía forma de deshacer una confirmación humana equivocada, y sin `unalias` + vigencia + reproceso, el determinismo que se gana es **determinismo del error**. Es la única cosa de esta lista que hay que construir *más* en lugar de menos.

---

### Riesgos residuales declarados

- **El sistema depende de un rol, no de una herramienta.** Si el facilitador no dice la frase-marcador, la captura es cero — y un registro vacío es indistinguible de una reunión sana: **la falla es silenciosa**. Por eso existe la tasa de declaración como métrica de supervivencia publicada: es el único instrumento de detección.
- **Decisiones de pasillo y WhatsApp.** En operaciones son un porcentaje alto y son estructuralmente invisibles. `fdekit decide add` cubre parte. Es una pérdida que se declara, no se esconde. *(Especulativo: no tengo estimación confiable de qué fracción.)*
- **Calidad de transcripción en sala** (4-8 personas, micrófono a distancia, gente que se pisa) es sustancialmente peor que el caso de pasillo para el que se calibró `fdekit.gemba`. Implicancia: el transcripto sirve para anclaje y búsqueda, no para citar textual sin revisión. Por eso la cita congelada la lee un humano al ratificar y por eso el tope de 500 chars — una cita larga no se revisa.
- **Riesgo político.** Un registro de compromisos con dueño y fecha es un instrumento de rendición de cuentas. Se manifiesta como *"no pongamos dueño todavía"*. Si eso pasa sistemáticamente, el problema no es el software.
- **Descubribilidad legal.** Un registro versionado con hash es excelente cuando tenés razón y muy malo cuando no. Se dice en el kickoff, no cuando pase.