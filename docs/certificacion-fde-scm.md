# Certificación FDE-SCM — contenido, unidades y precio

Diseño de un programa de certificación para **Forward Deployed Engineer con
piso de supply chain**, construido sobre `fde-field-kit`. Fecha: 2-ago-2026.

Todo lo que sigue son **propuestas con su razonamiento**, no parámetros
validados. Al final está la lista de lo que hay que medir antes de cobrarle a
alguien, y el criterio de muerte del programa.

---

## 1. Qué se certifica, y qué explícitamente no

**Se certifica:** que la persona puede tomar un log crudo de un WMS, producir un
hallazgo cuantificado que sobreviva a un CFO adversarial, medir el contrafactual,
cotizar el trabajo con un modelo que no miente, y dejar el sitio con trabajo
estándar y un monitor con dueño.

**No se certifica:** conocimiento conceptual de supply chain. Eso ya lo hace
ASCM con CPIM y CSCP, lo hace bien, y competir ahí es perder. La certificación
FDE-SCM **presupone** el dominio o lo delega, y evalúa la **ejecución de un
despliegue**.

Tampoco se promete empleo. El repo entero está construido sobre "no prometemos
resolver siempre; prometemos no mentir nunca en silencio", y una certificación
que insinúa colocación laboral rompe esa regla en la landing page.

### El hueco que llena

Tres evidencias, todas ya levantadas:

1. **El ecosistema FDE documenta cómo conseguir el trabajo, no cómo hacerlo.**
   De los nueve repos de GitHub con más estrellas para "forward deployed
   engineer", ocho son roadmaps, awesome-lists y guías de carrera. El único con
   código de trabajo tiene 12 estrellas y es el demo kit de un vendor
   (`docs/mercado-y-monetizacion.md`).
2. **La crítica de Kinaxis es una descripción de la vacante formativa.** Manik
   Sharma: poner *"ingenieros de 25 años con el cliente"* no aporta el dominio
   de supply chain. Nadie está formando el perfil que responde esa objeción.
3. **El 95% de las organizaciones no obtiene retorno de la IA generativa**
   (MIT NANDA, Media Lab, hallazgos preliminares sobre 52 organizaciones y 300+
   iniciativas públicas), y la causa que da el informe no es técnica: flujos
   frágiles, herramientas que no aprenden del contexto y desalineación con la
   operación diaria. Nuestra lectura agrega una más: nadie definió la unidad
   económica ni el contrafactual antes de empezar. El programa es, literalmente,
   un curso sobre esas causas.

Las certificaciones existentes cubren el concepto (CPIM, CSCP), la metodología
(Lean Six Sigma), o la herramienta de un vendor (Palantir, Kinaxis, Blue Yonder).
Ninguna evalúa **un despliegue completo con evidencia pública**.

---

## 2. Los tres niveles

| nivel | quién | formato | horas sincrónicas | evaluación |
|---|---|---|---|---|
| **1 — Associate** | analista de operaciones, ing. industrial, data analyst en logística | autoestudio + 4 talleres en vivo | 24 h / 4 semanas | 5 entregables corregidos |
| **2 — Professional** | quien va a estar en el piso del cliente | cohorte en vivo | 54 h / 9 semanas | capstone + defensa oral |
| **3 — Architect / Instructor** | quien extiende el kit o enseña | aprendizaje mentoreado | sin horario fijo / 12 semanas | herramienta nueva mergeada + una unidad dictada + revisión adversarial del capstone de otro |

El nivel 2 es el producto. El 1 es el filtro de entrada y el generador de
demanda. El 3 no se abre hasta tener egresados suficientes (ver la compuerta de
volumen en §7).

---

## 3. Las unidades

Horas sincrónicas. El trabajo asincrónico corre entre 1,5× y 2× eso.

### Bloque A — Terreno (Nivel 1, 24 h)

