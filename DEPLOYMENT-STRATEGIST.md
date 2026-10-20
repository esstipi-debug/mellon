# Deployment Strategist (DS) — Doctrina, Perfil y Diferenciación

Este documento formaliza la definición del rol de **Deployment Strategist (DS)**, por qué es el perfil exacto de Marcos Stipicich, cómo resuelve el 95% de fracaso en proyectos de IA corporativa, y los procesos operativos específicos (**Gemba walk, Genchi genbutsu, TWI, guardarraíles deterministas**) con los que aporta valor y se diferencia tanto de los consultores tradicionales como de los ingenieros de software puros.

---

## 1. Qué es un Deployment Strategist (DS)

En la doctrina original de **Palantir** (donde el equipo de campo se organizaba como unidad *Echo* en Business Development), en **OpenAI** (*Technical Deployment Lead - TDL*), y en firmas como **Databricks** o **Sierra AI**, el despliegue en cliente no lo hace un programador solitario. Se divide en dos funciones complementarias:

| Dimensión | Forward Deployed Software Engineer (Delta / FDE) | Deployment Strategist (Echo / DS) |
|---|---|---|
| **Misión central** | Escribir el código, APIs, conectores y pipelines de datos | **Descubrir el problema real, encontrar los datos, vencer la política interna y asegurar la adopción en producción** |
| **Punto de partida** | Recibe especificaciones o contratos de API | **Entra al piso/operación cuando el proceso está desordenado y nadie sabe qué datos sirven** |
| **Métrica de éxito** | Calidad de código, latencia, uptime, cobertura de tests | **Primer dólar de retorno, tiempo al primer hito de valor, tasa de adopción real en piso** |
| **Relación con el cliente** | Habla con ingenieros de datos y arquitectura de TI | **Habla con el gerente de operaciones, el supervisor de bodega, el director de finanzas y el operador** |
| **Frase que lo define** | *"I ship the code."* | *"The DS finds the problem and the dataset; the FDE integrates it. I make adoption stick."* |

> *"A Deployment Strategist identifies high-value problems, navigates organizational politics to secure data access, designs workflows that people actually use, and drives change management through hypercare."* — Doctrina de campo Palantir.

### 1.1. La definición de Ingeniero: *"Ingeniero es aquel que..."*

> *"Científico es aquel que estudia el mundo que existe; **ingeniero es aquel que diseña y hace funcionar soluciones en un mundo que nunca antes existió**."*  
> — Theodore von Kármán (fundador del Jet Propulsion Laboratory, NASA).

* **Definición esencial:** *Ingeniero es aquel que toma principios científicos y herramientas técnicas abstractas, y los hace operar de manera predecible, segura y económica bajo las restricciones implacables del mundo real.*
* **El Foco de Despliegue:** El programador o científico trabaja en abstracto; si el modelo falla en producción, culpa a los datos o al usuario. El **Ingeniero de Despliegue** asume la responsabilidad inversa: si el sistema no funciona en el piso real (Gemba) bajo la fatiga humana y los datos imperfectos, el diseño es el que está defectuoso.
* **Elevator Pitch:** *"Un desarrollador de software tradicional construye el sistema en la oficina y se desentiende de cómo se usa. Un consultor tradicional deja un informe en PDF y se va. Yo soy Ingeniero de Despliegue: cierro la brecha entre la tecnología y el piso operativo. Me meto al centro de distribución, audito la realidad de los datos en terreno, y construyo los puentes, integraciones y guardarraíles necesarios para que el software y la IA corran en producción de forma segura y los operarios realmente lo usen."*

---

## 2. Por qué el 95% de los proyectos de IA fracasan (El problema que resuelve el DS)

La investigación de mercado de este repositorio confirma que el cuello de botella de la IA empresarial **no es el modelo, es el terreno**:

1. **MIT Media Lab / Forbes (2026):** El **95% de los pilotos de IA generativa no entregan valor de negocio** ni llegan a producción. Solo el 5% logra impacto medible en ingresos o eficiencia.
2. **RAND Corporation (estudio sobre fallas de IA):** El **84% de las fallas** se deben a causas organizacionales, falta de liderazgo de negocio, problemas mal definidos y datos no estructurados/sucios.
3. **El "Purgatorio del Piloto" (Nabeel Qureshi, ex-Palantir):** *"Un cliente compra un piloto de 8–12 semanas y el equipo técnico pasa las 12 semanas completas peleando accesos y permisos con TI, para terminar corriendo la última semana parchando una demo que nadie va a usar."*
4. **Principio de Michael Hammer ("Don't Automate, Obliterate"):** Automatizar un proceso roto o caótico solo produce caos a mayor velocidad. Antes de integrar software o IA, el flujo debe ser rediseñado y estandarizado.

