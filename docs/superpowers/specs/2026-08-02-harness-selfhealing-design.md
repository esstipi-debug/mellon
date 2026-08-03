# Harness de self-healing — diseño

**Fecha:** 2026-08-02 · **Estado:** diseño aprobado, sin implementar · **Repo:** `C:\fde\fde-field-kit`

Un harness que convierte cada fracaso observado en un guardia permanente, y que
publica al lado cuánto **no** vigila.

---

## 0. Por qué existe

El HANDOFF del repo nombra el patrón de error dominante: **el bug que no falla,
sólo miente** — un número plausible producido por una unidad importada sin
pensar, o por un mismo texto alimentando dos campos. Van 17.

Dos guardias del repo nacieron cada uno de un bug real: el de convenciones
(tildes en `.py`) y el de higiene (efectos de lado en el árbol). Los dos fueron
escritos a mano, después del hecho, porque alguien se acordó. Este diseño
sistematiza ese acto: que la lección se destile y aterrice como código
ejecutable sin depender de que alguien se acuerde.

Y hereda el problema epistemológico que `Coverage` ya resolvió en
`decide/query.py:30`: un harness de self-healing hereda la interfaz de la
promesa *"detecta los bugs"*. No los detecta todos, y nunca va a poder.
Heredar la interfaz sin heredar la garantía, y callarlo, es el error más grave
que puede cometer este diseño.

---

## 1. Alcance

**Dos capas** que comparten un contrato y no comparten motor.

| | capa 1 | capa 2 |
|---|---|---|
| dónde corre | tu máquina | el notebook prestado del CD |
| motor | agente | código determinista |
| qué cura | el código del kit | la instrumentación y la calibración |
| red / modelo | sí | **no** |

**Fuera de alcance, a propósito:** curar la *operación* del centro de
distribución (emitir contramedidas desde el runbook o el A3). No comparte
mecanismo con nada de acá, mueve gente de verdad, y merece su propio ciclo
spec → plan → implementación cuando estas dos capas estén paradas.

**Fuera de alcance, estructural:** ningún camino por el que la capa 2 aprenda
en terreno. El notebook del CD **ejecuta, nunca destila**. Todo aprendizaje
pasa por la cosecha en tu máquina. Es lo que hace que la regla 2 del repo
(`torch` no entra al núcleo) sobreviva al harness.

---

## 2. Decisiones tomadas

Las cinco preguntas que definieron el diseño, con lo que se eligió y lo que eso
cuesta.

### D1 — Las dos capas, en capas

Sustrato compartido, dos consumidores. La espina compartida **no es el agente**:
es el protocolo `detectar que algo miente → destilar la regla → ejecutarla como
guardia → publicar la cobertura al lado`. La capa 1 lo ejecuta con un agente;
la capa 2, con un `if`.

### D2 — El harness escribe tests y también arregla `src/`

Autoridad máxima dentro de su worktree. Se evaluó restringirlo a escribir sólo
tests y guardias, por la asimetría de que apretar la restricción nunca es
silencioso y aflojarla sí. **Se eligió la autoridad amplia**, con la contención
en el aislamiento (§4) y en el oráculo (§5) en vez de en el permiso.

Costo asumido y declarado: el modo de falla del repo — el arreglo que produce
otro número plausible — es alcanzable por el harness. El oráculo mecánico y la
suite completa son lo que lo acota; el merge manual es lo que lo termina de
contener.

### D3 — El oráculo es la separación productor/oráculo

El que escribe el test no puede escribir el arreglo, y el que arregla no puede
tocar el test. Es el patrón adversarial que ya funcionó en este proyecto (el
escéptico bajó tres de cuatro estimaciones del estudio de países).

Se evaluó y **se descartó** agregar invariantes externas al test (chequeos
dimensionales, conservación, monotonía). Consecuencia que este diseño asume y
publica: **el harness aprende familias de error que ya sabés nombrar, no
descubre familias nuevas.** Crece por acumulación, no por generalización.

### D4 — La memoria es ejecutable; lo legible se deriva

