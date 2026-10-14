# Gemba walk — el método, y en qué se diferencia del kit

Verificado el **7 de agosto de 2026**. Cada afirmación lleva su marca: `[CITA]`
es texto textual de la fuente, `[PARÁFRASIS]` es resumen de contenido leído,
`[INFERENCIA]` es razonamiento propio, `[NO VERIFICADO]` es algo que no se pudo
confirmar en una página real. Las fuentes están al final.

```bash
python -c "from fdekit.gemba import GembaSession; print(GembaSession('g.jsonl', site='CD Pudahuel').checklist())"
```

Este documento es la **doctrina**; `src/fdekit/gemba/` es su forma ejecutable.
Cuando los dos no coinciden, gana el código y este archivo es el bug.

---

## 0. Por qué el kit tiene un módulo de gemba

`fdekit.gemba` es la herramienta 1 de nueve, y la única que no lee ningún
sistema del cliente. Eso no es una curiosidad: es el punto.

El resto del kit instrumenta el **software**. Esta herramienta instrumenta la
**operación**, que es lo que decide si el despliegue sobrevive al mes 3
([README](../README.md)). Un log del WMS registra lo que tuvo transacción. No
registra buscar el carro, esperar al supervisor, la planilla paralela, ni el
traslado que nadie escanea — y esas cuatro cosas son exactamente donde vive el
hallazgo que justifica el proyecto.

`[CITA]` Jimmy Bogard, *The Gemba Walk for Designing Software*:

> "My Gemba Walks are the very first thing I do on a new project."

> "So, as software developers, we have to get out of our chairs and go to the
> work being done if we want to build applications and systems that can truly
> transform an organization."

`[PARÁFRASIS]` El mecanismo de falla que describe es preciso: cuando dependés
solo de los "domain experts", no ves el proceso *real*. La gente que trabaja
dentro del proceso no nota que "ese proceso simple de 3 pasos en realidad tiene
10", y omite pasos manuales al describirlo — no por mentir, sino porque normaliza
las excepciones.

---

## 1. Definiciones, y las dos cosas que se confunden

| Término | Definición (Lean Enterprise Institute) | Naturaleza |
|---|---|---|
| **Gemba** (genba) | `[CITA]` "The Japanese term for 'actual place,' often used for the shop floor or any place where value-creating work actually occurs." | Un **lugar** |
| **Genchi genbutsu** | `[CITA]` "Going to the source to check facts for yourself so you can be sure you have the right information you need to make a good decision." | Una **acción** |
| **Gemba walk** | `[CITA]` "a management practice for grasping the current situation through direct observation and inquiry before taking action." | Una **práctica** |

Las tres definiciones son del léxico del LEI, y se citan tal como quedaron
verificadas en `mytra/mytra-context/claude/fde-metodologias-diagnostico.md`; no se
reabrieron contra la fuente en esta sesión.

`[PARÁFRASIS]` El LEI distingue dos visiones. *Gemba* es **sincrónico**: ves el
problema en el lugar de trabajo, lo arreglás, seguís; prioriza excelencia
operacional vía estandarización. *Genchi genbutsu* es **diacrónico**: buscás
mejorar y aprender qué **está ausente** — lo que podría existir y no existe;
prioriza innovación y aprendizaje continuo.

`[INFERENCIA]` Para un FDE la distinción decide qué hacer con las dos horas.
El discovery de un despliegue **no es un gemba de tipo "arreglar el problema
visible"**: es genchi genbutsu. Estás buscando el trabajo que *no se está
haciendo* porque nadie tiene la capacidad de hacerlo — la decisión que nadie
toma porque no hay datos, la excepción que se resuelve por WhatsApp. Un walk que
solo produce una lista de cosas rotas que cualquiera ve desde la oficina no pagó
el pasaje.

`[CITA]` El LEI cierra la definición del walk como "a way to understand work,
lead, and learn" — herramienta de observación, práctica de liderazgo y mecanismo
de aprendizaje a la vez, no una inspección.

### 1.1 Las tres cosas que Womack separa bajo el mismo nombre

`[PARÁFRASIS]` No todo lo que se llama "gemba walk" sirve para lo mismo:

