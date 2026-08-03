# Mytra FDE — handoff de continuación

**Repo:** https://github.com/esstipi-debug/mytra-fde (privado)
**Local:** `C:\fde\fde-field-kit` · **Rama activa:** `harness/plan-1`
**Estado:** 1.058 tests verdes, 1 deselected

### Montaje desde cero

```bash
git clone https://github.com/esstipi-debug/mytra-fde.git
cd mytra-fde
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m pytest -q
```

En Unix, `source .venv/bin/activate`.

Python 3.11. Núcleo: numpy, pandas, matplotlib, scipy, simpy. **`torch` vive en
el extra `audio` a propósito** — el kit tiene que correr en el notebook prestado
de un CD, sin GPU y sin permisos de instalación. Esa restricción es
**estructural, no una preferencia**: hay decisiones de diseño que existen sólo
por ella (el front-matter propio en vez de PyYAML, el grafo como
`dict[str, list[str]]` en vez de networkx). Para transcripción local:
`pip install -e ".[audio]"`.

El deselected es el marcador `vision` (`pyproject.toml`): necesita OpenCV y un
video de muestra. Correr aparte con `-m vision`.

---

## Por dónde empezar

1. Este archivo entero (son cinco minutos).
2. `docs/decide-fundacion-huecos.md` si vas a tocar `decide` — ahí están las 7
   decisiones estructurales y los 11 críticos ya resueltos. Los huecos H4 a H7
   están cerrados contra ese documento, y también H9, H10, H11 y H15.
3. `docs/HISTORIA.md` cuando algo del código parezca arbitrario: casi todo lo
   que parece raro está ahí explicado con el bug que lo causó.

---

## Leer esto antes de tocar nada

Tres cosas que cuestan trabajo perdido si no se saben:

**Hay varias sesiones de agente sobre el mismo repo.** Se perdieron archivos
completos dos veces por cambios de rama ajenos. **Lo no commiteado no
sobrevive**: escribir fuera del repo (scratchpad) y copiar + testear +
commitear en una sola operación.

**Nunca `git checkout <archivo>` para deshacer una mutación de prueba.** Así me
llevé puesto H6 entero. Copia de respaldo y restaurar desde ahí.

**Los hashes anteriores a `17b6901` sirven; los posteriores fueron reescritos.**
Verificar con `git merge-base --is-ancestor <hash> HEAD` — `git show` sobre un
hash huérfano funciona y engaña: muestra contenido real que ya no está en la
rama.

---

## Qué es Mytra FDE

Dos mitades que comparten filosofía y se usan distinto.

**El kit de diagnóstico de un CD** — trece módulos mapeados a las fases de un
despliegue: `gemba`, `timestudy`, `processmining`, `dataquality`, `sim`,
`baseline`, `probe`, `standardwork`, `spc`, `a3`, `value`, `synth`, `stats`.

```bash
fdekit demo --out out
fdekit value --findings out/hallazgos.json --archetype todos --control
```

**`fdekit.decide`, el canal DECIDIDA** — registro de decisiones de reunión con
semántica de Serena (símbolos, referencias, refactor seguro) sobre la separación
**decidida / hablada**.

```bash
fdekit decide agenda --meeting <id>     # puede decir "proponer cancelar"
fdekit decide draft --meeting <id> --file acta.txt
fdekit decide metrics                   # con compuerta de volumen
```

---

## Las 9 reglas duras

Romper una rompe la tesis del repo. Están documentadas en el código con el
porqué, y hay tests que las fijan.

1. **Lo no cuantificado va a una cola de revisión con dueño.** Un registro con
   huecos es peor que ninguno: genera falsa confianza.
2. **Capa pesada separada de capa pura.** `torch` vive en el extra `audio` a
   propósito: el kit corre en el notebook prestado de un CD, sin GPU ni permisos.
3. **No prometemos resolver siempre; prometemos no mentir nunca en silencio.**
4. **`today` como argumento**, nunca `date.today()` dentro de una función de análisis.
5. **Compuerta de volumen:** nada de fase 4 bajo 50 decisiones / 15 reuniones.
6. **Límites de control congelados.**
7. **Presupuesto de 7 decisiones por reunión.** No levantarlo.
8. **Una sola anualización**, donde vive `operating_days`.
9. **El sensor ve al operador; el archivo que sale del sensor, no.** La
   agregación no es una promesa en un documento: es una propiedad del código,
   verificada por `tests/test_field_privacy.py`. Es el argumento central de
   `fdekit.field` — casi todos los vendors venden vigilancia disfrazada de
   productividad; acá la medición viene con olvido diseñado.