Cada lección es un test o un guardia. Cero prosa normativa. El índice legible se
genera desde el corpus ejecutable, nunca al revés.

El motivo es evidencia del propio repo: la memoria actual del proyecto es
`HANDOFF.md`, escrito a mano, y **ya mintió** — el documento confiesa que sus
hashes posteriores a `17b6901` no sirven, y que los viejos siguen existiendo
como objetos huérfanos, así que `git show` sobre ellos funciona y engaña. Es la
misma decisión que ya se tomó para `estado_captura` (D5 de
`fundacion-huecos.md`): un estado que alguien tiene que acordarse de escribir es
un estado que va a estar mal.

### D5 — La capa 2 cura instrumentación y calibración

- **Instrumentación:** el kit detecta que *su propia medición* se degradó (el
  WMS cambió un campo, la cámara perdió cobertura, el maestro se pudrió) y lo
  declara, en vez de seguir produciendo números sobre datos que ya no
  significan lo mismo.
- **Calibración entre sitios:** cada despliegue deja constantes medidas, y el
  sitio siguiente arranca con priors reales.

**La trampa que este diseño esquiva explícitamente:** el "self-healing" ingenuo
sobre SPC es recalibrar los límites cuando suena la alarma. Eso no cura el
proceso, cura la alarma — y `spc/xmr.py:9` ya lo prohíbe por diseño: *"los
límites se CONGELAN. Recalcularlos cada semana hace que el proceso se degrade
sin que el equipo se entere."*

---

## 3. Arquitectura

```
                        fdekit.guard          ← el contrato (viaja en el paquete)
                    Hallazgo · Guardia · Cobertura
                       ╱                    ╲
        CAPA 1 (tu máquina)            CAPA 2 (notebook del CD)
        motor: agente                  motor: código determinista
        ┌──────────────────┐           ┌──────────────────────┐
        │ captura pasiva   │           │ guardias de          │
        │  (hook, escribe  │           │ instrumentación      │
        │   evidencia)     │           │                      │
        │        ↓         │           │ calibración por      │
        │ cosecha a pedido │  destila  │ sitio                │
        │  (worktree       │ ────────→ │                      │
        │   aislado)       │  guardias │ evalúa · publica     │
        │ testigo ∥ reparador          │ cobertura            │
        └──────────────────┘           └──────────────────────┘
```

Dos procesos en la capa 1, con **autoridades opuestas**:

| | corre | escribe | autoridad |
|---|---|---|---|
| **captura** | sola, en hook | un renglón de evidencia por episodio | sólo observa — no puede mentir |
| **cosecha** | a pedido | tests, guardias y arreglos en `src/` | máxima, en worktree aislado |

**La frontera:** lo que corre solo, sólo observa. Capturar nunca miente; actuar
sí puede.

Se evaluó y se descartó un loop continuo en segundo plano. El HANDOFF documenta
que hay varias sesiones trabajando este repo a la vez y que dos veces en una
tarde se revirtieron ediciones a medio hacer. Peor: el guardia de higiene **no
puede distinguir** "lo escribió un test" de "lo estaba editando otra sesión" —
está escrito en su propio mensaje de error. Un escritor permanente lo vuelve
ruido, y el primer reflejo sería desactivarlo: se habría cambiado un guardia
real por un harness.

También se descartó disparar la cosecha con cada suite roja. Un test rojo
durante TDD es el estado normal y deseado; un harness que se dispara ahí pelea
contra el método del repo.

---

## 4. Flujo de datos

### 4.1 Captura — barata, pasiva, un renglón

**Qué es un episodio.** El hook observa las corridas de `pytest` y guarda sólo
el resultado de la última (nombres de los tests que fallaron, `HEAD` en ese
momento). Un episodio se cierra cuando una corrida posterior deja en verde tests
que la anterior tenía en rojo. Ese par —el `HEAD` de la corrida roja y el de la
verde— es el episodio, y es lo único que la cosecha necesita para reconstruir
los dos árboles del oráculo.

