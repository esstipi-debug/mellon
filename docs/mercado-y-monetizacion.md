# Mercado del FDE y monetización del trabajo

Dos partes: qué dice la literatura y el ecosistema sobre el rol (agosto 2026), y
el modelo económico que implementa `fdekit.value` para cuantificar y cobrar.

---

## Parte 1 — Lo que dice el ecosistema

### Palantir: el modelo y sus críticos

El negocio comercial de Palantir llegó a **46% de los ingresos (~USD 2.100M)**,
partiendo de tres clientes comerciales en 2022. Muchos de esos despliegues son
de supply chain. El FDE mide el éxito por **impacto sobre la meta del cliente**
—reducir defectos que salen de la línea, no entregar features— y con el tiempo
la lógica que parecía específica de un cliente se sube al producto.

Las dos críticas serias, ambas de competidores directos que aparecen en la
lista de prospectos:

**Anaplan (Charlie Gottdiener, CEO):** *"Es un buen modelo para vender... No es
un gran modelo para operar el software."* El argumento es dependencia: el
cliente queda atado a los ingenieros del proveedor para cualquier cambio.

> Es una objeción correcta cuando el FDE no deja trabajo estándar ni runbook.
> Las herramientas 8 y 9 del kit existen para poder responderla con evidencia:
> hojas TWI firmadas y un monitor de degradación con dueño del lado del cliente.

**Kinaxis (Manik Sharma, ex-Palantir):** poner *"ingenieros de 25 años con el
cliente"* no aporta el dominio necesario en conceptos de supply chain.

> Esta es, literalmente, la descripción del hueco que llena un perfil con piso
> de CD, OR aplicada y código en producción. No es una crítica al rol: es una
> crítica a quién lo ocupa. Vale citarla en un primer correo.

**El dato incómodo:** el reporte del MIT Media Lab (2025) sobre 300+ despliegues
encontró que **el 95% de los pilotos de IA generativa no entrega valor de
negocio medible**. La causa dominante no es técnica. Es que nadie definió la
unidad económica ni el contrafactual antes de empezar — que es exactamente lo
que resuelven las herramientas 4, 6 y 9.

### Quién contrata y cómo trabaja

Del análisis de Pragmatic Engineer: Palantir (el mayor empleador), OpenAI (10+
FDEs en 8 ciudades de 3 continentes en 2025), Ramp (~15 en *pods*), Salesforce,
Commure, Gecko Robotics, Lindy.

Definición de consenso: equipos chicos que **poseen la ejecución punta a punta
de proyectos de alto riesgo**, alternando entre trabajo embebido en el cliente y
contribuciones al producto. Entre **25% y 50% del tiempo en sitio** según la
empresa. Escriben código sobre la infraestructura del cliente y ayudan a cerrar
ventas probando viabilidad.

Ninguna de las fuentes publica **cómo se cotiza ni cómo se factura** el trabajo
del FDE. Ese vacío es lo que motiva la parte 2.

### GitHub: el hallazgo es lo que NO hay

Búsqueda de repos con "forward deployed engineer", ordenados por estrellas:

| repo | ⭐ | qué es |
|---|---|---|
| `xdash/FDE-the-Guidance-Book-of-Forward-Deployed-Engineer` | 896 | guía de carrera (chino) |
| `pierpaolo28/Awesome-FDE-Roadmap` | 685 | roadmap |
| `suboss87/FDEOps` | 245 | "segundo cerebro" para FDEs |
| `libaice/Awesome-FDE` | 94 | lista curada |
| `weissmanntobi-del/Forward_Deployed_Engineer_Material` | 45 | material |
| `yeasy/forward_deployed_engineering_guide` | 36 | buenas prácticas |
| `OpenFDEAI/OpenFDE` | 30 | hub comunitario |
| `hasura/axiom` | 12 | demo kit de PromptQL |

**Ocho de nueve son roadmaps, awesome-lists y guías de carrera. Ninguno es
herramienta que corra.** El único con código de trabajo tiene 12 estrellas y es
el demo kit de un vendor.

Es un ecosistema que documenta cómo *conseguir* el trabajo y no cómo *hacerlo*.
Un repo con herramientas testeadas y un caso económico ejecutable no compite
contra nada en esa lista.

Complemento legítimo, no competencia: **`process-intelligence-solutions/pm4py`**
(997 ⭐, mantenido activamente) es la biblioteca de referencia de process mining.
La herramienta 3 del kit es deliberadamente ligera y sin dependencias; para
descubrimiento de modelos formales (Petri nets, Inductive Miner) hay que ir a
pm4py, y conviene decirlo en vez de fingir que se cubre todo.

---

## Parte 2 — El modelo económico

`fdekit.value` convierte el `hallazgos.json` del diagnóstico en un caso con
distribución, no en un número.

```bash
fdekit demo --out out
fdekit value --findings out/hallazgos.json --archetype todos --scale grande --sites 3 --control
```

### Las tres reglas que lo diferencian de una planilla de vendor

**1. Caja ≠ beneficio.** Una hora de picking liberada no es un ahorro si no se
deja de pagar. `labor_flex_share` es la fracción que sí se convierte en caja
—sobretiempo que se deja de pagar, temporales que no se contratan— y va de 0.15
en manufactura sindicalizada a 0.60 en e-commerce con dotación temporal. El
business case que asume 1.0 es el que el CFO rechaza.