1. **Value stream walk** — `[CITA]` "to raise consciousness about the
   possibilities for dramatic end-to-end improvement (kaizen or kaikaku, as you
   will)". Cruza departamentos y organizaciones.
2. **Management system walk** — evalúa si el sistema de gestión diaria mantiene
   estabilidad y soporta mejora. Mira cómo los managers resuelven problemas *vía
   el sistema*, no personalmente.
3. **Management by walking around** — directivos saltándose los canales normales.
   Womack lo cuestiona: `[CITA]` "why do top-level managers and improvement
   staffs need to race to gemba too to fight fires?"

`[INFERENCIA]` **El FDE hace el tipo 1.** Es el único de los tres que produce el
insumo que necesita: un mapa end-to-end del flujo real. Los tipos 2 y 3 son
prácticas de management del cliente, no de discovery. Confundirlos es la forma
más común de gastar un día de terreno en una reunión de pie.

### 1.2 Por qué "ya recorrimos el CD con el gerente" no cuenta

La cita más dura sobre esto es de Deming, *Out of the Crisis* (1982), reproducida
en dos fuentes independientes:

> `[CITA]` "Management by walking around is hardly ever effective. The reason is
> that someone in management, walking around, has little idea about what
> questions to ask, and usually does not pause long enough at any spot to get the
> right answer."

| Dimensión | Gemba walk | MBWA |
|---|---|---|
| **Objetivo** | Proceso específico, observación detallada | Visibilidad general, construir relación |
| **Destino** | Predeterminado, para observar una actividad puntual | Deambular sin destino definido |
| **Táctica** | Preguntas estructuradas y profundas | Sin profundidad; evita preguntas abiertas |
| **Resultado** | Ítems de mejora documentados, con dueño y fecha | Cambios inmediatos no planificados, a veces contraproducentes |

---

## 2. El protocolo: antes, durante, después

Esta es la parte que la certificación enseñó y que el kit **implementa a
medias a propósito**. La tabla dice qué hace el kit en cada paso y, cuando no lo
hace, por qué.

### 2.1 Antes — preparación

| Paso del protocolo | Qué hace el kit | Comentario |
|---|---|---|
| **Definir el objetivo** | Nada | Es decisión humana, y es la que más se saltea |
| **Elegir área y proceso** | `GembaSession(site=...)` y el campo `area` de cada `Observation` | El área es obligatoria en el esquema |
| **Armar equipo** | Nada | `observer` es un campo de texto, no un roster |
| **Comunicar la intención** | Nada | Ver la tensión de abajo: no es solo cortesía |
| **Preparar preguntas** | `GEMBA_QUESTIONS`, impresas por `.checklist()` | Seis preguntas fijas, en la voz del operador |
| **Consentimiento** | Nada en el código | Es precondición de proceso, no un flag |

`[INFERENCIA]` **La tensión que el protocolo no resuelve: comunicar la
intención y medir el efecto Hawthorne son objetivos opuestos.** Avisar antes
reduce la ansiedad del operario y es lo ético; también cambia su comportamiento,
que es exactamente lo que el manual prohíbe hacer con la línea base
(`C:\fde\MANUAL-FDE.md` §7.3, fuera de este repo). La resolución que sostiene
este kit:
**el gemba no produce la línea base.** Produce la lista de lo que el log no ve.
La línea base sale del log, que no sabe que lo estás mirando. Si un hallazgo de
gemba necesita número duro, el número se busca en el log, no en la observación.

`[CITA]` Womack sobre el checklist, y es una advertencia contra el propio kit:

> "a loose structure and the opportunity to follow every question wherever it
> leads is actually very useful in uncovering problems."

> "The best answer to this question is the answer that works for you in your
> organization."

`[INFERENCIA]` Las seis preguntas del kit no son las cinco de Womack, y la
diferencia es deliberada. Las de Womack (*¿cuál es el propósito de este proceso?
¿quién es responsable? ¿está logrando su propósito?*) son para un practicante
experimentado evaluando un proceso, y se contestan **mirando**. Las del kit son
para el **operador, en su turno**, y se contestan **preguntando**. Son
complementarias: Womack te da la estructura mental, el kit te da el guion. Ir con
las de Womack y sin las del kit produce una conversación con el supervisor.