Consecuencias de definirlo así, asumidas:

- Un bug arreglado sin que ningún test lo haya atrapado **no genera episodio**.
  Es la misma frontera de D3, en su forma operativa.
- Si entre la corrida roja y la verde hubo commits ajenos, el episodio arrastra
  ruido. La cosecha lo detecta cuando el árbol anterior no falla por el test
  esperado, y lo descarta con su motivo.
- Si el árbol estaba sucio en la corrida roja, no hay `HEAD` que lo reproduzca:
  el episodio se marca `irreproducible` y no se procesa. No se intenta
  reconstruir desde un stash.

El renglón que escribe:

```json
{"fecha": "2026-08-02", "commit_antes": "a551d87", "commit_despues": "9e32632",
 "tests_que_fallaban": ["test_value.py::test_anualizacion"],
 "archivos_tocados": ["src/fdekit/value/pricing.py"], "mensaje": "fix: ..."}
```

No interpreta, no clasifica, no escribe código. Si el hook se rompe, se pierde
evidencia y nada más: modo de falla benigno por construcción.

`evidencia.jsonl` se versiona y es **append-only**. Si la cosecha decide que un
episodio no da lección, lo marca; no lo borra. Es D3 de `fundacion-huecos.md`
aplicada acá — un log de eventos al que se le sacan eventos es exactamente la
mentira silenciosa que la regla 3 prohíbe.

### 4.2 Cosecha — a pedido, en worktree aislado

`git worktree add` sobre `harness/cosecha-YYYY-MM-DD`. El árbol de trabajo no se
toca en ningún momento, así que las sesiones concurrentes dejan de importar. El
patrón ya existe en el repo: `split-wt/`.

Por cada episodio, dos roles que no se ven:

| rol | ve | escribe | prohibido |
|---|---|---|---|
| **testigo** | la evidencia, el diff del arreglo, `src/` | un test que falla | tocar `src/` |
| **reparador** | el test rojo, `src/` | el arreglo en `src/` | tocar `tests/` |

### 4.3 El oráculo — mecánico, no opinable

El test nuevo prueba dos cosas **ejecutadas**, ninguna afirmada:

1. Contra el árbol **anterior** al arreglo → tiene que **fallar**.
2. Contra el árbol **posterior** → tiene que pasar.

Si pasa en los dos, el test es vacuo y **se rechaza el episodio entero**, con su
motivo escrito.

Es el chequeo que distingue un test que prueba algo de un test escrito para
acompañar un arreglo — porque se corre en un árbol donde el bug todavía existe.
No depende de que ningún agente sea honesto, sólo de que `git` y `pytest` lo
sean.

### 4.4 Aterrizaje

El guardia aprobado aterriza en `tests/guards/` con su `Hallazgo` completo. El
índice `docs/harness/lecciones.md` se **genera**, nunca se edita.

Los guardias que hablan de **datos** en vez de código (esquema del WMS, cobertura
de cámara, salud del maestro) se emiten además como `Guardia` deterministas en
`fdekit/guard/`, y viajan al CD en el paquete.

La cosecha entrega: una rama, un resumen, y su cobertura al lado — cuántos
episodios entraron, cuántos se rechazaron y por qué.

---

## 5. Componentes

Regla del repo: muchos archivos chicos, uno por responsabilidad. Frontera dura:
**lo que viaja al CD va en `src/`; lo que gasta tokens, no.**

### `src/fdekit/guard/` — el contrato, viaja en el paquete

Stdlib pura. Sin numpy, sin red, sin modelo.

| archivo | qué hace | depende de |
|---|---|---|
| `hallazgo.py` | `Hallazgo` frozen. Procedencia obligatoria en el constructor: sin commit, fecha y dueño no se construye | stdlib |
| `guardia.py` | `Guardia`: predicado + motivo escrito al lado + su `Hallazgo`. Registro por nombre | `hallazgo` |
| `cobertura.py` | `CoberturaGuardia.is_complete → False`, con `nota()` que dice cuántas familias vigila y cuántas sabe que no | stdlib |
| `instrumento.py` | Guardias de instrumentación. Devuelven `Hallazgo`, no booleanos | `guardia` |
| `calibracion.py` | Constantes medidas por sitio, con `n` de sitios y dispersión | `hallazgo` |