---

## 3. Por qué Marcos Stipicich calza en este puesto

El rechazo automático en postulaciones genéricas de "Software Engineer - FDE" (como el caso de ElevenLabs) no responde a una falta de capacidad técnica, sino a un **desajuste de categoría en el ATS**: un bot de screening descarta a quien tiene 13 años de experiencia en operaciones y supply chain buscando un desarrollador de frameworks web.

Sin embargo, para un rol de **Deployment Strategist**, ese historial es la credencial más valiosa:

```
[Consultor Tradicional]          [TU PERFIL: Deployment Strategist Técnico]           [Ingeniero de Software Puro]
Presentaciones en PowerPoint ──► Entiende P&L, entra al piso, corre Python,  ◄────── Escribe código en IDE,
No sabe correr un script         audita logs crudos y construye guardarraíles         no sabe hablar con operarios
y huye del piso de bodega                                                             ni entiende un balance de inventario
```

### La combinación que el mercado no encuentra:
* **La mayoría de los Deployment Strategists** vienen de consultoría estratégica (ex-McKinsey/Bain) o MBAs: tienen visión de negocio y facilidad de palabra, pero **no saben programar**. Dependen de un ingeniero para cada consulta SQL o prueba de concepto.
* **Tú tienes dientes técnicos propios:** Entiendes P&L, presupuestos operativos de USD 15M y rotación de inventarios de USD 100M, pero abres una terminal, corres Python, auditas logs con Monte Carlo, detectas cuellos de botella con SimPy y construyes guardarraíles con HMAC y SHA-256.

---

## 4. Procesos y Herramientas con los que doy valor y me diferencio

### 4.1. Gemba Walk & Genchi Genbutsu (Ir al lugar real de los hechos)
* **El problema habitual:** Las decisiones de software se toman según lo que el manual o la gerencia "dicen" que pasa. En la práctica, el piso opera con atajos, planillas no oficiales y parches informales.
* **Cómo aporto valor:**
  * Aplico **Gemba Walks** estructurados en el centro de distribución o planta de producción. Observo el flujo físico, identifico los cuellos de botella invisibles y hablo directamente con los operadores en su lenguaje.
  * Mapeo el proceso **As-Is real** (lo que la gente hace) frente al **To-Be necesario**, garantizando que el diseño del sistema resuelva fricciones reales y no teóricas.
  * En AGCO Melbourne, este enfoque en terreno permitió el cutover de un WMS a medida a Manhattan sobre 50.000 SKUs con **−20% en tiempos de ciclo**, con una causa documentada: *"because the floor actually used the system"*.

### 4.2. Auditoría Rápida de Datos y Saneamiento de Contratos (`dataquality` & `event logs`)
* **El problema habitual:** Las integraciones de IA se empantanan meses esperando que el cliente termine un proyecto de "Data Lake" o limpie su base de datos.
* **Cómo aporto valor:**
  * No exijo contratos de datos perfectos ni meses de preparación. Como implementé en `mytra-fde` y `fdekit`, inicio el diagnóstico con un log de apenas **5 columnas estándar** (`case_id, activity, timestamp, resource, location`), presentes en cualquier WMS, ERP o TMS del mundo.
  * Corro muestreo estratificado, intervalos de confianza de Wilson y detección de anomalías para saber en 48 horas si los datos soportan una decisión automatizada o si el modelo va a alucinar.

### 4.3. Estandarización de Trabajo y Traspaso Operativo (TWI & Shitsuke)
* **El problema habitual:** El software se entrega, el consultor se va, y a las dos semanas los operarios vuelven a sus libretas y Excels porque la capacitación fue un PowerPoint de una hora.
* **Cómo aporto valor:**
  * Metodología **TWI (Training Within Industry)**: instrucción estructurada de trabajo desglosada paso a paso, con puntos clave y razones de seguridad/calidad.
  * Acompañamiento en **Hypercare y Shitsuke (Sostener)**: permanencia en terreno durante el go-live hasta que la nueva rutina desplaza totalmente a las soluciones alternativas viejas.