### 2.2 Durante — observación

| Paso del protocolo | Qué hace el kit |
|---|---|
| **Seguir el proceso de principio a fin** | Nada — el orden de las observaciones lo da el observador |
| **Identificar el desperdicio** | `WASTE_TYPES`: los 7 + talento. `classify_waste()` sugiere desde el audio |
| **Involucrar al operario** | `operator_quote` guarda su frase textual |
| **Preguntas abiertas** | `GEMBA_QUESTIONS` |
| **Tomar notas** | `Observation` con `area`, `activity`, `description`, `photo_ref` |
| **NO hacer cambios en el momento** | Nada — y es la parte que el kit no puede impedir |

**La regla dura del kit:** toda observación necesita **duración y frecuencia**.
`Observation.quantified` exige las dos, y lo que no las tiene no entra al Pareto
— va a `unquantified()`, que es la lista de tareas del próximo turno. El
comentario en `capture.py` lo dice sin adornos: *"obliga a volver al terreno a
medir en vez de discutir con anécdotas"*.

`[INFERENCIA]` Esta regla es la corrección más importante al protocolo de
certificación. *"Tomar notas"* es una instrucción que no se puede verificar;
*"duración y frecuencia, o va a la cola"* sí. Un checklist que pide "anotar los
desperdicios" produce prosa que nadie puede agregar el viernes.

**El campo que decide si la observación vale plata: `in_event_log`.** `[CITA]`
el comentario de `schema.py`:

> Casi todo lo que se observa en un pasillo YA está en el log bajo otro nombre:
> "buscar un SKU que no está" es PICK_EXCEPTION_LOCATION, "rehacer el cartón" es
> CARTON_REWORK, "esperar pedidos liberados" es la espera de la transición
> ORDER_RELEASED -> PICK. Sumar esas horas a las que ya aporta `timestudy`
> duplicaría la palanca L1 entera.

Solo `counts_for_value` —cuantificada **y** declarada fuera del log— entra al
caso económico. Y `None` significa "no se declaró", no "no está": va a
`pending_log_status`, la cola de revisión. Un default de `True` o `False`
decidiría en silencio si la observación vale plata, que es lo que la regla 1 del
repo prohíbe.

### 2.3 Después — el seguimiento, que es donde muere

`[PARÁFRASIS]` El protocolo de certificación pide: revisar hallazgos,
identificar quick wins, desarrollar un plan de acción, asignar responsables,
agendar seguimientos. Y remata con la frase que importa: **sin seguimiento, la
mejor observación se pierde** y el impulso del walk se disipa.

`[INFERENCIA]` El kit resuelve esto por una vía distinta a la de una consultora,
y conviene ser explícito sobre la diferencia. Un plan de acción con "responsable"
y "fecha" en una plantilla es una promesa; en este repo el equivalente es
`fdekit.decide`, donde un compromiso sin `decision_id` **no se registra**, un
dueño fuera del roster **se rechaza**, y un criterio sin número o predicado
verificable **no pasa `validate()`**. El gemba produce observaciones; la acción
sobre ellas vive en el canal DECIDIDA, con las mismas compuertas que cualquier
otra decisión.

Lo que el kit **no** hace, y es deliberado: no convierte una observación en una
orden de trabajo, y no asigna dueños. `unquantified()` y `pending_log_status`
son colas con dueño **humano**; el software solo se niega a que desaparezcan sin
que nadie las mire.

---

## 3. Los desperdicios: muda, muri, mura — y por qué buscar solo muda es el error

`[PARÁFRASIS]` Los **siete desperdicios** los describió **Taiichi Ohno**
(*Toyota Production System*, 1988). El octavo —talento o creatividad no
utilizada— es de atribución **disputada**: circula como "el octavo desperdicio"
en la literatura de Lean Six Sigma, pero no hay una fuente primaria única que lo
fije. `[NO VERIFICADO]` No se pudo confirmar autoría. El kit lo incluye igual
(`WASTE_TYPES["TALENTO"]`) porque en un CD es el desperdicio más caro y el más
fácil de observar: *"gente que sabe la solución y nadie le pregunta"*.