---

## Las dos mitades que no son `decide`

El grueso del trabajo reciente fue en `fdekit.decide`, así que estos dos quedan
fáciles de pasar por alto. **No son menores: `field` solo tiene 167 tests.**

### `fdekit.field` — sensores que miden lo que el WMS *infiere*

El WMS dice que un picker recorrió una ruta; `field` la **mide**. Video →
detecciones → pistas en metros, con cobertura declarada.

El corte que gobierna el paquete: **`vision` es la única pieza que toca cv2**, y
sólo produce detecciones crudas. Todo lo demás es Python puro sobre un CSV, y
por eso se testea sin cámara — mismo patrón que `transcribe` con torch, y por la
misma razón estructural (regla 2).

| pieza | qué |
|---|---|
| `vision.py` | video → CSV de detecciones. La única que necesita OpenCV; su test lleva el marcador `vision` y sale del corrido por defecto |
| `homography.py` | proyección del plano de la imagen al plano del piso |
| `tracks.py` | detecciones crudas → pistas en metros, **con cobertura** |
| `coverage.py` | honestidad de una medición de terreno: mismo contrato que `Coverage` en `decide` |
| `privacy.py` | la regla 9, hecha código |

**Un límite conocido y declarado** (vale conocerlo antes de prometer nada): con
dos operadores por zona, el umbral *k* no impide deducir quién es quién. Lo
mitiga, no lo elimina. Está en la sección 6 del spec y en el docstring.

Se usa desde el CLI: `fdekit field ...`

### `fdekit.guard` — el harness de auto-verificación

Contrato compartido entre la capa agéntica y la de terreno: `Hallazgo` (el dato
que cruza las dos capas, con procedencia obligatoria), `Guardia` (un predicado
**con su motivo escrito al lado**) y `cobertura` (misma doctrina que `Coverage`:
nombra primero lo que NO vigila).

**Stdlib pura a propósito.** Este subpaquete viaja al notebook prestado de un
CD, donde no hay GPU, ni red, ni permisos de instalación. Cualquier import
pesado que entre ahí rompe la regla 2.

Es trabajo en curso de otra sesión — ver `docs/superpowers/plans/` para el plan
vigente antes de tocarlo.

---

## Lo hecho en la última ventana

Los 14 críticos del diseño de huecos colapsaron en **7 decisiones
estructurales** (`C:\fde\fundacion-huecos.md`, con la resolución de los 11
críticos que la refutación encontró contra la propia fundación).

| commit | qué |
|---|---|
| `bf1c449` | **`save()` valida**, con semántica de *no empeorar el registro* |
| `aab3719` | **el Corpus** — `Meeting.clase`/`canal`, `Decision.origen`, dos predicados y un join |
| `a596cf3` | **dos columnas de toques** — la afirmación central del diseño era falsa |
| `9e32632` | **la retención tiene ejecutor**, reloj correcto, y destruye de verdad |
| `69d6bc4` | **H7** — el perfil gobierna grabación y gate |
| `42516c8` | **H6** — el estado de captura se DERIVA |
| `10b5bdf` | **H5a** — ingesta de chat (WhatsApp/Teams) |
| `99617ee` | **H5b** — CONFLICTO y NO_DECISION |
| `b3fbbe5` | **el carril declarado es paralelo al techo de la sala** |
| `7484000` | **el portal de alias** rechaza el símbolo sin slots |
| `8bb5f6c` | **H4** — la siembra del arranque en frío |
| `867b683` | **H4** — la ingesta de actas históricas, y H4 queda cerrado |
| `bed7351` | **H11** — el compromiso renegociado en privado |
| `b9fd59d` | **H9** — onboarding, rotación y entrega al piso |
| `b548458` | **H10** — la superficie de lectura para el cliente |
| `a469dc0` | **H15** — propiedad, salida y uso punitivo |
| `b8b2ee1` | **H12a** — léxico bilingüe, y el número del ASR se avisa |
| `d603a9a` | **H12c** — el id lleva al autor |
| `547585e` | **H16** — accesibilidad ejercible, y **H12e** |

Más seis bugs vivos encontrados en el camino, todos de clase *"no falla,
miente"* y todos reproducidos antes de tocarlos.

---