Sobre `calibracion.py`: `archetypes.py:290` conoce hoy dos calibraciones,
`"chile"` y `"generico"`, y `"generico"` avisa que no sirve para cotizar. Se
agrega una tercera clase, `"medida"`, que es la que crece — con la honestidad
que el módulo ya exige: una constante medida en un sitio no es lo mismo que una
medida en diez, así que viaja siempre con su `n` y su dispersión, y por debajo
de un `n` mínimo se comporta como `"generico"` y lo dice.

### `tools/harness/` — la capa 1, fuera del paquete

Nunca se instala, nunca viaja.

| archivo | qué hace |
|---|---|
| `captura.py` | El hook. Rojo→verde, un renglón. Sin dependencias, falla hacia el lado seguro (no escribe) |
| `cosecha.py` | Orquesta: monta el worktree, itera episodios, arma el reporte |
| `roles.py` | Testigo y reparador, con sus prohibiciones |
| `oraculo.py` | El chequeo rojo→verde de dos árboles. **Es código, no un agente** |
| `indice.py` | Genera `docs/harness/lecciones.md` desde `tests/guards/` |

### `tests/guards/` — la memoria ejecutable

Un archivo por lección, nombrado por la familia de error. Corre en cada
`pytest`: una lección que dejó de ser cierta se pone roja el mismo día.

### `.harness/` — el estado

`evidencia.jsonl` (append-only, versionado) y `cosecha/` (un reporte por
corrida). Ninguno se edita a mano.

### Cambio al guardia de convenciones

Hoy cubre `src/fdekit/` y `tests/`. Se agrega `tests/guards/`, porque ahí
escribe un agente y es donde una tilde se cuela sin que nadie mire. `tools/`
queda **afuera a propósito**: no viaja al notebook del CD, que es la única razón
por la que la regla de tildes existe.

---

## 6. Modos de falla

**Las prohibiciones se hacen cumplir con `git diff`, no con confianza.** El diff
de cada rol se verifica contra su frontera; un diff que la cruza se rechaza
entero. Un rol que puede violar su prohibición no tiene prohibición, tiene una
sugerencia.

**El arreglo que cura el test y rompe otra cosa.** El oráculo corre la **suite
completa** en los dos árboles. Si un test que pasaba antes ahora falla, el
episodio se rechaza aunque el test nuevo esté verde.

**El guardia que se pone rojo seis meses después.** Va a pasar, y el reflejo es
borrarlo. Un guardia sólo se borra **con motivo escrito**, y el borrado es en sí
mismo un episodio de evidencia con procedencia. Agregar y quitar cuestan lo
mismo en trazabilidad; si no, el corpus se erosiona en silencio.

**La cosecha que no encuentra nada.** Tiene que poder devolver **cero
guardias**, y es un resultado bueno. Es `agenda()` otra vez: la operación de
mayor retorno del sistema es la que puede decir "proponer cancelar". Una cosecha
que siempre produce algo está produciendo ruido para justificarse.

**El merge.** La rama de cosecha **nunca se mergea sola**. Es la única línea que
la autoridad amplia de D2 no cruza, y es lo que mantiene el problema de las
sesiones concurrentes fuera del harness.

**En terreno: la degradación que no se cura recalibrando.** Cuando
`instrumento.py` detecta que la medición se degradó, tiene **prohibido** ajustar
el número para que vuelva a parecer sano. Declara la pérdida de cobertura y
sigue publicando el resto.

**El límite que hereda D3.** Sin invariantes externas, el harness sólo aprende
de fracasos que ya se manifestaron como test rojo: **no puede atrapar el bug que
nunca falló**, que es el patrón dominante del repo. Eso no va en una nota al
pie — es lo primero que dice `CoberturaGuardia.nota()`. El harness vigila las
familias que ya mordieron y publica que las otras no las vigila nadie.