| # | Desperdicio | Definición operativa (`WASTE_TYPES`, en vocabulario de CD) |
|---|---|---|
| 1 | **TRANSPORTE** | mover material sin transformarlo (traslados entre zonas) |
| 2 | **INVENTARIO** | stock parado, WIP acumulado, pallets esperando |
| 3 | **MOVIMIENTO** | movimiento del operador sin valor (buscar, agacharse, caminar) |
| 4 | **ESPERA** | operador o material esperando (cola, autorización, sistema lento) |
| 5 | **SOBREPRODUCCIÓN** | preparar antes de tiempo, olas liberadas de más |
| 6 | **SOBREPROCESO** | pasos que el cliente no pide (doble digitación, doble control) |
| 7 | **DEFECTO** | error que obliga a rehacer (mal picking, mal cartón, mal rótulo) |
| 8 | **TALENTO** | gente que sabe la solución y nadie le pregunta |

### 3.1 La corrección que la certificación no hace

`[PARÁFRASIS]` Darren Walsh (Lean Enterprise Academy) describe el error que ve
en organizaciones que ya tienen rutinas formales de gemba walk, con asistencia
disciplinada de todo el equipo gerencial: **pasaban caminando al lado de los
problemas de desempeño del negocio sin una sola conversación**, más preocupados
por el orden, la limpieza, la presencia del personal y por completar la rutina.
Su consejo:

> `[CITA]` "**Stop looking for muda (non value added work)**. If you look deep
> enough you are likely to find thousands of examples of waste, issues and
> problems. Instead, focus on finding muri (overburden) and mura
> (variation/unevenness), and check that the frontlines are dealing with muda
> reduction and observing value flow."

> `[CITA]` "**Stop focusing on people being busy and efficient.** Instead focus on
> value-stream effectiveness; otherwise you will end up hiding many of your
> biggest opportunities or driving point improvement."

`[INFERENCIA]` **Esto contradice frontalmente el material de certificación**, que
define el objetivo del walk como "identificar los 7 desperdicios". Y la razón por
la que Walsh tiene razón es aritmética, no filosófica: hay infinitos ejemplos de
muda. Un walk que busca muda produce una lista larga, heterogénea y sin
denominador — el insumo exacto del que este repo desconfía. **Muda es el
síntoma; muri y mura son la causa.** El operario que camina de más (muda) es
consecuencia de un layout que lo sobrecarga (muri) o de una ola que llega
despareja (mura). Corregir el muda sin tocar el muri garantiza que el muda
vuelva con otra forma.

**La traducción al kit, y es una limitación real:** `WASTE_TYPES` clasifica
**muda**. El kit no tiene un campo para muri ni para mura, y `classify_waste()`
solo reconoce los ocho tipos. `[INFERENCIA]` La consecuencia práctica es que la
distinción se sostiene en el campo `root_cause` (y en `five_whys`), no en el
tipo de desperdicio. Un `waste_type` dice *dónde* duele; el `root_cause` dice
*por qué*. Un Pareto ordenado por `waste_type` sin el `root_cause` poblado es una
lista de síntomas con buena tipografía.

### 3.2 La pregunta que precede a "¿cómo lo usamos?"

`[PARÁFRASIS]` Sammy Obara (ex Toyota, 16 años en TPS) señala que los líderes
creen que copiando las herramientas de Toyota obtienen los resultados de Toyota.
Su ejemplo es Kanban: Toyota creó una solución para un problema **que Toyota
tenía**, y muchas empresas que no tienen ese problema la adoptan igual.

> `[CITA]` "Perhaps the question that comes before 'How do I use it?' should be
> 'Why do they use it?'"

`[INFERENCIA]` Para un FDE, esta es la razón por la que este documento **no es
una plantilla para copiar**. El gemba walk del kit está calibrado para un centro
de distribución: las preguntas están en jerga de bodega chilena y el Pareto se
mide en turnos. Llevado a una mesa de atención al cliente o a un proceso de
compras sin traducir, produce la versión consultora del error de Obara —
la ceremonia sin el problema.

---

## 4. Anti-patrones