## Lo que sigue

### 1. H4 — cerrado

`src/fdekit/decide/seed.py`. Las tres entradas del arranque en frío: las 15-30
decisiones vigentes declaradas en el kickoff, los alias iniciales, y la ingesta
de actas anteriores al sistema.

```bash
fdekit decide meeting --id kickoff --clase KICKOFF --scope pudahuel ...
fdekit decide seed    --meeting kickoff --file planilla.csv --by "Marcela Perez"
fdekit decide minutes --meeting kickoff --dir actas/
```

La planilla es CSV con separador `;` — no `,`, porque las filas de criterio
llevan comas y un CSV con comas se parte en la mitad de la única columna que la
regla 1 exige completa. Sale con código 2 si algo quedó afuera.

Lo que sostiene el diseño, por si alguien lo toca:

- Las sembradas van con `origen=SIEMBRA`, y por lo tanto **no son `auditable`**:
  quedan fuera del Corpus y no abren la compuerta de la regla 5.
- **`promotion_ceiling(clase, origen)` es el único techo del sistema** y
  `add_decision` cuenta por `(meeting_id, origen)`. El carril declarado es
  paralelo (`DECLARED_BUDGET = 30`), no una excepción: sembrar contra un
  `meeting_id` explotaba en la octava, y la única salida era borrar el
  `--meeting` — justo la ruta donde no hay roster ni consentimiento.
- **`slots` poblados** con `extract_slots(statement + " " + criteria)`.
  `AliasStore.add` es ahora un portal que **rechaza el símbolo sin slots**: sin
  ellos `mark_disputed` no puede disputar y `_l2` no puede proponer, así que L1
  sería la única vía y sería indisputable.
- `why()` dice `origen` / `auditable` / `nota_origen`. Antes una sembrada
  devolvía el mismo objeto que una decidida en sala.
- `decide add decision --origen` cierra el agujero por el que un acta histórica
  aterrizaba como REUNION con fecha de hace seis meses: sería la línea base
  entera del XmR.

De `seed_minutes` (la ingesta histórica), tres cosas que sostienen el diseño:

- **La fecha base sale del nombre del archivo** (`2026-02-10-comite.txt`), y un
  acta sin fecha se rechaza. Procesarla contra hoy resuelve el habla relativa
  del acta al año equivocado y hace nacer compromisos con plazo inventado.
- **Ningún borrador sale `ready`**: todos llevan `sigue_vigente` en `missing`.
  Es la única pregunta del ejercicio y la que ningún parser puede contestar.
  Nada se auto-promueve, ni siquiera lo que parsea limpio.
- **La expiración viaja en el objeto** (`DecisionDraft.expira_en_horas`), no en
  el llamador ni en la constante global. El lote vive dos semanas; el flujo
  corriente sigue en 24 h. Subir la global rompería la propiedad que sostiene la
  confianza de la cola — *"lo no revisado en 24 h no existe"*.

### 2. Correr la fase 0 con gente real

**Es lo único que valida todo lo demás.** Hoy hay 852 tests que prueban que el
sistema hace lo que dice; ninguno que pruebe que a alguien le sirve. Criterio
declarado: ≥70% de los puntos de agenda terminan con fila escrita.

### 3. Los huecos del tier 2 y 3 — cerrados

| hueco | qué quedó | comando |
|---|---|---|
| **H9** | `rotacion.py` — el que llega, el que se va, el que ejecuta | `brief`, `reassign`, `orphans`, `card` |
| **H10** | `render.py` — una página HTML sin red ni login | `publish` |
| **H11** | `slip()` — renegociar más barato que el silencio | `slip` |
| **H15** | `cierre.py` + `docs/politica-de-datos.md` | `handover` |

Tres cosas de ahí que conviene no romper sin leer el porqué:

- **El rastro de `reassign` va en minúsculas.** `HIST_RE` convierte cualquier
  token en mayúsculas del historial en una actividad del event log: escribir
  `REASIGNADA:` corre la línea base congelada del XmR (regla 6) sin que ningún
  número se vea mal.
- **La cuarta corrida de `slip` no se rechaza.** Rechazarla manda al dueño al
  silencio, que es el modo de falla que H11 describe. Se aplica y abre una
  pregunta, resuelta por el dueño de la *decisión*.
- **`handover` escribe, verifica y recién ahí destruye.** El orden es la
  garantía; al revés no se vuelve.

### 4. H12 y H16 — cerrados