| U | unidad | h | módulo | criterio de aprobación |
|---|---|---|---|---|
| A0 | La tesis y el contrato de datos. Por qué instrumentar la operación y no el software. `case_id, activity, timestamp, resource, location` y por qué negociar un contrato más rico en el kickoff cuesta tres semanas | 3 | — | exporta el contrato desde un sistema real o justifica por escrito qué campo no existe |
| A1 | Gemba cuantificado. Observación estructurada offline, Pareto de desperdicio, `transcribe`. **La regla 1: lo que no está cuantificado no entra al análisis, va a una cola de revisión con dueño** | 6 | `gemba` | 20 observaciones de terreno con duración y frecuencia; la cola de revisión ordenada para una sola vuelta al pasillo |
| A2 | Estudio de tiempos. Ciclos, variación entre operadores, espagueti, mapa de calor. La distancia **no** es euclidiana; el tiempo de servicio se reconstruye desde el recurso | 6 | `timestudy` | espagueti sobre un layout propio + explicación de por qué la recta subestima entre 30% y 200% |
| A3 | Calidad de datos. Muestreo estratificado, IC de Wilson, auditoría física de maestros, y el vínculo χ² defecto→reproceso | 6 | `dataquality` | plan de muestreo con MOE declarado + un `risk_ratio_2x2` interpretado |
| A4 | El A3: el problema en números. Cómo se escribe un hallazgo que no se puede refutar en la sala | 3 | `a3` | A3 que pasa `validate()` |

### Bloque B — Diagnóstico y prueba (Nivel 2, 21 h)

| U | unidad | h | módulo | criterio de aprobación |
|---|---|---|---|---|
| B1 | Process mining. DFG, variantes, conformidad contra el flujo declarado, y **el cuello por tiempo total perdido, no por transición más lenta** — que es el error de quien optimiza sin Teoría de Restricciones | 6 | `processmining` | lista de actividades que ocurren todos los días y no estaban en el kickoff |
| B2 | Simulación. DES calibrado desde el log, Ley de Little, Erlang C, y el barrido que muestra la rodilla del dimensionamiento | 6 | `sim` | el gráfico de la reunión de capex, con la rodilla identificada y el punto donde agregar gente deja de comprar nada |
| B3 | **Línea base y contrafactual.** MDE, tamaño de muestra con ICC, pre/post, diferencias-en-diferencias. Por qué la ventana son semanas y no días | 9 | `baseline` | spec de línea base que el instructor firma **sin devolución**. Si no hay grupo de control posible: escribir por qué y qué le pasa a la banda de atribución |

B3 es la unidad más larga a propósito. Es la que separa este programa de un
curso de herramientas: en la demo del kit, el pre/post naive dice que el
proyecto **empeoró** el ciclo 56%; DiD con control dice que lo **mejoró** 8,7%
(IC95 [-8,5, -1,5] min, p=0,006). Sin grupo de control esa reunión se pierde, y
perderla es el modo de muerte más común de un despliegue.

### Bloque C — Entrega y supervivencia (Nivel 2, 15 h)

| U | unidad | h | módulo | criterio de aprobación |
|---|---|---|---|---|
| C1 | Integraciones. X12 940/945/214/856, contratos de API, husos horarios, idempotencia. Los separadores se leen del sobre ISA, no se asumen | 6 | `probe` | valida un lote de mensajes reales o mutados, incluyendo el socio que usa `\|` |
| C2 | Trabajo estándar. Hojas TWI Job Instruction y runbook de traspaso | 4 | `standardwork` | hoja TWI que un supervisor ejecuta sin el autor presente |
| C3 | SPC y degradación. XmR, 8 reglas de Nelson, **límites congelados** | 5 | `spc` | monitor con dueño nombrado del lado del cliente y justificación escrita de la ventana base |

C2 y C3 son la respuesta con evidencia a la objeción de Anaplan —*"buen modelo
para vender, no para operar"*. Un egresado que no puede producir un traspaso
firmado no puede responderla, y por eso son obligatorias.

### Bloque D — Dinero, decisiones y honestidad (Nivel 2, 18 h)

| U | unidad | h | módulo | criterio de aprobación |
|---|---|---|---|---|
| D1 | El caso económico. Seis palancas trazadas a la herramienta que las mide, cinco arquetipos, Monte Carlo. **Caja ≠ beneficio**: `labor_flex_share` y por qué el caso que asume 1,0 es el que el CFO rechaza. La primera pregunta al cliente es por el **contrato**, no por el país | 6 | `value` | `ValueCase` sin warnings sin responder, contra un arquetipo elegido y defendido |
| D2 | Precio y contrato. La escalera (T&M → fijo → suscripción → hitos → gainshare), piso/techo/verificación escrita, y **por qué `price_band()` se niega** a cotizar gainshare sin contrafactual medido | 3 | `value.pricing` | cotiza dos modelos para el mismo hallazgo y explica cuál no puede ofrecer y por qué |
| D3 | El canal DECIDIDA. **Fase 0 obligatoria: dos semanas con una planilla y en la sala no entra software.** Registro, marcadores verbales, resolutor L0→L1→L2, y por qué no hay L3 | 4 | `decide` | corre una fase 0 de 2 semanas sobre una reunión real y reporta la tasa de declaración con su denominador |
| D4 | Consentimiento y datos. Ley 21.719 (vigente 1-dic-2026), anonimización antes de persistir, propiedad del registro y su uso punitivo | 2 | `decide.schema` | política de retención escrita para el canal HABLADA |
| D5 | **"No falla, miente".** El modo de falla dominante. Auditoría de unidades escrita, una sola anualización, tests que verifican propiedades y no ejecución | 3 | todos | encuentra el bug plantado en un `hallazgos.json` que imprime un VAN perfectamente creíble |