---

## 7. Testing

### 7.1 El test que falsifica el harness entero

Un harness que genera tests es **infalsable por defecto**: puede producir
guardias para siempre sin que nadie sepa si sirven. Es exactamente el hallazgo
que reordenó este proyecto, así que aplicarlo al harness no es opcional.

El HANDOFF lista **17 bugs que no fallaron, solo mintieron**. Ese es el
conjunto de validacion, y ya existe.

Se toma uno con su par de commits — la anualización doble es el candidato
natural, tiene rama propia (`fix/anualizacion-unica`) — se le da al harness el
árbol **anterior** al arreglo, y se le pregunta si produce un guardia que atrape
el bug. La respuesta es un sí o un no ejecutable.

El número honesto no es 17/17: es **cuántos de los 17 atrapa, publicado**. Si
atrapa dos, el harness atrapa dos, y `CoberturaGuardia` lo dice con esas
palabras.

### 7.2 Por unidad

| unidad | cómo se testea | el test que importa |
|---|---|---|
| `oraculo.py` | dos árboles fixture | darle un **test vacuo real** (verde en los dos árboles) y verificar que lo rechaza. Sin este test, el oráculo es decorativo |
| `roles.py` | diffs sintéticos | un diff del reparador que toca `tests/` → rechazado |
| `captura.py` | `tmp_path`, hermético | no depende del `cwd` — el repo ya tuvo ese bug en un fixture |
| `hallazgo.py` | constructor | sin procedencia → levanta |
| `cobertura.py` | propiedad | `is_complete` es `False` **siempre**, fijado por test, igual que `Coverage` |
| `indice.py` | derivación | el `.md` es función pura de `tests/guards/`; editarlo a mano no sobrevive a la regeneración |
| `calibracion.py` | umbral de `n` | `n` bajo el mínimo → se comporta como `"generico"` y avisa que no sirve para cotizar |
| `instrumento.py` | degradación simulada | el número publicado **no cambia**; lo que cambia es la cobertura |

### 7.3 Dos reglas del repo que aplican tal cual

**Los tests del harness corren sin el harness.** `pytest` verde no puede
depender de que la cosecha haya corrido. Si el harness se cae entero, la suite
sigue siendo la verdad.

**`today` es argumento, nunca `date.today()` adentro.** Regla 4. Acá muerde más
que en ningún lado porque el corpus se ordena por fecha.

---

## 8. Criterio de éxito

El harness sirve si, y sólo si:

1. Reproduce guardias para al menos uno de los 17 bugs históricos, con el
   número exacto publicado (§7.1).
2. Rechaza un test vacuo plantado a propósito (§7.2).
3. Una cosecha sobre evidencia sin lección devuelve cero guardias sin
   inventarse ninguno (§6).
4. `CoberturaGuardia.nota()` nombra lo que el harness no vigila, en la primera
   línea (§6).

Ninguno de los cuatro es una opinión. Los cuatro son tests.

---

## 9. Orden de construcción

Este spec cubre dos capas que se construyen por separado. **Son dos planes de
implementación, no uno.**

**Plan 1 — el contrato y la capa 1.** `fdekit.guard` (`hallazgo`, `guardia`,
`cobertura`), después `tools/harness/` completo, y cierra con el test de
falsificación de §7.1 sobre los 17 bugs históricos.

Es el que va primero porque el criterio de éxito entero vive acá: si el harness
no atrapa ninguno de los 17, la capa 2 no vale la pena.

**Plan 2 — la capa 2.** `instrumento.py` y `calibracion.py`, que consumen el
contrato ya estable y no dependen de una sola línea de `tools/`. Arranca cuando
el plan 1 cerró, y sólo si cerró con al menos un bug histórico atrapado.

La dependencia va en una sola dirección: la capa 2 importa `fdekit.guard` y
nada más. Si el plan 1 se abandona, `instrumento.py` y `calibracion.py` siguen
siendo construibles a mano — sólo se pierde el que los escribe solo.