| hueco | qué quedó |
|---|---|
| **H12a** | léxico y slots **bilingües por término**: "reslotear" y "slotting" dan el mismo canónico. Slot `hito` (cutover, go live, hypercare) |
| **H12b** | `Decision.advisories()` avisa si el criterio trae un número que no está en la cita |
| **H12c** | `DecideStore(root, autor="JM")` → `D-JM-041`, serie propia por autor |
| **H12d** | ya cerrado por H6 (el estado de captura se deriva) |
| **H12e** | el límite del hash post-TTL, declarado en `verify()` y en la política |
| **H16** | `decide transcript` + la página deja de señalar sólo con color |

Tres que conviene no romper:

- **Ampliar el léxico es la operación que puede romper precisión alta / recall
  bajo**, y romperla es peor que el hueco: un falso positivo entra al registro
  con cara de decisión. Hay un test que verifica que ninguna forma nueva dispara
  sobre habla común (`"i agree with that"`, `"quedamos de vernos"`).
- **El número del criterio avisa, no bloquea.** La cita viene del canal HABLADA,
  que es de peor calidad *por construcción*; bloquear le daría autoridad al
  canal equivocado. Las fechas se recortan antes de buscar magnitudes: si no,
  serían dos falsos por cada decisión con plazo.
- **Sin `--autor` nada cambia.** El caso de un solo FDE es el normal y un prefijo
  ahí sería ruido permanente.

**Lo que queda abierto:** ninguno de los 16 huecos del crítico. Lo que sigue es
lo de siempre — correr la fase 0 con gente real.

### 4. Con fecha de vencimiento

- **Ley 21.719** (protección de datos, Chile) rige desde el **1-dic-2026**. La
  política de retención del canal HABLADA ya tiene ejecutor (`tick`), pero la
  página de política de datos del kickoff hay que escribirla.
- **IMM Chile** sube a $553.553 el 1-may-2026 (la calibración usa $539.000).
- **Ley 21.561**: 42 h/semana desde abr-2026, **40 h desde abr-2028**. Hay un
  test que falla a propósito cuando eso cambie.

---

## Cómo trabajar acá

Lo que produjo los mejores resultados, y vale replicarlo:

**Reproducir antes de creer.** El patrón de error dominante del repo es *"no
falla, miente"*: un número plausible producido por una unidad mal importada o
por un texto que alimenta dos campos. No se ve leyendo — se ve ejecutando.

**Verificar revirtiendo.** Un test que pasa con y sin el arreglo no prueba nada.
Cada arreglo de esta ventana se verificó revirtiéndolo y confirmando que los
tests caen.

**Los refutadores adversariales encontraron bugs reales, y reportaron cifras
que no reproducen.** Tres casos medidos:

| reportaron | reprodujo |
|---|---|
| "5 de 16 casos deflacionados al piso" | 0 de 16. El **mecanismo** sí era real |
| "tres comportamientos distintos en el orden día/mes" | consistente en dd/mm. El defecto real era otro |
| "el veredicto del XmR se da vuelta a DEGRADACIÓN" | no se da vuelta |

**Los mecanismos que reportan son reales, los conteos no. Implementar por el
mecanismo, nunca por la cifra.**

---

## Documentos

| archivo | qué contiene |
|---|---|
| `C:\fde\HANDOFF.md` | el handoff largo: historia completa, tabla de bugs del patrón, decisiones de diseño |
| `C:\fde\fundacion-huecos.md` | las 7 decisiones estructurales + resolución de los 11 críticos |
| `C:\fde\huecos-diseno.json` | los 4 diseños originales y sus 84 defectos |
| `C:\fde\h5-formatos-chat.md` | formatos de export verificados byte a byte contra 6 archivos reales |
| `docs/reuniones-decide-diseno.md` | el diseño de `decide`: 4 enfoques, 3 jueces, síntesis |
| `docs/reuniones-decide-huecos.md` | los 16 huecos del crítico, priorizados |
| `docs/mercado-y-monetizacion.md` | Palantir/Anaplan/Kinaxis y el modelo de precio |
| `docs/calibracion-chile-2026.md` | costo laboral, jornada, FX, tarifas 3PL, con fuente |
| `docs/labor-flex-share-4-paises.md` | estudio de 4 países con refutación adversarial |
| `docs/politica-de-datos.md` | la página del kickoff: base de licitud, retención, uso no punitivo, cierre |