D5 es la unidad que más cuesta enseñar y la que más vale. El repo lleva diez
bugs documentados de esa clase —el `cada 10 minutos` que multiplicaba el impacto
×40, la anualización doble que dejaba L1 y L2 **20% bajas en silencio**, el
`p=0, significant=True` con varianza cero— y todos pasaban los tests. El
ejercicio usa esos casos reales, incluido el hallazgo de auditoría que se anotó
como *"verificado a mano"* y estaba mal.

**Total ruta completa: 78 h sincrónicas** (24 + 54).

---

## 4. Evaluación: el capstone, y por qué no hay examen de opción múltiple

Un examen de opción múltiple mide lo mismo que ya miden CPIM y CSCP, y no mide
nada de lo que este programa dice enseñar. La evaluación es un **despliegue de
90 días comprimido**, sobre el CD sintético del kit o —preferido— sobre datos
del empleador del alumno.

Cinco compuertas, todas pasa/no pasa:

| # | compuerta | qué se verifica |
|---|---|---|
| G1 | **Dato** | log que cumple el contrato, con el denominador expuesto al lado. Nada anualizado antes de `value` |
| G2 | **Triangulación** | dos herramientas independientes que llegan al mismo hallazgo por caminos distintos |
| G3 | **Contrafactual** | DiD con control medido, o la penalización de atribución declarada y aplicada |
| G4 | **Caso** | `ValueCase` cuyas warnings están respondidas por escrito, no silenciadas |
| G5 | **Traspaso** | TWI + monitor con límites congelados y dueño del lado del cliente |

Más una **defensa oral de 45 minutos frente a un CFO adversarial**: un evaluador
cuyo trabajo explícito es refutar el número. Es el mismo método que produjo los
mejores resultados en el repo — el refutador bajó 3 de 4 estimaciones del
estudio de `labor_flex_share`, y en Chile a la mitad.

**No hay certificado de consolación.** Existe una constancia de asistencia, se
llama así, y no da badge ni aparece en el directorio. Un programa que reparte
credenciales a quien no pasó las compuertas se convierte en lo que critica en
dos cohortes.

### La credencial

El problema real de una certificación nueva es que no la respalda nadie. Tres
caminos, en orden de preferencia:

1. **Evidencia pública** — el badge es un enlace al capstone del egresado
   (artefactos, hash del transcripto, spec firmada). Verificable por cualquiera
   sin confiar en el emisor. Es el único activo que un cert nuevo puede
   construir rápido, y es exactamente lo que el mercado de credenciales de papel
   no ofrece.
2. **Universidad** (educación continua: UC, UAI, UNAB) — compra credibilidad y
   canal, cuesta margen y agrega meses de comité.
3. **OTEC / franquicia SENCE** — ver §5, la aritmética no lo justifica para
   este público.

### Recertificación cada 2 años

No es un cobro recurrente disfrazado: los parámetros del kit tienen fecha de
vencimiento real. Jornada 42 h → **40 h en abril 2028**, IMM sube el 1-may-2026,
Ley 21.719 entra en vigencia el 1-dic-2026, tipo de cambio con rango anual de
854 a 932. Un egresado de 2026 que cotiza con esos defaults en 2028 entrega un
caso mal calibrado. Se renueva presentando **un despliegue nuevo** o
re-defendiendo.

---

## 5. Precio sugerido

### Las anclas del mercado

| referencia | precio | qué entrega |
|---|---|---|
| ASCM CPIM (bundle miembro) | ~USD 1.860 · all-in típico 2.000–3.500 | examen de concepto, autoestudio |
| ASCM CSCP (bundle miembro) | ~USD 1.970 | ídem |
| Maven, curso técnico en vivo 6 semanas | ~USD 1.850 | cohorte, sin credencial verificable |
| Maven, rango general | USD 950–3.500 | — |
| Diplomado SCM online 5 meses (UNAB) | CLP 1.700.000 ≈ USD 1.860 | diploma universitario, sin artefacto |