Los siete primeros son doctrina verificada. El octavo es específico de este rol.

| Anti-patrón | Evidencia |
|---|---|
| **Convertirlo en auditoría** | `[CITA]` LEI define el gemba walk "rather than a simple inspection activity". El framing de auditoría cambia el comportamiento del operario y destruye el dato |
| **Ir sin propósito (= MBWA)** | Deming: no sabés qué preguntar y no te quedás lo suficiente |
| **Corregir en el momento** | `[PARÁFRASIS]` KaiNexus: el walk produce ítems documentados con dueño y fecha; el MBWA produce "immediate, unplanned changes that may be counterproductive" |
| **Checklist rígido cuando buscás el panorama** | Womack: la estructura suelta es la que descubre problemas |
| **Observar una sola vuelta del ciclo** | `[CITA]` AllAboutLean: "even for highly cyclical work, following only one round is definitely not enough" |
| **Confiar solo en el dato del sistema** | La observación física revela problemas que el dato no muestra |
| **No pedir consentimiento** | AllAboutLean pide consentimiento del trabajador **y** aprobación del comité de empresa antes de observar |
| **Ir con la solución ya vendida** | `[INFERENCIA]` Si ya se firmó "vamos a poner un LLM en el customer service del CD", el walk se degrada en búsqueda de justificación. El walk solo tiene valor si el resultado puede ser "esto no se soluciona con software" |

### 4.1 El anti-patrón que describe LEI y que es idéntico al del FDE

`[PARÁFRASIS]` Alice Lee (ex directora del LEI) describe el modo de falla así: los
líderes creen que tienen que tener todas las respuestas, y eso no cambia en el
gemba walk. El punto del walk es "Go and See (and listen)", pero los líderes
luchan con el "ver y escuchar" porque están más cómodos con el "hacer y decir".
Le resulta **extremadamente incómodo** ver errores ocurriendo delante suyo sin
poder corregirlos.

`[CITA]` Lo que Lee discute con el líder antes de salir:

> "You don't have to have all the answers. You're going to see problems, you're
> going to see things that might make you nervous, and you're going to want to
> jump in and fix it. But I need you to just go in with a questioning and
> nonjudgmental mindset and think, 'What is actually happening? What am I
> actually seeing and what do I now know? What else do I need to know and how
> will I learn it?'"

`[INFERENCIA]` Un ingeniero de software en el piso del cliente es esa misma
persona con otra camiseta. Ver un `UPDATE` manual a las 3 de la mañana produce
el mismo impulso de saltar y arreglarlo — y arreglarlo en el momento destruye
tres cosas a la vez: la observación, la confianza del operario, y la posibilidad
de que el workaround sea el requisito real que nadie escribió. La frase de Lee
es el mejor script de preparación que tiene este kit, y no está en el código.

---

## 5. Servicios y software: el "office gemba"

`[PARÁFRASIS]` El material de certificación extiende el walk fuera de
manufactura con tres ejemplos, y el inventario del repo se llama *"inventory"*
porque en un servicio no hay pallets:

- **Manufactura** — un operario esperando material revela un problema de timing
  de la cadena de suministro que el dato no mostraba.
- **Oportunidad de automatización** — operadores haciendo pasos manuales dentro
  de un proceso ya automatizado (mover material entre estaciones que una cinta
  podría mover).
- **Servicio** — empleados de cara al cliente peleando con tecnología obsoleta,
  lo que produce más tiempo de respuesta y más espera del cliente.

`[INFERENCIA]` La traducción de los siete desperdicios a un proceso de servicio
—y a un proceso de software— es directa si se cambia "material" por
"información":

| Desperdicio | En un CD | En un proceso de servicio o de software |
|---|---|---|
| Transporte | traslado entre zonas | reenviar el mismo dato entre sistemas por correo o planilla |
| Inventario | pallets esperando | tickets abiertos, ramas sin mergear, trabajo a medias |
| Movimiento | buscar, agacharse, caminar | buscar el dato en tres sistemas, cambiar de herramienta |
| Espera | cola, autorización, sistema lento | aprobación, build lento, esperar al que sabe |
| Sobreproducción | preparar antes de tiempo | reportes que nadie lee, features que nadie pidió |
| Sobreproceso | doble digitación, doble control | doble carga del mismo campo, doble aprobación |
| Defecto | mal picking, mal cartón | dato malo en el maestro, reintento, retrabajo |
| Talento | nadie le pregunta al que sabe | el workaround que el operario diseñó y nadie documentó |

