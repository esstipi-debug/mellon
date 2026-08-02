# Calibración Chile 2026 — validación de los defaults económicos

Verificado el **1 de agosto de 2026**. Cada parámetro trae su fuente. Los que
siguen siendo supuestos están marcados y `parametros_sin_verificar()` los lista.

```bash
fdekit value --findings out/hallazgos.json --calibration chile --archetype todos --control
```

Los defaults originales de `archetypes.py` eran priors razonables de LATAM, sin
validar. Esta es la corrección.

---

## Las tres correcciones que mueven la aguja

### 1. La jornada legal: 42 horas, no 45

La Ley 21.561 va por etapas: 45 → 44 (abr-2024) → **42 (26-abr-2026)** → 40
(abr-2028). Un FTE chileno rinde:

| concepto | horas |
|---|---:|
| brutas (42 × 52,14) | 2.190 |
| − vacaciones (15 días hábiles) | −126 |
| − feriados hábiles (~11) | −92 |
| **contratadas** | **1.971** |
| − ausentismo 5% | −98 |
| **productivas** | **1.873** |

El default de 2.000 h estaba **6,4% alto** y era un supuesto importado de EE.UU.

Detalle que corregí en el modelo mientras validaba: reducir la jornada **no**
baja la base de costo laboral. Cambia cuánta gente hace falta para el mismo
trabajo, no cuánto trabajo hay. `annual_labor_cost_usd` ahora se calcula sobre
horas de dotación directa, no sobre FTE × horas — confundir las dos cosas es
como se justifica mal una reducción de dotación.

### 2. El costo laboral: USD 6,3/hora, no USD 10-14

Construido desde la estructura legal, no desde agregadores de sueldos:

| concepto | CLP/mes |
|---|---:|
| sueldo base | 560.000 |
| gratificación legal (25%, tope 4,75 IMM/12 = 213.354) | 140.000 |
| bonos asistencia/producción | 60.000 |
| **imponible** | **760.000** |
| cargas empleador 7,65% (AFC 2,4% + mutual 1,75% + previsional patronal 3,5%) | 58.140 |
| provisiones 10% (vacaciones 6% + indemnización 4%) | 76.000 |
| **costo empresa mensual** | **894.140** |

→ **$5.729 CLP/hora productiva = USD 6,26** al tipo de cambio de 915.
Factor sobre sueldo base: **1,60×**.

**Por qué no usé los agregadores de sueldos.** Computrabajo e Indeed reportan
$445.545 a $520.674 para operario de bodega — *por debajo del ingreso mínimo
legal vigente de $539.000*. Mezclan períodos, jornadas parciales y líquido con
bruto. Anclar en un número que es ilegal habría sido peor que no validar nada.

Los defaults genéricos (USD 10-14/h) estaban **60-120% altos**. Eran cifras de
EE.UU. o de frontera norte de México, no de Santiago.

### 3. El ingreso por pedido de un 3PL: USD 2,2, no USD 4,8

Tarifario público de Stocka (2026): pick & packing **$850/pedido**,
almacenamiento **$26.500/m³/mes**, despacho RM **$3.200/pedido**.

El flete es traspaso con margen fino. Incluirlo duplica el denominador y hace
ver chico un beneficio que respecto del negocio real es grande. Ingreso de
fulfillment (pick&pack + asignación de almacenaje/VAS, sin flete) ≈ **$2.000 CLP
= USD 2,19**.

**Este es el número menos confiable de la calibración** y está marcado como tal:
la asignación de almacenaje y servicios de valor agregado por pedido no es
pública, y Stocka es un 3PL de e-commerce de paquete chico — un operador
industrial B2B factura por pallet-mes y por línea, con otra estructura.

---

## Resto de parámetros

| parámetro | valor | fuente |
|---|---|---|
| IMM | $539.000 (sube a $553.553 el 01-may-2026) | Ley 21.751 |
| TPM | 4,5% desde marzo 2026 | Banco Central |
| Tipo de cambio | 915 CLP/USD (rango 2026: 854-932) | BCCh, dólar observado |
| Ticket e-commerce | $80.000 (+2,8% vs 2025) | CCS, Q1-2026 |
| Ticket CyberDay 2026 | $93.000 (USD 104) | CCS |
| WACC USD, empresa grande | 8,5% (era 14%) | derivado, **no observado** |

Sobre el tipo de cambio: uso el punto medio del rango observado, no el spot. El
spot mueve el caso 10% de un mes a otro y eso no es información sobre el
proyecto.

---

## Lo que sigue siendo supuesto

`parametros_sin_verificar()` los devuelve con instrucciones de cómo resolverlos:

| parámetro | valor | cómo conseguirlo |
|---|---|---|
| feriados hábiles | 11/año | contar del calendario del año y cruzar con el reglamento interno (retail y e-commerce operan en feriado) |
| ausentismo | 5% | sale de la planilla de asistencia del cliente; rango observado 4-8% |
| mutual (Ley 16.744) | 1,75% | depende de la siniestralidad de la empresa; pedir la tasa real |
| provisión indemnización | 4% | el teórico es 8,33%; con la rotación de bodega la efectiva es menor. Pedir el histórico de finiquitos |
| WACC | 8,5% | **pedir el que usa el cliente en su comité de inversiones**: siempre tienen uno y siempre es distinto al que uno calcula |

Ese último es el más importante de la lista. Discutir el WACC propio contra el
del cliente es una discusión que no se gana y que no hay que tener.

---

## Impacto sobre el caso económico

Mismo `hallazgos.json`, escala grande, 3 sitios, con contrafactual medido:

| arquetipo | caja p50 genérico | caja p50 Chile | Δ |
|---|---:|---:|---:|
| 3PL | USD 409.808 | USD 316.106 | **−23%** |
| Retailer omnicanal | 1.270.346 | 1.131.583 | −11% |
| E-commerce | 1.528.947 | 1.078.464 | **−29%** |
| Manufactura | 824.305 | 797.577 | −3% |
| Mayorista | 1.100.270 | 1.067.097 | −3% |

La corrección pega fuerte exactamente donde las horas son la historia (3PL y
e-commerce, −23% y −29%) y casi nada donde la palanca dominante es capital de
trabajo o incidentes evitados. El WACC más bajo compensa una parte: mejora el
VAN aunque el beneficio anual caiga.

**Ninguno de los casos se cae.** Los paybacks siguen entre 3 y 9 meses. Pero un
caso presentado con los defaults genéricos habría prometido a un cliente de
e-commerce chileno un 40% más de lo que puede entregar, y eso se descubre en el
mes 9, en la reunión equivocada.

---

## Lo que NO validé

- **Costo de un incidente de integración** (USD 6.500 a 40.000 según arquetipo).
  Sin fuente pública. Es el parámetro que más peso tiene en manufactura.
- **`labor_flex_share`** (0,15 a 0,60). Es la variable más importante del modelo
  entero y depende de la composición contractual de cada cliente: cuánto es
  planta, cuánto plazo fijo, cuánto suministro transitorio. Solo se resuelve
  mirando la planilla.
- **`capex_per_station_usd`**. Cotización de proveedor, caso a caso.
- **Volúmenes de los arquetipos** (pedidos/día por escala). Son órdenes de
  magnitud plausibles, no un censo de CDs chilenos.

## Fuentes

- [Ley 21.751 — Ingreso Mínimo Mensual, BCN](https://www.bcn.cl/leychile/navegar?idNorma=1214530)
- [Ley 40 Horas: reducción a 42 h desde el 26-abr-2026 — Reporte Minero](https://www.reporteminero.cl/noticia/noticias/2026/04/ley-40-horas-reduccion-jornada-laboral-chile-2026)
- [Costo por contratación en Chile 2026 — Buk](https://www.buk.cl/blog/costo-por-contratacion-chile-calculo-empresa)
- [Cotización empleador 3,5% agosto 2026 — CalculaChile](https://calculadorachile.cl/blog/cotizacion-empleador-3-5-agosto-2026-costo-pyme)
- [Dólar observado — dolaruf.cl / Banco Central de Chile](https://dolaruf.cl/dolar)
- [Banco Central mantiene la TPM en 4,5% — XTB](https://www.xtb.com/lat/analisis-y-noticias/analisis-de-mercado/el-banco-central-de-chile-mantiene-la-tasa-en-4-5-y-advierte-que-el-shock-externo-es-mas-adverso-de-lo-previsto)
- [Comercio electrónico superó US$2.500 millones en Chile — CCS](https://www.ccs.cl/ecommerce/comercio-electronico-chile-us2500-millones-primer-trimestre-2026/)
- [CyberDay 2026: US$531 millones, ticket promedio US$104 — CCS](https://www.ccs.cl/2026/06/04/cyberday-2026-cerro-con-mas-de-5-millones-de-transacciones-y-us-531-millones-en-ventas/)
- [Tarifario Stocka.cl](https://stocka.cl/pages/tarifas)
- [Sueldos operador de bodega — Computrabajo](https://cl.computrabajo.com/salarios/operarioa-de-bodega) *(no usado como ancla: reporta bajo el mínimo legal)*
