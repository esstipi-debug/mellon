# Mytra FDE — handoff de continuación

**Repo:** https://github.com/esstipi-debug/mytra-fde (privado)
**Local:** `C:\fde\fde-field-kit` · **Rama activa:** `harness/plan-1`
**Estado:** 852 tests verdes, 1 deselected

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
2. `docs/decide-fundacion-huecos.md` si vas a hacer **H4** — ahí están las 7
   decisiones estructurales y los 11 críticos ya resueltos.
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

## Las 8 reglas duras

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

Más seis bugs vivos encontrados en el camino, todos de clase *"no falla,
miente"* y todos reproducidos antes de tocarlos.

---

## Lo que sigue

### 1. H4 — la siembra (lo único que falta de los huecos)

Las 15-30 decisiones vigentes declaradas en el kickoff, los alias iniciales y la
ingesta de actas históricas. El documento lo llama *"el mejor retorno del
proyecto entero"*: el día 1 el registro está vacío y compite contra 3 años de
historial, así que `why()` y `referencing()` devuelven vacío justo en las 4
semanas donde se juega la adopción.

Sus cuatro críticos ya están resueltos en `fundacion-huecos.md`. El principal
—`origen` sin ruta de escritura fuera de `seed.py`— **dejó de existir** cuando
el campo aterrizó con el Corpus.

Lo que hay que respetar al construirlo:

- Las sembradas van con `origen=SIEMBRA`, y por lo tanto **no son `auditable`**:
  quedan fuera del Corpus y no abren la compuerta de la regla 5.
- Sembrar 15-30 decisiones contra un `meeting_id` explota en la octava por el
  techo de 7. El carril de siembra es paralelo, no una excepción al techo.
- **Poblar `slots`** con `extract_slots(statement + " " + criteria)`: sin slots,
  `mark_disputed` no puede disputar nunca los alias sembrados, y 30 alias
  declarados de memoria resuelven `EXTRACTED 1.0` de forma permanente e
  irrevisable.

### 2. Correr la fase 0 con gente real

**Es lo único que valida todo lo demás.** Hoy hay 852 tests que prueban que el
sistema hace lo que dice; ninguno que pruebe que a alguien le sirve. Criterio
declarado: ≥70% de los puntos de agenda terminan con fila escrita.

### 3. Huecos que quedan abiertos

- **H9** — onboarding, rotación y compromisos huérfanos
- **H10** — superficie de lectura para el cliente (no va a leer markdown en git)
- **H11** — el compromiso renegociado en privado
- **H15** — propiedad del registro al cierre, y uso punitivo

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