`[NO VERIFICADO]` No se encontró literatura académica revisada por pares sobre
gemba walk aplicado específicamente a despliegue de IA. Las búsquedas de "gemba
walk AI" devuelven mayoritariamente **la dirección inversa** — usar analítica de
video para *hacer* gemba walks. Cruzar "forward deployed engineer" con
lean/gemba devuelve avisos de empleo, no contenido metodológico.

---

## 6. El ciclo de captura del kit, en concreto

```python
from fdekit.gemba import GembaSession, Observation, transcribe_to_session

s = GembaSession("gemba.jsonl", site="CD Pudahuel", observer="FDE")

# En el pasillo, sin wifi: append-only a JSONL local.
s.add(Observation(
    area="Picking", activity="buscar SKU faltante", waste_type="MOVIMIENTO",
    description="el picker recorre dos pasillos porque la ubicacion del WMS esta vencida",
    duration_s=95, frequency_per_shift=14, operators_affected=1,
    in_event_log=None,          # no se declaro -> cola de revision
    operator_quote="el sistema me manda al 4 y esta en el 9",
))

# El audio del pasillo entra por la misma puerta.
agregadas, por_revisar, avisos, cobertura = transcribe_to_session(
    "turno1.m4a", s, area="Picking", shift="mañana", anonymize=("Rodrigo",)
)

print(s.pareto())          # ordena por horas/turno; sin cuantificar no entra
print(s.unquantified())    # la lista de tareas del proximo turno
print(s.value_input())     # lo que aporta al caso economico, solo fuera del log
```

**Leer esa salida con cuidado, porque es el punto entero del campo.** Con
`in_event_log=None` el ejemplo da `pareto` = 0,3694 h/turno y, a la vez,
`value_input` = **0,0 h/turno** con `pending_log_status = 1`. No es un bug: la
observación se ve, se cuenta y se discute con el supervisor —pero **no se cobra**
hasta que alguien declare si ese recorrido ya deja rastro en el log. Callarlo y
sumarlo igual sería inventar plata; el `0,0` es la regla 1 funcionando.

Cuatro propiedades que hacen que esto no sea una libreta digital:

1. **Offline y append-only.** En los pasillos de un CD no hay wifi, y una
   herramienta que necesita conexión para registrar una observación no se usa —
   se vuelve a la libreta (`capture.py`).
2. **El Pareto ordena por horas/turno, no por frecuencia.** Un desperdicio que
   pasa mucho y dura poco no es el mismo problema que uno raro y caro.
3. **La unidad es el turno observado, no el año.** La anualización es una sola y
   vive en `value/levers.py`. El `* 250` que vivía en `schema.py` era
   anualización doble y se eliminó en `4898ca9`.
4. **Nada con identidad sale del proceso.** El `marker_id` se hashea con una sal
   de sesión que nunca se escribe a disco, y toda la salida pasa por
   `field.privacy.gate_output`.

`[INFERENCIA]` La propiedad 2 y la regla de duración+frecuencia son la misma
idea dos veces: **el kit está construido para no poder producir un Pareto de
anécdotas.** Esa es su contribución real al método. El resto del gemba walk se
puede enseñar en una hora; lo que no se enseña es la disciplina de no agregar lo
que no se midió.

---

## 7. Las tres cosas que este documento no resuelve

`[INFERENCIA]` Enumerarlas vale más que aparentar cobertura:

1. **El sesgo de selección de la muestra.** El observador elige *qué* mirar, y
   el sesgo de saliencia —se observa el caso llamativo— es el dominante en
   gemba. **Ningún sensor arregla esto**, y ninguna cantidad de micrófonos
   tampoco. La única defensa es declarar el criterio de muestreo antes de entrar
   al pasillo.