Ninguna de esas entrega un portafolio de despliegue verificable. Ese es el
espacio para cobrar por encima del diplomado y a la par del cohorte técnico.

### La tabla

Dos monedas porque el poder adquisitivo del público chileno/LatAm y el del
público global difieren por un factor de ~2, y cobrar un precio único regala una
mitad o excluye la otra.

| producto | horas | global USD | LatAm USD | Chile CLP |
|---|---|---:|---:|---:|
| **Nivel 1 — Associate** | 24 h | 590 | 390 | 359.000 |
| **Nivel 2 — Professional** | 54 h + capstone | 2.400 | 1.500 | 1.390.000 |
| **Ruta completa (1+2)** | 78 h | 2.700 | 1.700 | 1.590.000 |
| **Nivel 3 — Architect / Instructor** | 12 sem mentoreadas | 4.900 | 3.500 | — |
| **Challenge exam** (capstone + defensa, sin clases) | — | 490 | 350 | 329.000 |
| **Recertificación bienal** | — | 190 | 140 | 129.000 |

**Cohorte 0 a 50%** (LatAm USD 750), declarada como piloto, con el criterio de
muerte publicado antes de vender la primera plaza. Es la fase 0 del propio kit
aplicada al programa.

### B2B — donde está el dinero

| producto | precio | qué incluye |
|---|---:|---|
| Cohorte cerrada, hasta 12 personas | USD 18.000 | las 54 h sobre el CD sintético |
| **Cohorte cerrada + calibración** | **USD 26.000–34.000** | las 54 h **sobre el log real del cliente**, con `--calibration` ajustada a su planilla y su contrato de dotación |

La segunda es la oferta que importa, y no es un curso: **el capstone del equipo
es el diagnóstico del CD del cliente**. Termina con una spec de línea base
firmada, que es precisamente el requisito que `price_band()` exige para poder
ofrecer hitos por resultado o gainshare.

O sea: la capacitación **es la rampa de acceso al modelo de precio de arriba de
la escalera**, y se paga sola con la primera palanca. Vender la certificación
como negocio de contenidos es subvalorarla; es un instrumento de originación.

### Chile: la aritmética de SENCE, que no cierra

Topes 2026: **$5.600/hora-participante** e-learning sincrónico, **$5.000**
presencial. Sobre 54 h → máximo franquiciable **$302.400** por participante.

Pero la cobertura depende del tramo de renta:

| tramo | renta bruta | cobertura | aporte SENCE sobre 54 h |
|---|---|---:|---:|
| alto | ≤ 25 UTM | 100% | $302.400 |
| medio | 25–50 UTM | 50% | $151.200 |
| bajo | > 50 UTM | 15% | **$45.360** |

El público del Nivel 2 —ingenieros y analistas senior— cae mayoritariamente en
el tramo >50 UTM. SENCE aporta **~3% de un precio de $1.390.000**, contra el
costo de operar como OTEC (acreditación NCh 2728, reportería, auditoría).

**Conclusión: no diseñar el programa alrededor de la franquicia.** Sí vale
mencionarla en la propuesta B2B —el tope del 1% de la planilla anual se usa igual
y el descuento es real aunque chico—, y sí cambia el cálculo si alguna vez se
vende una versión para supervisores de turno, que caen en el tramo de 25–50 UTM
con 50% de cobertura.

---

## 6. Economía del programa

Cohorte abierta de 15, mezcla 60% LatAm / 40% global:

```
ingreso    9 × 1.500  +  6 × 2.400            = USD 27.900
plataforma (10%)                              =    −2.790
instrucción 54 h + corrección 15 × 6 h = 144 h
  a USD 100/h de costo de oportunidad         =   −14.400
                                                ──────────
margen por cohorte, régimen                   = USD 10.710
```

Producción inicial: ~240 h (materiales, dataset de ejercicios, rúbricas,
evaluadores). Se amortiza en **~2,5 cohortes**.

El punto incómodo: a una cohorte abierta por trimestre, el programa rinde
~USD 43.000 al año, que es menos que un solo contrato de gainshare de escala
media. **La cohorte abierta es marketing con margen positivo; el ingreso está en
B2B y en lo que B2B origina.** Dos cohortes cerradas con calibración
(USD 60.000) superan un año entero de cohortes abiertas y dejan dos clientes con
línea base medida.

---

## 7. La propia filosofía del kit, aplicada al programa