### 4.4. Guardarraíles Deterministas para IA (El Patrón Ithildin: Seguridad y Gobernanza para TI)
* **El problema habitual:** Las gerencias de TI y Seguridad vetan los proyectos de IA porque temen que un LLM tome decisiones erróneas, corrompa la base de datos transaccional o viole regulaciones (Ley 21.719 en Chile, GDPR, etc.).
* **Cómo aporto valor:**
  * Arquitectura de **límite estricto**: el modelo de lenguaje solo asiste o redacta; **el motor determinista valida y decide**.
  * Mecanismo de **Safe-staging writeback (Patrón Ithildin)**: tal como formalicé en [`DIRECTRICES-MELLON-ITHILDIN.md`](DIRECTRICES-MELLON-ITHILDIN.md) y en el módulo ejecutable [`fdekit.ithildin`](fde-field-kit/src/fdekit/ithildin/), las propuestas de edición sobre el ERP se clasifican por riesgo (lectura / reversible / irreversible), se congelan en un dry-run firmado con HMAC/SHA-256 y requieren aprobación con ledger de rollback idempotente. TI aprueba el despliegue porque el riesgo de corrupción transaccional es matemáticamente nulo.

### 4.5. Medición Científica de ROI: Línea Base y Contrafactual (`baseline` & Diff-in-Diff)
* **El problema habitual:** La empresa adopta IA pero nadie sabe si el ahorro fue por el software o por estacionalidad, promociones de ventas o rotación de personal (el autoengaño de la comparación naive pre/post).
* **Cómo aporto valor:**
  * Diseño de experimentos con **Diferencias en Diferencias (Diff-in-Diff)** y chequeo de tendencias paralelas (como en el módulo `baseline` de `mytra-fde`).
  * Demuestro con rigor estadístico (p-valores e intervalos de confianza al 95%) el impacto real del despliegue, justificando la inversión ante el CFO y asegurando el retainer del 15–20% anual.

---

## 5. Resumen de Posicionamiento

| Frente a... | Mi diferenciador como Deployment Strategist |
|---|---|
| **El Consultor de Negocio (Big 4 / McKinsey)** | Yo no me quedo en la recomendación teórica ni delego la ejecución técnica: diagnostico en piso, audito datos crudos con código propio y dejo software corriendo en producción. |
| **El Ingeniero de Software Tradicional** | Yo no me frustro con la política corporativa ni exijo que me entreguen datos limpios: voy al Gemba, destrabo los permisos, gano la confianza del operador y garantizo que el software se use. |
| **El Vendedor de SaaS / Startups de IA** | Yo no vendo licencias vacías ni pilotos que mueren en 90 días: vendo adopción real, gobernanza sin riesgo y valor medible en P&L. |

---

## 6. Validación Externa de Mercado: Guía FDE Pulse (2026)

Documento de referencia: [`investigacion/fde-pulse-forward-deployed-strategist.md`](investigacion/fde-pulse-forward-deployed-strategist.md) (Rome Thorndike, CEO de Provyx / *FDE Pulse*, 2026).

La industria formalizó la separación entre **FDE** (Forward Deployed Engineer) y **FDS** (Forward Deployed Strategist):
1. **El rol existe formalmente:** Contratado en Palantir, ElevenLabs, Salesforce (*Agentforce Strategy Lead / Customer Success Architect*), Workhelix y consultoras boutique de IA como WON (*AI Strategist*).
2. **Explicación del screening ATS:** Los FDE puros provienen de ingeniería de software y escriben código de producto. Los FDS provienen de operaciones, consultoría o producto, y lideran scoping, C-suite, caso de negocio y adopción.
3. **El Unfair Advantage de Marcos:** El mercado reporta que los FDS típicos vienen de consultoría (McKinsey/Bain) y *no programan*. Marcos posee la visión de negocio y P&L de un FDS, pero con la capacidad técnica de auditar logs con Python, construir guardarraíles y desplegar herramientas nativas de IA.
4. **Banda Salarial:** Base de **USD $120.000 a $220.000**, con compensación total en Palantir de hasta **USD $250.000–$350.000**.
5. **Compendio Maestro de Ofertas de Mercado:** Análisis detallado de las vacantes activas en Databricks, Palantir, OpenAI, ElevenLabs, WON, Salesforce y Workhelix en [`investigacion/compendio-ofertas-ds.md`](investigacion/compendio-ofertas-ds.md).