2. **La frecuencia estimada por recuerdo.** El factor más sesgado de los tres
   que multiplican el impacto; ±100% es normal. Un turno fijo de 8 h
   (`SHIFT_HOURS`) agrega −25%/+50% en CDs con turno de 6 o 12 h. La frecuencia
   de un evento **con transacción** es un conteo del log, no una estimación: si
   el WMS lo registra, no se le pregunta al operario.
3. **La clasificación de desperdicio con léxico de keywords.** `WASTE_LEXICON`
   es jerga chilena de bodega y no transfiere a otro país. Y `Draft.confidence`
   no es una probabilidad: con un solo keyword da 1,0. Un modelo de lenguaje lo
   haría mejor y **rompería la restricción de correr sin GPU**, que es
   estructural en este kit.

---

## Fuentes

**Lean Enterprise Institute (primarias)**
- https://www.lean.org/lexicon-terms/gemba-walk/ — definición de gemba walk
- https://www.lean.org/the-lean-post/articles/gemba-workplace-genchi-genbutsu-go-and-see-whats-the-difference/ — gemba vs. genchi genbutsu
- https://www.lean.org/the-lean-post/articles/gemba-walk-checklist/ — Womack, las 5 preguntas y el reparo al checklist rígido
- https://www.lean.org/leanpost/Posting.cfm?LeanPostId=906 — los tres tipos de walk
- https://www.lean.org/the-lean-post/articles/what-too-many-lean-leaders-forget-about-gemba-walks/ — Darren Walsh, *muda* vs. *muri*/*mura* · `[CITA]` verificada 7-ago-2026
- https://www.lean.org/the-lean-post/articles/advice-from-the-gemba-top-mistakes-lean-leaders-make-i/ — Alice Lee (ver y escuchar), Sammy Obara (¿por qué lo usan?) · `[CITA]` verificada 7-ago-2026

**Gemba práctico y crítica**
- https://www.leanblog.org/2011/10/dr-deming-on-management-by-walking-around/ — Deming, cita de *Out of the Crisis*
- https://blog.kainexus.com/improvement-disciplines/lean/gemba-walk/the-difference-between-gemba-walks-and-management-by-walking-around — tabla gemba vs. MBWA
- https://www.allaboutlean.com/spaghetti-diagrams/ — consentimiento, una sola vuelta no alcanza

**Origen de los desperdicios**
- Ohno, T. *Toyota Production System: Beyond Large-Scale Production* (1988) — los siete desperdicios. Confirmado como fuente en literatura académica indexada (p. ej. *CITPM 2018*, wz.pcz.pl)

**Material de certificación Lean Six Sigma (origen de la §2 y §3)**
- El ciclo antes/durante/después y la checklist de quick wins provienen de material de certificación Lean Six Sigma de divulgación (familia de sitios de certificación tipo GoLeanSixSigma / Six Sigma Online). `[NO VERIFICADO]` No se pudo fijar la página exacta: `goleansixsigma.com` respondió 403 y las copias consultadas son derivadas. Se usa como **material de certificación**, no como fuente primaria, y §3.1 lo corrige contra LEI.

**No verificables / disputadas**
- Autoría del **octavo desperdicio** (talento): `[NO VERIFICADO]`, sin fuente primaria única.
- **Los "ocho pasos de la visita al gemba"** que describe una tesis de maestría de la Universidad de Malasia Pahang (`umpir.ump.edu.my/id/eprint/38992`): la fuente existe —el buscador devuelve su texto— pero el PDF **no se pudo abrir** (fallo de descarga), así que los ocho pasos concretos **no se pudieron verificar** y no se incluyen. La única frase recuperada es: `[CITA]` "The eight steps that are required to be taken when visiting Gemba are depicted in Figure 3.5", y remite a una figura que no se pudo leer.
- Literatura académica revisada por pares sobre gemba walk aplicado a despliegue de IA: **no encontrada**. Las búsquedas devuelven mayoritariamente la dirección inversa (analítica de video *para hacer* gemba walks).
- `leanproduction.com/gemba-walk/` — 404 al 7-ago-2026.
- `sixsigmaonline.org/gemba-walk-lean-six-sigma/` — responde 200 pero el cuerpo llega truncado; no se pudo citar textualmente.