Sería incoherente vender un curso sobre medir el contrafactual sin medir el del
curso.

**Métrica de resultado, falsable y declarada antes:** porcentaje de egresados
que, dentro de **90 días del cierre**, producen una **spec de línea base firmada
por un sponsor operativo real** (empleador o cliente). No "satisfacción", no
"tasa de finalización" — ambas se autocumplen.

**Criterio de muerte, declarado antes de vender la cohorte 0:** si menos del
**60%** de la cohorte 0 pasa las cinco compuertas, y menos del **35%** produce
una spec firmada a 90 días, no hay cohorte 2. Se arregla el programa o se cierra.
Elegir el umbral después es elegir el que da bien.

**Compuerta de volumen:** el Nivel 3 y el directorio público de egresados no se
abren bajo **30 egresados del Nivel 2**. Un directorio con seis nombres no es una
red, es una lista, y prometer la red el día 1 quema la credibilidad igual que
prometer el grafo bonito antes de las 50 decisiones.

**Lo que no está cuantificado va a la cola de revisión:** cualquier promesa de la
landing page que no tenga medición atrás no se publica. Incluye "mejora tu
empleabilidad".

---

## 8. Riesgos y lo que NO está validado

| # | riesgo | qué haría falta |
|---|---|---|
| 1 | **TAM chico.** ¿Cuántos FDE-SCM hay en Chile? Probablemente decenas. El programa solo funciona si es LatAm + global en inglés, o si el comprador es la empresa y no la persona | contar vacantes reales de 12 meses en CL/AR/MX/CO; el barrido de julio 2026 del usuario es el punto de partida |
| 2 | **Credencial sin respaldo.** Un cert nuevo compite contra ASCM en reconocimiento y pierde | validar con 10 gerentes de operaciones si el portafolio verificable pesa más que la sigla |
| 3 | **Los precios de esta tabla son anclas, no disposición a pagar medida** | 15 entrevistas de precio con el público objetivo, o una landing con precio real y lista de espera |
| 4 | **El B2B con calibración no es un curso: es consultoría con clases adentro.** Puede canibalizar el contrato de diagnóstico que hoy vale más | decidir si es puerta de entrada con descuento o producto propio, y no venderlo a los dos precios |
| 5 | **Capacidad del instructor.** 144 h por cohorte no escalan con una persona; el Nivel 3 existe para eso pero llega después | — |
| 6 | El costo de oportunidad de USD 100/h de §6 es un supuesto | — |
| 7 | Los precios de ASCM varían por tramo de membresía y cambian sin aviso | verificar en ascm.org al momento de publicar la comparativa |

**Lo más importante que falta:** el kit nunca corrió una **fase 0 con gente
real** (`HANDOFF.md`, "lo que NO está hecho"). Enseñar `decide` en la unidad D3
antes de que su propia fase 0 esté validada es vender lo que el repo se niega a
prometer. Dos salidas: correr la fase 0 antes de la cohorte 1, o dictar D3
marcada explícitamente como método no validado, con eso escrito en el material.

---

## Fuentes

- [APICS/ASCM certification comparison chart](https://www.apics.org/docs/default-source/certification/apics-certification-comparison-chart.pdf)
- [CSCP Certification Cost — ISM](https://www.ism.ws/certifications/cscp-certification-cost/)
- [CSCP Exam Fees 2026 — edudelphi](https://edudelphi.com/blog/cscp-exam-fees/)
- [Pricing your course — Maven Help Center](https://help.maven.com/en/articles/6732396-pricing-your-course)
- [How to decide the price & length of your course — Maven](https://maven.com/resources/course-price-and-length)
- [Diplomado en Dirección SCM y Abastecimiento — UNAB](https://postgrado.unab.cl/programas/diplomado-en-direccion-supply-chain-management-y-abastecimiento/)
- [Franquicia Tributaria — SENCE](https://sence.gob.cl/empresas/franquicia-tributaria)
- [SENCE actualiza valor hora para Franquicia Tributaria](https://sence.gob.cl/organismos/noticias/sence-actualiza-valor-hora-para-franquicia-tributaria-mayor-financiamiento-para-capacitacion-de-calidad)
- [Valor Hora SENCE 2026 — OTEC Solutions](https://otecsolutions.cl/valor-hora-sence-guia-completa-para-duenos-de-otecs/)
- Internas: `docs/mercado-y-monetizacion.md`, `docs/calibracion-chile-2026.md`, `README.md`, `HANDOFF.md`