**2. Sin contrafactual, la atribución se castiga.** Con grupo de control medido,
atribución (0.65 / 0.85 / 0.95). Sin él, (0.20 / 0.40 / 0.65): media móvil más
baja y rango mucho más ancho, porque el rango debe reflejar la ignorancia real.
Esa función de cinco líneas es todo el argumento económico de la herramienta 6.

**3. Cada palanca contra su propio denominador.** Las palancas de horas se
contrastan contra la base de costo laboral (FTE directos derivados de líneas
procesadas); las de capital, contra el valor del inventario. Comparar el
beneficio total contra los ingresos es un error de denominador que hunde casos
correctos: para un 3PL el "ingreso" es una tarifa por pedido.

### Las seis palancas y qué herramienta las mide

| palanca | unidad | medida por |
|---|---|---|
| L1 productividad | h/año | gemba.pareto + standard_work_gap + travel_stats |
| L2 reproceso | h/año | rework_summary + link_defects_to_rework (PAF) |
| L3 capacidad diferida | estaciones | sim.sizing_sweep (la rodilla) |
| L4 nivel de servicio | pedidos/año | cycle_time_stats + diff_in_diff |
| L5 capital de trabajo | USD inventario | dataquality.audit_summary |
| L6 incidentes evitados | incidentes/año | probe + spc.degradation_alarm |

Regla dura: **si una palanca no tiene herramienta que la mida, no entra al
caso.** Eso es lo que separa esto de una planilla.

### Los cinco arquetipos y por qué el mismo hallazgo vale distinto

Corriendo el mismo `hallazgos.json` contra cada arquetipo, escala grande, con
contrafactual medido:

| arquetipo | palanca dominante | % del beneficio que es caja |
|---|---|---|
| **3PL** | horas recuperadas | ~75% |
| **Retailer omnicanal** | capital de trabajo | ~64% |
| **E-commerce** | horas recuperadas | ~85% |
| **Manufactura** | incidentes evitados | ~69% |
| **Mayorista** | capital de trabajo | ~82% |

Un 3PL cobra por unidad procesada: cada hora liberada es margen y su dotación es
mayormente flexible. Un mayorista tiene USD 65M inmovilizados y las horas casi
no le mueven la aguja. **Vender el mismo argumento a los dos es no entender a
quién le estás vendiendo.**

### La escalera de precio

El modelo que podés ofrecer depende de si mediste. Se sube, no se salta.

| modelo | riesgo del proveedor | ¿requiere medición? | captura típica |
|---|---|---|---|
| tiempo y materiales | bajo | no | — |
| precio fijo | medio | no | — |
| suscripción | medio | no | 8-15% |
| hitos por resultado | alto | **sí** | 10-20% |
| gainshare | muy alto | **sí** | 15-30% |

`price_band()` **se niega** a cotizar gainshare o hitos sin grupo de control, y
explica por qué: el cliente puede atribuir la mejora a la estacionalidad y tiene
razón. Ese "no" es la función más valiosa del módulo.

También se niega cuando el piso por margen supera la captura máxima del modelo,
en vez de emitir una banda degenerada que captura el 90% del beneficio del
cliente y se ve razonable en una planilla. Devuelve las cuatro salidas reales:
achicar alcance, subir escala, ampliar palancas, o cobrar T&M y volver.

### Rollout multi-sitio

Dos curvas de experiencia, no una: el sitio 2 rinde casi lo mismo que el 1
(`benefit_learning=0.95`) pero cuesta bastante menos (`cost_learning=0.55`),
porque el descubrimiento ya se hizo. A 5 sitios: beneficio ×4.66, costo ×2.49.

Ese diferencial **es** la razón económica del rollout, y es el argumento para
que el segundo contrato se cotice distinto al primero.

### El detector de humo

`ValueCase.warnings()` marca lo que el cliente va a preguntar:

- atribución alta sin grupo de control
- `cash_share` de horas sobre 50%
- palancas de horas sobre 15% de la base laboral ("estás prometiendo recortar 1
  de cada 6 horas de la operación")
- liberar más del 10% del inventario por calidad de datos
- payback bajo 3 meses ("demasiado bueno, revisar la aritmética")
- menos del 25% del beneficio en caja ("es un caso de capacidad, no de ahorro:
  venderlo como ahorro garantiza una discusión perdida en el mes 9")

### Cláusulas que evitan el juicio

`gainshare_terms()` devuelve piso (cubre el costo aunque el beneficio sea cero),
techo (sin él no firman), y el método de verificación **escrito**. Si el
contrato dice "de común acuerdo", el acuerdo se rompe el primer trimestre malo.

Y detecta el gainshare degenerado: cuando el piso domina los tres escenarios,
`es_precio_fijo_disfrazado=True`. El cliente lo va a notar; mejor decirlo
primero.

---

## Fuentes

- [Palantir And Forward Deployed Engineering: What Should We Believe? — Forbes, 10-jul-2026](https://www.forbes.com/sites/stevebanker/2026/07/10/palantir-and-forward-deployed-engineering-what-should-we-believe/)
- [What are Forward Deployed Engineers, and why are they so in demand? — The Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers)
- [A Day in the Life of a Palantir Forward Deployed Software Engineer — Palantir Blog](https://blog.palantir.com/a-day-in-the-life-of-a-palantir-forward-deployed-software-engineer-45ef2de257b1)
- [Forward Deployed Engineers — Silicon Valley Product Group](https://www.svpg.com/forward-deployed-engineers/)
- [pm4py — process-intelligence-solutions](https://github.com/process-intelligence-solutions/pm4py)
- Búsqueda de repos vía API de GitHub, 1-ago-2026.
