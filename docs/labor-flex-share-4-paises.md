> Estudio del 1-ago-2026. Cuatro paises, un investigador y un refutador
> adversarial por pais, mas marco metodologico y sintesis. 10 agentes, 462
> llamadas a herramientas, 72 minutos. El refutador descargo y reproceso los
> archivos primarios: cubos del ABS, el ZIP de 31,5 MB de OEWS, series JOLTS y
> CES, el PDF de 432 paginas de la Encla, el XLSX de la EIL.
>
> **El refutador bajo tres de las cuatro estimaciones.** Los numeros vigentes
> son los suyos.
>
> | pais | investigador | refutador | veredicto |
> |---|---|---|---|
> | Estados Unidos | 0,45 / 0,75 / 0,88 | **0,25 / 0,58 / 0,85** | MUY_ALTO |
> | Argentina | 0,35 / 0,55 / 0,75 | **0,15 / 0,55 / 0,90** | RAZONABLE |
> | Chile | 0,40 / 0,88 / 0,96 | **0,15 / 0,45 / 0,70** | MUY_ALTO |
> | Australia | 0,30 / 0,63 / 0,83 | **0,18 / 0,42 / 0,78** | MUY_ALTO |
>
> Implementado en `fdekit/value/labor_regimes.py`. Dos correcciones al modelo
> salieron de aca: el recargo de sobretiempo ya no se aplica a la fraccion
> completa de horas, y la diferenciacion de flexibilidad paso del arquetipo de
> empresa al modelo de dotacion (el contrato manda sobre el pais).
>
> Marco metodologico completo al final del documento.

# Calibración final de `labor_flex_share` — cuatro países, centro de distribución

**Fecha de consolidación: 2026-08-01.** Todas las cifras provienen de la investigación de país y su refutación adversarial; ninguna se cita de memoria. Cuando una cifra no pudo verificarse contra su fuente, está marcada como tal y **no se usa como input**.

**Salida reportada = `flex_cash_y1`** (caja efectivamente ahorrada entre el mes 1 y el 12), porque es literalmente lo que pregunta la definición operativa. El `flex_run_rate` (anualizado al mes 12) se reporta aparte y **no debe usarse para payback**. Confundirlos es el error nº1 de este estudio y uno de los cuatro informes lo cometió.

---

## 0. Meta-hallazgo antes de los números

Tres de los cuatro informes de país recibieron veredicto **MUY_ALTO** del refutador (Australia, EE.UU., Chile) y uno **RAZONABLE** (Argentina). Los tres sobrestimados fallan **por los mismos dos mecanismos, en la misma dirección**:

1. **Fijar `Ω` (tasa de captura sin reemplazo) o `a_ATT` en 1,0** con el argumento de que la capacidad de atrición sobra frente a un proyecto de 0,5 FTE. Ese argumento supone que *cualquier* baja del sitio sirve para absorber las horas liberadas. No es así: hace falta una baja **en el rol y el turno cuyas horas se liberaron**, más la decisión efectiva de no cubrirla. En EE.UU. ese bloque aportaba el 68 % de la moda; en Australia, el 59 %.
2. **Reportar run-rate como caja del año 1** (Chile: 0,88 reportado vs 0,55 calculado por el propio informe, que además escribió "reportar este número y no el run-rate" y luego reportó el run-rate).

La capa de **evidencia** es, en cambio, de calidad alta en los cuatro países: el refutador descargó y reprocesó los archivos primarios (cubos ABS, ZIP de OEWS de 31,5 MB, series JOLTS/CES/ECEC, PDF de 432 páginas de la Encla, XLSX de la EIL) y las cifras reprodujeron casi todas exactas. **El problema no está en los datos; está en los parámetros que ningún dato público cubre.**

---

## 1. Tabla de calibración final

`flex_cash_y1` — fracción de 1.000 horas liberadas que se convierte en egreso de caja evitado dentro de 12 meses, para un proyecto **individual** en un CD de dotación mediana (150–300 permanentes), sin supuesto de autorización agresiva de despidos.

| País | Investigador | Refutador | **FINAL (low / mode / high)** | Run-rate mes 12 (derivado, no medido) | Quién gana y por qué |
|---|---|---|---|---|---|
| **Estados Unidos** | 0,45 / 0,75 / 0,88 | 0,25 / 0,58 / 0,85 | **0,25 / 0,58 / 0,85** | ~0,80 | **Refutador.** `Ω`=1 implícito aportando el 68 % de la moda; `c_TEMP`=0,98 por encima del techo (0,97) de la banda derivada por el propio informe; granularidad de 0,51 FTE no tratada; heterogeneidad estatal (New Jersey) documentada pero no incorporada al rango. |
| **Argentina** | 0,35 / 0,55 / 0,75 | 0,15 / 0,55 / 0,90 | **0,15 / 0,55 / 0,90** | ~0,95 | **Refutador en el rango, empate en la moda.** El 0,55 sobrevive pero *por compensación de dos errores de signo opuesto* (θ demasiado bajo, y retraso de ejecución descontado sólo de V4). El piso 0,35 no se reproduce con el modelo del propio informe (da 0,50) y su driver declarado —bajar `Ω`— no mueve nada. |
| **Chile** | 0,40 / 0,88 / 0,96 | 0,15 / 0,45 / 0,70 | **0,15 / 0,45 / 0,70** | ~0,80 | **Refutador, decisivo.** Dos hallazgos independientes: (a) el 0,88 es run-rate, no caja; (b) `s_TEMP` está anclado en la fila sectorial de la Encla (10,7 %) que es una **mezcla por tamaño de empresa**; la Tabla 2 del mismo capítulo da 25,5 % para gran empresa. El informe aplicó la corrección por tamaño a las EST y no a la pieza mayor. |
| **Australia** | 0,30 / 0,63 / 0,83 | 0,18 / 0,42 / 0,78 | **0,18 / 0,42 / 0,78** | ~0,65 | **Refutador.** `s_TEMP` de moda (0,28 en horas) termina *por encima* del único ancla medido (21,1 % en cabezas) después de aplicar una corrección cabezas→horas que debería bajarlo (el factor implícito en los propios datos ABS es ~0,6, no 0,85). `a_ATT`=1,0 contradice el caveat del propio informe (`Ω`=0,3–0,6). |

**Dónde le doy la razón al investigador contra el refutador:**

- **Australia, V2.** El refutador confirmó celda por celda el `s_OT` de ANZSIC 53 (3,74 %). Es el único parámetro genuinamente medido sobre almacenamiento en los cuatro países y se mantiene intacto.
- **Australia, V4.** El cálculo de `S ≈ 2,53 meses` y `m* ≈ 9,5` sobrevive completo: el refutador extrajo el texto del Fair Work Act y confirmó la escala de s.119 y la tabla de s.117. Australia se parece a EE.UU. en caja de salida aunque su EPL diga otra cosa.
- **EE.UU., tesis de país.** `S ≈ 0`, WARN no se dispara en el caso de uso real, y el 19,5 % anual de *layoffs and discharges* de JOLTS es evidencia **revelada** (no teórica) de que V4 está disponible. El refutador la confirmó y la mantuvo.
- **Chile, V4 y el quinto canal.** El hallazgo de que la restricción chilena es de **precio y no de permiso** (sin autorización administrativa previa, finiquito en 10 días hábiles) sobrevive. Y su propuesta de agregar un bucket `h_CONTR` para subcontratación fue *reforzada* por el refutador, que encontró que la subcontratación en gran empresa chilena es 54,4 %, no el 34,9 % nacional que citaba el informe.
- **EE.UU., `λ_TEMP` < 1.** El investigador refutó al marco metodológico (que asume `λ>1`) mostrando que el trabajador de agencia en EE.UU. gana ~20,5 % menos que el de nómina propia. La dirección es correcta. El refutador tiene razón en que la **materialidad** está sobrevendida (mueve el resultado de 0,756 a 0,755), pero no en que la dirección esté mal.
- **Argentina, θ.** El refutador demuestra que `θ = 1 − a_ATT/2 = 0,50` es aritméticamente inconsistente con una atrición 33× mayor que la necesidad, y propone θ≈0,97. Técnicamente tiene razón sobre la fórmula, pero **operativamente el 0,50 del investigador es un proxy defendible** del retraso de ejecución más el emparejamiento rol/turno, que el modelo no tiene en ningún otro lado. Neto: mantengo la moda en 0,55 y **anoto explícitamente que el modelo argentino no es robusto** — llega al número correcto por el camino equivocado, y por lo tanto su análisis de sensibilidad publicado es engañoso.

**Dónde no le doy la razón a ninguno de los dos:** el tope de 90 días de la indemnización por obra o faena en Chile. El refutador tiene razón en que **no aparece en la URL citada** (ORD. N° 954/9 de la DT) y por lo tanto no está acreditado. Pero de ahí no se sigue que sea falso. Queda como **pendiente de re-fundamentación**, no como cifra refutada. Materialidad baja (sólo mordería tras ~3 años de obra continua).

---

## 2. Desagregación por vía

Leyenda: **[SEC]** = dato del sector logístico/almacenamiento · **[NAC]** = promedio nacional o multisectorial, usado como banda de sanidad · **[DER]** = derivado por cálculo, no medido · **[LEG]** = regla legal, no estadística.

### 2.1 V1 — Trabajadores eventuales

| País | Cifra | Marca | Fuente y URL |
|---|---|---|---|
| **AUS** | Casuals en división ANZSIC I (Transport, postal and warehousing) = **21,1 %** de empleados (125.569 / 596.324 mil). Serie 2014–2025 **plana**: 19,9 → 21,1, pico 24,2 en 2022 | **[SEC]** pero agregado (incluye camioneros, correo, ferrocarril, aviación) | ABS Working Arrangements Aug-2025, Tabla 7 — https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/working-arrangements/aug-2025/63360_Table07.xlsx |
| **AUS** | Labourers 45,2 % casual · Machinery operators and drivers 25,4 % · **Administrative and support services 27,6 %** (donde ABS clasifica al labour hire) | **[NAC]** ocupacional / sectorial | misma fuente |
| **AUS** | Labour hire: 351.000 personas = **2,3 % del empleo total**; Labourers 24,6 % del mix; 73,6 % sin licencias pagas. **No hay apertura por industria del host** | **[NAC]** | ABS Labour hire workers Dec-2025 — https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/labour-hire-workers/latest-release |
| **AUS** | Casual loading 25 %; **mínimo 4 horas por turno** (restricción de granularidad); terminación **sin preaviso ni indemnización** (FWA s.123(1)(c), s.119(3)) | **[LEG][SEC]** | MA000084 cl.11.1/11.2 — https://awards.fairwork.gov.au/MA000084.html · https://www.fwc.gov.au/documents/resources/nes-redundancy-pay.pdf |
| **USA** | 53-7062 (*Laborers and material movers*) en NAICS 561320 = **394.220 sobre 2.950.270 nacional = 13,4 %**. NAICS 493 total 1.963.680 vs NAICS 561320 total 2.593.250 | **[SEC]** cruce ocupación × industria | BLS OEWS May-2025 — https://www.bls.gov/oes/special-requests/oesm25in4.zip |
| **USA** | Cota superior del cluster de piso = **31,1 %**, corregida a **~24–26 %** por deriva de codificación ocupacional (las agencias aportan el 47,6 % de los movedores de material pero sólo el 7,9 % de los stockers — artefacto de clasificación) | **[DER]** | misma fuente |
| **USA** | Swing estacional NSA de nómina propia: **NAICS 493 = 2,0–4,8 %** vs **NAICS 492 couriers = 27,0–32,7 %** (2022–2025) | **[SEC]** — hallazgo clave | BLS CES — https://download.bls.gov/pub/time.series/ce/ce.data.43a.TransportationAndWarehousingAndUtilities.Employment |
| **USA** | ASA: 2,0 M temporales/semana (Q4-2025), 9,5 M personas distintas en el año, **turnover de la industria de staffing 376 %** → tenencia media ~11 semanas | **[NAC]** todos los segmentos de staffing | https://americanstaffing.net/posts/2026/03/30/employment-and-sales-rebound-in-q4/ |
| **CHL** | Temporal directo, rama "Transporte y almacenamiento; información y comunicaciones" = 9,5 % plazo fijo + 1,2 % obra o faena = **10,7 %** | **[SEC]** — **NO USAR SOLO** (mezcla por tamaño) | Encla 2023, Cap. 2, Tabla 3 — https://www.dt.gob.cl/portal/1629/articles-127353_recurso_1.pdf |
| **CHL** | **Corrección decisiva:** gran empresa = 16,0 % plazo fijo + 9,5 % obra o faena = **25,5 % temporal directo** (vs 7,7 % en microempresa) | **[NAC] por tamaño** — es el ancla correcta para un CD | Encla 2023, Cap. 2, **Tabla 2** — misma URL |
| **CHL** | EST: **14,3 % de las grandes empresas** las usa; en las usuarias hay **12,3 suministrados por 100 directos** (= 11,0 % de la dotación del sitio). Subcontratación en gran empresa: **54,4 %** | **[NAC]** por tamaño | Encla 2023, Cap. 12 — misma URL |
| **CHL** | EST topadas en **90 días** (aumentos ocasionales, eventos extraordinarios) o **180 días** (proyectos nuevos), **no renovables** | **[LEG]** — techo estructural de V1 | CT arts. 183-Ñ/183-O (Ley 20.123) — https://www.bcn.cl/leychile/navegar?idNorma=254080 |
| **ARG** | Personal de agencia = **0,41 % de la dotación** (I-2026); serie I-25 0,50 → I-26 0,41. Contratos a plazo determinado = **4,54 %** | **[NAC]** industry-of-workplace (evita el Error 1) | EIL Tabla 1.3, STEySS — https://www.argentina.gob.ar/sites/default/files/eil_2605_estadisticas.xlsx |
| **ARG** | Cota superior estructural: CIIU 7491 "Obtención y dotación de personal" = **17.988 puestos** sobre 6.614.831 asalariados privados registrados = **0,27 %** | **[NAC]** industry-of-record | OEDE/SIPA Cuadro 7 — https://www.argentina.gob.ar/sites/default/files/nacional_serie_empleo_trimestral_7.xlsx |
| **ARG** | Salida mensual del personal de agencia **4,6 %–9,9 %** vs 1,80 % del indeterminado (may-2026) → el stock rota 6–10 veces/año | **[NAC]** | EIL Tabla 1.5 — misma URL |
| **ARG** | ESE: **sin plazo máximo legal ni cupo cuantitativo**; solidaridad de la usuaria limitada a "obligaciones devengadas durante el tiempo de efectiva prestación" (art. 29 LCT texto Ley 27.802) | **[LEG]** | Dec. 1694/2006 — https://servicios.infoleg.gob.ar/infolegInternet/anexos/120000-124999/122396/norma.htm |

**Valores de `s_TEMP` (fracción de HORAS) que uso, tras reconciliación:**

| País | low | mode | high | Base |
|---|---|---|---|---|
| EE.UU. | 0,14 | 0,18 | 0,25 | OEWS con asignación proporcional; la banda 13–31 % del informe original **no es un intervalo coherente** (denominador nacional abajo, denominador 493 arriba) |
| Chile | 0,15 | 0,25 | 0,35 | Tabla 2 (gran empresa) + capa EST + contratistas |
| Australia | 0,12 | 0,22 | 0,38 | 21,1 % cabezas corregido a horas (factor ~0,6) + add-on de labour hire no medido |
| Argentina | 0,02 | 0,03 | 0,06 | vía agencia pura. Hasta 0,08 si se incluye plazo determinado, **y en ese caso `c_TEMP` baja a 0,6–0,7** (un plazo fijo no se apaga la semana siguiente) |

**El error nº1 del marco, medido en tres sistemas estadísticos independientes:**
- EE.UU.: 394.220 movedores de material trabajan en almacenes pero se cuentan en NAICS 561320 — **cero** de ellos aparece en NAICS 493 (OEWS May-2025).
- Chile: la logística aparece con 10,7 % temporal contra 22,5 % nacional; la prueba de que es artefacto está en la rotación — rama H = 28,1 %/año, **rama N (donde viven las EST) = 45,6 %/año** (INE jun-2025).
- Australia: el labour hire se clasifica en ANZSIC 7212, confirmado por ABS en *Spotlight on the Labour Account* — https://www.abs.gov.au/articles/spotlight-labour-account

### 2.2 V2 — Sobretiempo

| País | Cifra | Marca | Fuente y URL |
|---|---|---|---|
| **AUS** | **ANZSIC 53 Warehousing and storage services: 3,74 %** de horas pagadas (40,1 totales − 38,6 ordinarias). **Es el mejor dato warehouse-específico de los cuatro países** | **[SEC]** medido | ABS EEH May-2025, Cubo 15 — https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/employee-earnings-and-hours-australia/may-2025/63060DO015_202505.xlsx |
| **AUS** | Evidencia del error de agregación *dentro* de la misma división I: 46 Road transport **10,36 %** · 51 Postal **8,02 %** · 52 Transport support **7,58 %** · **53 Warehousing 3,74 %** → usar la división I sobrestima el piso de un CD ~2× | **[SEC]** | misma fuente |
| **AUS** | Ocupaciones de piso: 741 Storepersons 5,42 % · 891 Freight handlers 5,33 % · 832 Packers 5,51 % | **[NAC]** ocupacional | ABS EEH Cubo 13 — https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/employee-earnings-and-hours-australia/may-2025/63060DO013_202505.xlsx |
| **AUS** | `μ_OT` **medido** (no supuesto): **1,41×** (ANZSIC 53) y **1,55×** (Storepersons), consistente con el 150 %/200 % del award (175 %/225 % casuals) | **[SEC][DER]** | cálculo sobre Cubos 13/15 · MA000084 cl.21.1 — https://awards.fairwork.gov.au/MA000084.html |
| **USA** | **NO EXISTE dato oficial de horas extra fuera de manufactura.** Verificado sobre `ce.series`: las series de tipo 04 y 09 (238 series, no 142 como decía el informe) caen **todas** en supersectores 30/31/32. `CES4349300004` y `...0009` no existen | **[SEC]** no-encontrado verificado | https://download.bls.gov/pub/time.series/ce/ce.series |
| **USA** | Ancla superior: manufactura, producción y no supervisorios = **9,1 %** de horas (3,717/41,025, 2025) | **[NAC]** manufactura | https://download.bls.gov/pub/time.series/ce/ce.data.30c.Manufacturing.ProductionEmployeeHoursAndEarnings |
| **USA** | Ancla inferior: ECEC *Overtime and premium*, Trade/transportation/utilities = **0,45 USD/h y 1,2 % de la compensación** (2025 Q4). **Verificado que ECEC no publica el estimate_code 10 para la industria 430000** | **[NAC]** diluido por comercio minorista | https://download.bls.gov/pub/time.series/cm/cm.data.1.AllData |
| **USA** | Trampa aritmética confirmada: NAICS 493 producción/no supervisorios promedia **38,51 h < 40** y sin embargo hay sobretiempo (distribución bimodal). Nunca estimar `s_OT = max(0, h−40)/h` | **[SEC]** | https://download.bls.gov/pub/time.series/ce/ce.data.43b.TransportationAndWarehousingAndUtilities.AllEmployeeHoursAndEarnings |
| **CHL** | **La Encla no desagrega horas extra por rama** (verificado leyendo el índice del Cap. 10: sólo por tamaño y sexo). 29,0 % de trabajadores de gran empresa hizo horas extra; 14,7 h/mes entre quienes las hacen → `s_OT` derivado **~2,1 %** | **[NAC]** derivado, mes de referencia **nov-2022** | Encla 2023 Cap. 10 Tablas 3/4 — https://www.dt.gob.cl/portal/1629/articles-127353_recurso_1.pdf |
| **CHL** | `μ_OT` = **1,50** (recargo único de 50 %, art. 32 CT). **Compensación en tiempo** (no-caja): en gran empresa 3,3 % sólo horas compensadas + 23,6 % mixto = **~27 % de las empresas**, no el 8–15 % que reportaba el informe | **[NAC]** | Encla 2023 Cap. 10 Tabla 5 (fila gran empresa) |
| **CHL** | Jornada legal **42 h/sem desde el 26-abr-2026** (44 h desde abr-2024; 40 h desde abr-2028). A volumen constante, **convierte horas ordinarias en extraordinarias al 1,5×** | **[LEG]** | Ley 21.561 — https://www.bcn.cl/leychile/navegar?idNorma=1191554 |
| **ARG** | **No existe ninguna estadística argentina de horas.** Verificado: cero ocurrencias de "hora", "extra", "jornada" y "suplement" en las 128 hojas de la EIL | **[NAC]** no-encontrado verificado | https://www.argentina.gob.ar/sites/default/files/eil_2605_estadisticas.xlsx |
| **ARG** | Único anclaje: Dec. 484/2000, **30 h/mes y 200 h/año** sin autorización administrativa previa → 200/2.070 = **9,7 %** de las horas trabajadas. **Es un umbral de autorización, no una prohibición absoluta** | **[LEG][DER]** | https://servicios.infoleg.gob.ar/infolegInternet/anexos/60000-64999/63347/norma.htm |
| **ARG** | `μ_OT` = **1,50** días comunes y **2,00** sábado después de 13 h, domingos y feriados (art. 201 LCT, **sin modificaciones** por la Ley 27.802). CCT 40/89 rama 5.12: si las 44 h se concentran lun-vie, **toda hora del sábado hasta las 13 h se paga al 100 % de recargo** | **[LEG][SEC]** | https://aaba.org.ar/wp-content/uploads/2026/03/reforma-laboral-ley-27802-cuadro-comparativo-LCT.pdf · https://www.fadeeac.org.ar/wp-content/uploads/2021/08/CCT-40-89.pdf |
| **ARG** | **Riesgo de anular V2:** art. 197 bis LCT (texto Ley 27.802) habilita banco de horas y francos compensatorios. Si el CD lo aplica, el sobretiempo **no es caja** y `c_OT` se desploma | **[LEG]** | misma URL AABA |

**Valores de `s_OT` que uso:** Australia 0,030 / **0,045** / 0,055 (medido) · EE.UU. 0,05 / **0,07** / 0,10 (derivado, banda ancha) · Chile 0,03 / **0,04** / 0,06 (subo el 2,1 % derivado: el ancla es de nov-2022, mes peak de retail chileno, y la jornada bajó dos escalones desde entonces) · Argentina 0,03 / **0,06** / 0,09 (supuesto acotado por el tope legal).

### 2.3 V3 — Rotación sin reemplazo

| País | Cifra | Marca | Fuente y URL |
|---|---|---|---|
| **USA** | JOLTS 480099 (transporte + almacenamiento + **utilities**): separaciones totales **48,0 %** anualizado · **quits 26,0 %** · layoffs and discharges **19,5 %** (2025). Ratio logística/nonfarm = **1,22×**, no el "1,5×" que circula | **[SEC]** agregado con utilities | https://download.bls.gov/pub/time.series/jt/jt.data.5.Quits · https://download.bls.gov/pub/time.series/jt/jt.data.6.LayoffsDischarges |
| **USA** | **No existe serie JOLTS para NAICS 493.** Verificado sobre el archivo maestro: los únicos códigos con prefijo 4 son {400000, 420000, 440000, 480099} | **[SEC]** no-encontrado verificado | https://download.bls.gov/pub/time.series/jt/jt.series |
| **USA** | `A` ≈ **2.080 h pagadas** / ~1.944 trabajadas. EE.UU. es el único de los cuatro **sin feriados ni vacaciones pagas obligatorias por ley federal** (7 + 10 días son práctica voluntaria) | **[SEC]** corte ocupacional | BLS NCS March 2025 — https://download.bls.gov/pub/time.series/nb/nb.data.1.AllData |
| **CHL** | Tasa de Salida Laboral, "Transporte y almacenamiento" = **28,4 %** anual (TRL 28,1 %); **grandes empresas 26,0 %**; nacional 30,1 %. **Ratio logística/economía = 0,93: en Chile la logística rota MENOS que el promedio** | **[SEC]** registro administrativo censal | INE Flujos Laborales N°8, jun-2025 — https://www.ine.gob.cl/docs/default-source/estadisticas-registros-administrativos/boletines/tasas-de-rotaci%C3%B3n-laboral/2025/junio-2025.pdf?sfvrsn=74e53e73_4 |
| **CHL** | Es una tasa de **puestos**, no de personas, e incluye el vencimiento de plazos fijos y obras ya contados en `s_TEMP`. `τ` de permanentes ≈ **18–22 %**, no 28,4 % | **[DER]** corrección del refutador | misma fuente |
| **ARG** | Tasa de salida = **2,00 %/mes = 24,0 % anual** (2025). Renuncias = **51,1 %** de las bajas → **`τ` voluntario = 12,3 %/año** | **[NAC]** empresas privadas 10+ ocupados | EIL Tablas 1.1 y 1.7 — https://www.argentina.gob.ar/sites/default/files/eil_2605_estadisticas.xlsx |
| **ARG** | **`Ω` revelado — el único país donde se puede estimar de fuente pública.** La Tabla 1.5 publica *tasa de reemplazo*: 1,08/2,00 = 54 % de bajas repuestas → **46 % NO repuestas** (49 % para contratos indeterminados; 52 % en may-2026) | **[NAC]** — techo de `Ω`, no `Ω` limpio | misma URL |
| **ARG** | Destrucción bruta de puestos, letra CIIU I = **14,2 %** anual (76.344/539.138, 2025). Es flujo de puestos a nivel de firma: **piso de `τ`, no `τ`** | **[SEC]** agregado con comunicaciones | OEDE — https://www.argentina.gob.ar/sites/default/files/flujos_de_creacion_y_destruccion_de_empleo_2.xlsx |
| **ARG** | Rama Transporte/almacenamiento/comunicaciones **se contrae** entre −2,56 % y −3,62 % interanual desde 2025 → hoy "no reemplazar" produce **hard savings**, no cost avoidance (R6 juega a favor) | **[SEC]** | EIL Tabla 1.2bis — misma URL |
| **AUS** | Tasa de separación, división I = **13,07 %** anual (742,0k base; 53,0k no empleados + 43,9k cambiaron). Ocupacional: Labourers **18,45 %**, Machinery ops 15,40 % | **[SEC]/[NAC]** — **NO comparable con JOLTS** | ABS Job mobility Feb-2026, Tablas 4 y 6 — https://www.abs.gov.au/statistics/labour/jobs/job-mobility/feb-2026/62230_Table04.xlsx |
| **AUS** | `A` = **2.014 h ordinarias / 2.092 h totales** por FTE-año (38,6 h × 52,18). Usar 2.080 introduce 3–5 % de sesgo | **[SEC][DER]** | ABS EEH Cubo 15 |

**Advertencia de comparabilidad, crítica:** el 13,07 % australiano y el 48,0 % estadounidense **miden cosas distintas**. ABS Job mobility es punto-a-punto de personas (encuesta de hogares: dónde estabas hace 12 meses); JOLTS es flujo mensual de establecimiento. Ponerlos en la misma columna comparativa es un error grave. La Tasa de Salida chilena (28,4 %) es de **puestos** sobre registro administrativo, y la argentina (24,0 %) es de **movimientos de nómina** sobre encuesta de empresas. **Ninguna de las cuatro es directamente comparable con las otras tres.**

### 2.4 V4 — Despido

| País | `S` (meses de costo cargado) | `m* = 12 − S` | Regla específica y URL |
|---|---|---|---|
| **EE.UU.** | **≈ 0,0–0,5** (sólo vacaciones acumuladas donde el estado lo obliga) | **≈ 11,5–12,0** | *Employment at-will* en 49 de 50 estados; **ninguna ley federal exige indemnización**. WARN impone **preaviso, no indemnización**: umbrales 100+ empleados, 50 bajas/30 días o 33 % + 50, o 500+; preaviso 60 días — https://www.law.cornell.edu/uscode/text/29/2101 |
| **EE.UU. (New Jersey)** | **≈ 3–5** con 3 años de antigüedad | **≈ 7–9** | Mini-WARN reformada (vigente 10-abr-2023): **90 días de preaviso MÁS 1 semana de indemnización por año de servicio, obligatoria y no renunciable**, +4 semanas si no se preavisa — https://www.jacksonlewis.com/insights/new-jerseys-expanded-mini-warn-law-take-effect-april-2023 |
| **Australia** | **≈ 2,53** base / **≈ 2,1** cargado (4 años de antigüedad: 3 sem preaviso + 8 sem indemnización) | **≈ 9,5** | FWA s.119: escala 4→16 semanas, **cae a 12 semanas a partir de los 10 años**; excluidos <12 meses y *small business* (<15 empleados). s.117: preaviso 1–4 sem, pagable en lugar → salida el mismo día. **Sin autorización administrativa previa** — https://www.fwc.gov.au/documents/resources/nes-redundancy-pay.pdf · https://www.fwc.gov.au/documents/resources/nes-notice-of-termination.pdf |
| **Chile** | **≈ 4,0** (4 años) · **≈ 6,2** (7 años) · **≈ 9,2** (11+ años) *(cifras corregidas por el refutador; el informe reportaba 4,0/5,8/10,1 y sólo el primer caso reproducía)* | **≈ 8,0 / 5,8 / 2,8** | IAS art. 163: 30 días por año, **tope 330 días (11 años)**; aviso art. 162: 30 días o 1 mes sustitutivo íntegro. **Imputación del 1,6 % del aporte patronal a la AFC baja `S` ~15–20 %** (Ley 19.728 art. 13). **Sin autorización administrativa previa** para despido colectivo; finiquito en 10 días hábiles — https://www.dt.gob.cl/portal/1628/w3-article-60593.html · https://www.suseso.cl/612/w3-propertyvalue-122277.html |
| **Argentina** | **≈ 4,0** (3 años) · **≈ 5,6** (5) · **≈ 8,9** (8) · **≈ 10,5** (10) · **≥ 12** (12+ → **V4 aporta CERO**) | **8,0 / 6,4 / 3,1 / 1,5 / 0** | LCT art. 245 (texto Ley 27.802, B.O. 6-mar-2026): 1 mes por año, tope 3× promedio del CCT **con piso del 67 % de la remuneración**; es **"la única reparación procedente"** y su pago **extingue todo reclamo** vinculado al despido. Preaviso art. 231: 1 mes hasta 5 años, 2 meses por encima — https://www.boletinoficial.gob.ar/detalleAviso/primera/339128/20260306 |
| **Argentina — canal especial** | **≈ 0,2** para el ~10–12 % de la dotación permanente que está dentro del período de prueba en cualquier momento (24 % de rotación × 0,5 año) | **≈ 11,8** | **Período de prueba de 6 meses** (8 por CCT en empresas de 6–100), art. 92 bis LCT texto Ley 27.742, **no modificado** por la Ley 27.802. Extinción sin causa, **sin indemnización y —desde 2026— sin preaviso ni integración del mes**. No usable dos veces con el mismo trabajador — https://aaba.org.ar/wp-content/uploads/2026/03/reforma-laboral-ley-27802-cuadro-comparativo-LCT.pdf |

**Corrección legal importante (Argentina):** el investigador afirmó dos veces que el aporte al **Fondo de Asistencia Laboral** (1 % grandes / 2,5 % MiPyME, vigencia 1-nov-2026, carencia 6 períodos) es "un costo NUEVO sobre la nómina que reduce el ahorro neto de TODAS las vías". **Refutado:** el Decreto 408/2026 permite **detraer** ese porcentaje de las alícuotas patronales ordinarias de seguridad social. El costo laboral total no aumenta. Lo que sí es correcto es que el FAL **prefinancia pero no sustituye** la indemnización del art. 245, y que con carencia de 6 meses no ayuda en el año 1 — https://www.boletinoficial.gob.ar/detalleAviso/primera/342622/20260601

**EPL de la OCDE: los cuatro países quedaron NO_VERIFICABLES.** Ninguno de los cuatro refutadores pudo re-extraer los valores contra la fuente; los cuatro investigadores los tomaron del marco del equipo. Además, en Argentina la serie 2025 **es anterior a la Ley 27.802** y sobrestima hoy la rigidez. Y hay una duda direccional concreta en EE.UU.: en la dimensión de **despido colectivo** el WARN Act probablemente hace que EE.UU. *no* sea el más bajo. **No publicar estos valores sin re-extracción**, y no usarlos como input en ningún caso — el índice ordena países, no da `S`.

---

## 3. Ranking y la institución concreta que produce la diferencia

Ordeno por **flexibilidad institucional**, no por la moda numérica — las modas no rankean igual (Argentina 0,55 > Chile 0,45 > Australia 0,42) porque cada informe aplicó disciplina distinta a `θ` y `Ω`, y esos parámetros no son datos de país sino supuestos de modelo. **La comparación honesta entre países está en las instituciones y en `S`, no en el punto estimado.**

### 1º — Estados Unidos (mode 0,58)
**La institución:** *employment at-will* + ausencia total de estatuto federal de indemnización. La FLSA regula el sobretiempo (29 U.S.C. 207) pero **no contiene obligación de severance**; el WARN Act (29 U.S.C. 2102) impone **preaviso de 60 días, no dinero**, y su remedio por incumplimiento es *back pay* del período de preaviso.

**Consecuencia mecánica:** `S ≈ 0` → `m* ≈ 12`. **EE.UU. es el único país donde V4 no tiene ventana cerrada.** Y esto invierte la jerarquía del marco: un CD estadounidense **no tiene por qué esperar la atrición**, puede reducir dotación directamente en el mes 1–3 y capturar 9–11 meses de caja, en vez del ~50 % que da la llegada uniforme de bajas. La prueba de que es práctica corriente y no teórica: JOLTS mide **19,5 % anualizado de layoffs and discharges** en el sector en régimen normal, sin fricción legal.

**El matiz que rompe la homogeneidad:** New Jersey — uno de los mercados de almacenamiento más grandes del país — tiene desde 2023 **indemnización legal obligatoria**. Un CD en Texas y uno en New Jersey **no tienen el mismo `labor_flex_share`**.

### 2º — Australia (mode 0,42)
**La institución:** Fair Work Act **s.123(1)(c)** — la División 11 (preaviso y redundancy pay) **no se aplica a un casual employee** — combinada con **s.119(3)**, que dispone que el servicio como casual no computa para la antigüedad indemnizatoria. El casual australiano es la figura **más cancelable de los cuatro países**: se apaga con el roster de la semana siguiente, costo de terminación cero. Única fricción: el **mínimo de 4 horas por turno** de MA000084 cl.11.1, que es una restricción de *granularidad* (hay que cancelar turnos enteros), no de horizonte.

**Y para V4:** `S ≈ 2,5 meses` → `m* ≈ 9,5`, con salida ejecutable el mismo día pagando en lugar del preaviso y **sin autorización administrativa previa**. Australia se parece mucho más a EE.UU. que a Chile o Argentina **en caja de salida**, pese a que su EPL_R de la OCDE (1,66) sea más del doble que el de EE.UU. (0,75) — la advertencia del marco de que "el EPL ordena países pero no da `S`" queda probada aquí.

**Lo que le baja el puesto:** (a) el `s_TEMP` medido (21,1 % en cabezas, división I) es **plano desde 2014**, no creciente; (b) el *employee choice pathway* (vigente 26-ago-2024) migra a planilla el núcleo de casuals de facto permanentes, erosionando la reserva de V1 en 2025–2027; (c) **`Same Job Same Pay` no aplica a un CD cubierto sólo por award** — una *regulated labour hire arrangement order* exige que el HOST tenga enterprise agreement o workplace determination, y las órdenes efectivamente dictadas son minería del carbón, tripulación de Qantas y avícola, **ninguna de almacenamiento**.

### 3º — Argentina (mode 0,55, pero el más frágil)
**La institución diferencial:** el **período de prueba de 6 meses** del art. 92 bis LCT (texto Ley 27.742 de 2024, confirmado no modificado por la Ley 27.802), ampliable a 8 meses por CCT en empresas de 6 a 100 trabajadores. Extinción sin causa, **sin indemnización, sin preaviso y sin integración del mes**. Con 24 % de rotación anual, **~10–12 % de la dotación permanente de un CD está en esa condición en todo momento**, con `S ≈ 0,2` y `m* ≈ 11,8`.

**Esto no cabe en la partición OT/TEMP/PERM del marco:** son horas `h_PERM` por contrato que se comportan como `h_TEMP` con `c ≈ 1`. Es el canal de reducción más barato del país y ningún índice lo captura.

**Lo que lo frena:** art. 245 LCT sin tope en años de antigüedad → `S` de 4,0 meses a los 3 años y **≥12 meses a los 12 años, donde V4 aporta cero**. Y **`τ` argentino es la mitad del benchmark de EE.UU.** (24,0 % vs ~40–46 % de JOLTS TTU 2025; voluntario 12,3 % vs 24,0 %), lo que significa que **el presupuesto compartido de atrición se agota con la mitad de proyectos concurrentes**. La restricción R4 muerde antes que en cualquier otro país del estudio.

**Por qué es el más frágil pese a la moda alta:** el modelo argentino llega a 0,55 por compensación accidental de dos errores de signo opuesto, y su escenario bajo (0,35) no se reproduce con su propio modelo (da 0,50). El número es defendible en magnitud, no en derivación.

### 4º — Chile (mode 0,45)
**La institución que lo distingue:** los **arts. 183-Ñ y 183-O del Código del Trabajo** (Ley 20.123). El suministro de trabajadores sólo procede por causales tasadas y con tope de **90 días** (aumentos ocasionales de actividad, eventos extraordinarios) o **180 días** (proyectos nuevos, ampliaciones), **no susceptibles de renovación**.

Esto tiene dos caras y hay que decir las dos. Hace `c_TEMP ≈ 1,0` para la porción EST — la relación **se extingue sola dentro del año, sin indemnización por años de servicio**. Pero **impide sostener una fracción alta de la dotación base por esa vía todo el año**: el peak de CyberDay/Black Friday cabe holgadamente en 90 días; la operación de régimen, no. Chile es el único de los cuatro países con un **techo legal duro sobre `s_TEMP`**.

**Segunda institución:** el art. 159 N°4 permite plazo fijo de **1 año con una sola renovación**, y **dos o más contratos a plazo en 12 meses dentro de un período de 15 hacen presumir contrato indefinido**. La regla anti-encadenamiento impide construir una capa permanente de "eventuales" con renovaciones sucesivas — que es exactamente la práctica que en otros países infla `s_TEMP`.

**Y el `τ` más bajo del estudio:** 28,4 % sectorial / 26,0 % en grandes empresas, con ratio logística/economía de **0,93** — en Chile la logística rota *menos* que el promedio nacional. Los sectores flexibles chilenos son construcción (51,6 %) y servicios administrativos (45,6 %).

**Contrapeso a favor de Chile, que es real:** la restricción chilena a V4 es de **precio, no de permiso**. No hay autorización administrativa previa para despido colectivo, no hay consulta sindical obligatoria, y el finiquito sale en 10 días hábiles. Y la **imputación del aporte patronal a la AFC** (Ley 19.728 art. 13) baja `S` un 15–20 %, cosa que ningún índice EPL captura.

> **Advertencia sobre el ranking 3º vs 4º:** Argentina y Chile están **dentro de la banda de incertidumbre uno del otro**. El orden se invierte si el CD chileno es usuario intensivo de EST (donde Chile realiza 11 % de la dotación del sitio, contra un stock argentino de agencia de apenas 0,27 % del empleo privado registrado) o si el CD argentino tiene antigüedad media alta y una dotación estabilizada sin flujo de período de prueba.

---

## 4. Diferenciación por tipo de dotación: planta propia / 3PL / mix

Esto es **el ajuste más grande del estudio y el peor documentado**. Ninguna estadística oficial de ningún país publica `s_TEMP` ni `τ` por modelo de dotación. Lo que sigue es un marco de ajuste construido sobre reglas legales verificadas más aritmética declarada; **los deltas son juicio, no medición**, y están etiquetados como tales.

### El punto conceptual que hay que fijar primero

Cuando el CD opera con 3PL, **las horas liberadas no están en la nómina del CD: están en una factura de servicios**. Eso las saca del alcance del Código del Trabajo y las mete en el alcance del **contrato comercial**. La partición OT/TEMP/PERM del marco **no las contiene**. Hay que agregar un quinto bucket `h_CONTR` con su propio `c_CONTR` y su propio `λ`, y medirlo con la factura, no con estadística laboral.

Evidencia de que este canal es grande, no marginal:

- **Chile:** 34,9 % de las empresas subcontrata alguna actividad; **54,4 % en gran empresa**; 12,1 % subcontrata su **giro principal** — Encla 2023 Cap. 12, https://www.dt.gob.cl/portal/1629/articles-127353_recurso_1.pdf
- **Argentina:** el art. 29 LCT (texto Ley 27.802) limita la solidaridad de la usuaria a "obligaciones devengadas durante el tiempo de efectiva prestación" y le permite repetir contra la ESE — https://aaba.org.ar/wp-content/uploads/2026/03/reforma-laboral-ley-27802-cuadro-comparativo-LCT.pdf
- **Australia:** ABS declara explícitamente que las empresas de labour hire y sus empleados se clasifican a ANZSIC 7212, **fuera** de la división del host — https://www.abs.gov.au/articles/spotlight-labour-account
- **EE.UU.:** 2.593.250 empleados en NAICS 561320 contra 1.963.680 en NAICS 493 — https://www.bls.gov/oes/special-requests/oesm25in4.zip

### Ajustes propuestos (JUICIO, no medición)

| Modelo | Ajuste a `flex_cash_y1` | Mecanismo |
|---|---|---|
| **Planta propia 100 %** | **Base** (los rangos de la §1) | El resultado depende íntegramente de `Ω`, de `S` y de la voluntad organizacional de ceder dotación |
| **3PL open-book / cost-plus, con FTEs facturados por hora** | **+0,10 a +0,25**, y `θ` sube a 0,85–0,95 | Reducir un FTE facturado es una **enmienda de orden de compra**, no un despido. `S` desaparece del P&L del cliente y pasa al del operador. `m*` deja de existir como restricción. **Es el único arreglo donde `m*` no importa.** |
| **3PL closed-book / precio fijo por unidad manipulada (por caja, por línea, por pallet)** | **+0,05 a +0,15 en run-rate, pero 0,00 a +0,05 en caja del año 1** | La eficiencia se captura **sólo en la renegociación de tarifa**, típicamente en el aniversario del contrato. Un proyecto que corre en el mes 3 puede no ver un peso hasta el mes 13. |
| **3PL con volumen mínimo comprometido o management fee piso** | **−0,10 a −0,30 respecto de planta propia** | La cláusula de volumen mínimo actúa exactamente como una garantía de horas: `c_CONTR` cae a `1 − (volumen comprometido / volumen actual)`. **Es el peor caso de los cinco y el más frecuente en 3PL dedicado.** |
| **Mix (núcleo propio + agencia/labour hire en el margen)** | **+0,05 a +0,15** sobre planta propia pura, **pero sólo si el proyecto ataca el turno o la zona donde está el eventual** | El eventual está concentrado, no repartido. Ver §5. |

### Tres reglas de aplicación

1. **El delta del 3PL depende del `c_CONTR` del contrato, no del país.** Un 3PL open-book en Chile puede tener `flex_cash_y1` más alto que planta propia en EE.UU. La institución que manda es la cláusula de preaviso y de volumen comprometido, no el Código del Trabajo. **Pedir el contrato antes que cualquier estadística.**
2. **`λ_CONTR` > 1 casi siempre, y eso mejora el multiplicador de caja aunque no mueva la share en horas.** En Argentina está probado por convenio: el CCT 40/89 item 5.11.6 establece que **el personal eventual o contratado percibe el convenio completo** — no hay descuento salarial por usar eventuales, sólo flexibilidad, y con el markup de la ESE la hora de agencia **cuesta más** que la interna. https://www.fadeeac.org.ar/wp-content/uploads/2021/08/CCT-40-89.pdf
3. **Excepción documentada: en EE.UU. `λ_TEMP < 1`.** OEWS May-2025 muestra que el trabajador de agencia gana ~20,5 % *menos* que el de nómina propia en las mismas ocupaciones (53-7062: 17,35 vs 21,82 USD/h). Con markup light-industrial de ~45 %, el bill rate queda en ~25,2 USD/h contra un costo cargado interno de ~30,6 USD/h → `λ_TEMP ≈ 0,82`. **Apagar una hora de agencia en EE.UU. ahorra menos que apagar una hora interna** — al revés del supuesto del marco. La parte salarial es confianza alta; la del markup es **confianza baja** (blogs de vendors que discrepan entre sí: 25–40 % vs 40–55 %) y la materialidad medida sobre el resultado es **~0,001** — es un caveat de tercer orden, no un hallazgo de primer orden.

---

## 5. Efecto del peak estacional: por qué una línea base de noviembre miente

### La evidencia dura, y es contraintuitiva

**El pico estacional de un CD estadounidense NO aparece en la nómina propia del almacén.** Swing NSA (pico−valle)/media anual:

| Serie | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| **NAICS 493 Warehousing and storage** | 3,0 % | 4,3 % | 4,8 % | **2,0 %** |
| **NAICS 492 Couriers and messengers** | 28,1 % | 27,0 % | 32,7 % | **28,4 %** |

Fuente: BLS CES, series CEU4349300001 y CEU4349200001 — https://download.bls.gov/pub/time.series/ce/ce.data.43a.TransportationAndWarehousingAndUtilities.Employment

Dos lecturas compatibles: (a) el pico **se compra vía agencias**, que se cuentan en NAICS 5613 y por lo tanto son invisibles en 493; (b) el pico está en la última milla, no en el CD. Amazon anunció **250.000 contrataciones estacionales** en EE.UU. para 2025 (tercer año consecutivo en el mismo nivel — https://www.foxbusiness.com/lifestyle/amazon-hiring-250000-workers-upcoming-holiday-season, anuncio corporativo replicado por prensa, **confianza media**) y ese volumen **no se ve** en el swing de 2,0 % de NAICS 493.

**Consecuencia directa:** en EE.UU. `s_TEMP` es esencialmente `s_AGENCIA`. Los eventuales de contratación directa en la nómina del CD aportan poco.

### Lo que sabemos del peak en los otros tres países

- **Chile:** +**~30 %** de vacantes temporales en centros de distribución en Black Friday respecto de un mes normal — Teamwork vía Logística360, https://logistica360chile.cl/black-friday-impulsa-contratacion-en-bodegas-produccion-y-transporte/ · **confianza baja** (vendor, sin metodología). Coherente con el hecho de que el peak chileno **cabe holgadamente en la ventana de 90 días del art. 183-Ñ** y la operación de régimen no.
- **Australia: la línea base publicada está medida en el valle.** ABS Working Arrangements tiene mes de referencia **agosto**, es decir pre-peak en el hemisferio sur. El 21,1 % de casuals de la división I es, casi con certeza, **menor** que la casualización de noviembre-diciembre en un CD de retail. Dirección del sesgo: hacia abajo. Magnitud: **no encontrada**.
- **Chile, sesgo en dirección opuesta:** el `s_OT` derivado de la Encla (2,1 %) tiene mes de referencia **noviembre de 2022** — mes peak de retail y e-commerce chileno. Que el sobretiempo esté en **mínimo histórico de la serie** justamente en un mes peak **debilita**, no refuerza, la hipótesis de que "el almacén chileno usa poco sobretiempo". Es el argumento más fuerte para subir `s_OT` chileno de 2,1 % a la banda 3–6 %.
- **Argentina:** no encontrado. No existe ninguna estadística argentina de horas ni de estacionalidad de eventuales en logística.

### La regla de ajuste (derivada, con inputs débiles)

Si `s_TEMP` en peak es **2–3×** el de valle (bracket construido sobre el swing de 28 % de couriers en EE.UU. y el +30 % de vacantes chileno, **ninguno de los dos medido sobre `s_TEMP` de un CD**), y `s_TEMP` aporta entre 0,15 y 0,30 de la moda:

> **Una línea base medida en noviembre-diciembre sobrestima el `flex_cash_y1` anual en aproximadamente 0,08 a 0,20 puntos**, es decir entre un 15 % y un 40 % relativo.

Y el efecto se refuerza porque **el sobretiempo también es peak-concentrado**: las horas extra se acumulan en la temporada alta, de modo que un `s_OT` medido en peak infla el mismo número por segunda vía.

### Qué hacer, en orden de preferencia

1. **Medir `H` y la partición sobre 12 meses corridos de nómina.** Es lo único correcto (regla A0.2 del marco: contra horas efectivamente pagadas).
2. Si sólo hay una foto, **tomarla en el valle** (marzo–abril en el hemisferio sur; febrero–marzo en el norte) y tratar el peak como **cota superior explícita**, nunca como base.
3. Si sólo hay una foto de peak, **descontar 0,08–0,20 puntos y decir que se descontó**, con la aritmética a la vista.
4. **Nunca extrapolar un `Ω` de peak.** En temporada alta la dotación mínima por turno es más alta, hay menos holgura para no cubrir una baja, y `Ω` cae. Un `Ω` medido en noviembre es el peor `Ω` del año y no representa al resto.

---

## 6. Lo que NO se pudo verificar

### 6.1 Parámetros que no existen en ninguna estadística pública de ningún país

| Parámetro | Por qué importa | Estado |
|---|---|---|
| **`Ω`** — tasa de captura sin reemplazo | **Es el parámetro que más mueve el resultado en los cuatro países.** En EE.UU. el bloque permanente con `Ω`=1 aportaba el 68 % de la moda; con `Ω`=0,75 el total cae de 0,756 a 0,60; con `Ω`=0,50 cae a 0,42 | No existe. **Única aproximación pública del estudio:** EIL Argentina Tabla 1.5 publica *tasa de reemplazo*, y el cociente reemplazo/salida da **46 % de bajas no repuestas** (49 % para indeterminados). Es un **techo** de `Ω`, no `Ω` limpio — en una rama que se contrae mezcla incapacidad de reponer con captura deliberada |
| **`λ_TEMP`** — bill rate de agencia ÷ costo cargado interno | Define el multiplicador de caja de V1 | Chile, Argentina, Australia: **no encontrado**. EE.UU.: sólo blogs de vendors que discrepan entre sí (25–40 % vs 40–55 %) |
| **`s_TEMP` medido en HORAS** (no en cabezas) | Toda la evidencia oficial de los cuatro países cuenta personas | No existe en ningún país. En Australia la corrección cabezas→horas es la mayor fuente de incertidumbre del estimado (75,9 % de los casuals son part-time vs 20,2 % de los no casuals) |
| **Distribución de antigüedad (tenure) del piso del CD** | Determina `S` y por lo tanto `m*`. En Argentina la diferencia entre 3 años (`m*`=8) y 12 años (`m*`=0) es la diferencia entre V4 útil y V4 nulo | No encontrado en ninguno de los cuatro países |

### 6.2 Cifras que se citaron y no se pudieron abrir

| Cifra | País | Estado |
|---|---|---|
| **Valores EPL de la OCDE** (los 12 valores, cuatro países × tres dimensiones) | Los 4 | **NO_VERIFICABLE en los cuatro casos.** Ningún refutador pudo localizarlos en el dataset. Duda direccional concreta en EE.UU. (despido colectivo, por el WARN Act). **No publicar sin re-extracción** |
| Duración media del contrato EST = 54 días (AGEST) | Chile | **URL devuelve HTTP 404.** Retirar. `c_TEMP≈1,0` para EST se sostiene independientemente sobre el art. 183-O |
| Tope de 90 días de la indemnización por obra o faena | Chile | **No acreditado en la URL citada.** No necesariamente falso; re-fundamentar o retirar |
| Superannuation guarantee 12 % desde 1-jul-2025 | Australia | ATO devolvió **HTTP 403**. Efecto de segundo orden sobre `S` |
| Articulado del Decreto 408/2026 (alícuotas FAL 1 %/2,5 %) | Argentina | Sólo verificado en resúmenes profesionales concordantes, no en el B.O. |
| WERC *DC Measures* — *annual workforce turnover* | Global | **De pago.** Es el único benchmark de rotación específico de CD con metodología publicada — https://werc.org/page/ASSESS-DC_Measures |
| ALOG Chile / WTW — *Caracterización del Mercado Laboral Logístico* | Chile | **De pago.** La mejor fuente sectorial candidata que existe para Chile |
| WEC *Economic Report 2025* — *agency work penetration rate* | Global | PDF descarga pero no se pudo extraer el texto. **Ningún valor reportado** |
| North American Warehouse Labor Turnover Survey (GCCA/IARW) | EE.UU. | Restringido a miembros; versiones públicas de 2018–2020, pre-pandemia |

### 6.3 Cifras a RECHAZAR si reaparecen

- **"43 % de rotación en warehousing"** (gitnux, opensend y similares) — sin fuente primaria rastreable. Confirmado por dos refutadores independientes que sigue circulando.
- **"La rotación en logística es 1,5× la de la economía"** — JOLTS 2025 da **1,22×** contra total nonfarm y **1,10×** contra total privado.
- **"22 % de rotación en Logística y Operaciones" en Argentina** (wellhub.com) — sin estudio primario, sin año, sin muestra, y en el mismo cuerpo del artículo el 22 % aparece también como "intención de cambio laboral", que es otra cosa.
- **Rotaciones de 7–8 % de encuestas de consultoras** (Randstad Argentina, Adecco Chile) — miden universos y definiciones distintas de las oficiales (24,0 % EIL, 30,1 % INE). **No mezclar.**
- **"Sobretiempo = 15 % de los costos laborales de almacén a nivel global"** (gitnux) — sin fuente.

### 6.4 Lo que hay que pedirle al cliente para cerrar el número

Ordenado por cuánto mueve el resultado:

1. **12 meses corridos de nómina del turno/zona que el proyecto ataca**, con las horas etiquetadas en tres columnas: pagadas con recargo / a tarifa normal de eventual / a tarifa normal de permanente. Esto resuelve `s_OT`, `s_TEMP` y `s_PERM` de una sola vez, bottom-up, y hace irrelevante toda la discusión de arriba sobre estadística sectorial.
2. **Facturas de la agencia (EST / ESE / labour hire / staffing) de esos mismos 12 meses**, en horas y en dinero. Resuelve `s_TEMP` y `λ_TEMP` simultáneamente.
3. **Extracto del HRIS de 12 meses de bajas**, con rol, turno, fecha, tipo de contrato (permanente / temporal / en período de prueba), causal (renuncia / despido / vencimiento) y **si la posición se cubrió o no**. Es la única forma de estimar `Ω` y de obtener un `τ` restringido a permanentes. Sin esto, `Ω` es un supuesto y el rango se queda ancho.
4. **El instrumento colectivo del sitio**: Enterprise Agreement (Australia — manda sobre MA000084 y puede fijar garantías de horas, topes de casuals y esquemas de redundancy más generosos que las NES), CCT y su rama (Argentina — verificar si hay acuerdo de **banco de horas** del art. 197 bis, que anula V2 como vía de caja), instrumento colectivo (Chile — puede mejorar el recargo del 50 %), y estado del convenio (EE.UU.).
5. **La jurisdicción exacta del sitio** (EE.UU.): federal por defecto vs **New Jersey**, que cambia `m*` de ~12 a 7–9.
6. **Distribución de antigüedad de la dotación permanente afectada.** Sin ella, `S` sólo se parametriza por escenarios.
7. **Pronóstico de volumen del CD a 12–24 meses**, y **decisión explícita de Finanzas** sobre si banca *cost avoidance* o sólo *hard savings*. En Chile, con ~86 % del `labor_flex_share` viniendo de V3, esa decisión sola determina si el número vale 0,45 o vale 0,13.
8. **El contrato con el 3PL**, si lo hay: preaviso, volumen mínimo comprometido, mecanismo de ajuste de tarifa y fecha de aniversario.
9. **Registro de todos los proyectos concurrentes que tocan la misma población** (regla R4). Sin esto, la cartera se sobrevende sin que ningún proyecto individual lo vea.

---

## 7. Los tres errores más probables al aplicar estos números

### Error 1 — Reportar el run-rate como si fuera caja del año 1
**Frecuencia observada: 1 de 4 informes, y el error valía 0,43 puntos.** El informe de Chile calculó correctamente `flex_cash_y1 ≈ 0,55`, escribió textualmente *"reportar este número y no el run-rate cuando se calcula payback"*, y a continuación reportó **0,88** en el campo de la estimación.

**Por qué pasa:** la aritmética del run-rate es limpia y satisface (`s_OT·c_OT + s_TEMP·c_TEMP + s_PERM·a_ATT` tiende a 1 cuando el proyecto es chico frente a `N_base`). La aritmética de la caja exige multiplicar el bloque permanente por `θ`, y `θ` no sale de ninguna estadística.

**Cómo evitarlo:** reportar **siempre las dos salidas juntas**, con la fórmula a la vista. Regla práctica: con reducciones repartidas a lo largo del año, `flex_cash_y1 ≈ 0,45–0,55 × flex_run_rate`. Si alguien presenta un solo número, preguntar cuál de los dos es.

### Error 2 — Fijar `Ω` o `a_ATT` en 1,0 porque "la atrición sobra"
**Frecuencia observada: 3 de 4 informes.** El argumento es siempre el mismo y siempre suena razonable: *"el proyecto necesita 0,42 FTE y la capacidad de atrición del sitio es de 16–21 FTE/año, así que `a_ATT` = 1"*. En EE.UU. eso producía el 68 % de la moda; en Australia, el 59 %; en los dos casos con **cero datos de país detrás**.

**Por qué está mal, en tres capas:**
1. **Emparejamiento rol/turno.** Las horas liberadas son de picking, en un turno concreto. Hace falta una baja **en ese rol y ese turno**, más la decisión efectiva de no cubrirla. Si la rotación está en el turno día y el proyecto libera el turno noche, `Ω` no es 1, es 0 para esas horas.
2. **Granularidad.** 1.000 horas/año son **0,42–0,51 FTE** según el país. No se despide medio operario. Y las horas de un proyecto de mejora continua típicamente vienen **repartidas en minutos por turno entre decenas de operarios** (12 min/turno × 40 personas), forma en la que **no son convertibles en cabezas** sin rediseñar el plan de dotación. Todo el bloque V3+V4 supone divisibilidad y apilabilidad perfectas del trabajo, y ningún informe lo enunció.
3. **Fijar en su máximo teórico el parámetro que uno mismo declara dominante y no medido produce un techo, no un modo.** Los tres informes declararon en sus caveats que `Ω` es la variable que más mueve el resultado y que no existe en ninguna fuente pública — y después la fijaron en 1.

**Cómo evitarlo:** `Ω` entre 0,45 y 0,80 en el caso base según cobertura de turno, roles licenciados (montacargas, reach truck, HACCP, hazmat, cámara de frío) y colchón de ausentismo; **sensibilidad obligatoria a 0,50 y 0,75**; y clasificar 6–12 meses de bajas reales del sitio antes de firmar. El ancla empírica más cercana que existe es el 46–52 % de bajas no repuestas de la EIL argentina.

### Error 3 — Leer `s_TEMP` en la fila equivocada de la tabla equivocada
Este error tiene **dos versiones opuestas** y ambas aparecieron en el estudio.

**Versión A — subregistro por código industrial.** El trabajador de agencia que hace picking en un CD es, estadísticamente, empleado de la agencia: su industria es "servicios de empleo", no "almacenamiento". Leer `s_TEMP` sobre el código del almacén **excluye por construcción la mayor parte de la flexibilidad que se quiere medir**. Probado en tres sistemas independientes: EE.UU. (394.220 movedores de material en NAICS 561320, cero en 493), Chile (rama H rota 28,1 %/año, rama N donde viven las EST rota 45,6 %), Australia (labour hire en ANZSIC 7212, fuera de la división I).

**Versión B — confundir sector con tamaño de empresa.** Ésta es más sutil y le costó al informe chileno su hallazgo bandera. La fila sectorial "Transporte y almacenamiento" de la Encla da **10,7 % temporal**, muy por debajo del 22,5 % nacional — y el informe concluyó que "un CD chileno tiene mucha menos válvula contractual de la que sugiere el imaginario del sector". Pero **la Tabla 2 del mismo capítulo** da **25,5 % en gran empresa** contra 7,7 % en microempresa. La fila sectorial es una **mezcla por tamaño dominada por empresas chicas**. Un CD es gran empresa. El informe aplicó la corrección por tamaño para las EST (*"un CD es gran empresa: la tasa relevante es 14,3 %, no 1,9 %"*) y **no la aplicó a la pieza mayor**.

**Cómo evitar las dos versiones a la vez:** medir `s_TEMP` **bottom-up** — horas facturadas por la agencia y por los contratistas ÷ horas totales del turno afectado. La factura de la agencia es el mejor dato que existe y el cliente ya lo tiene. Cuando haya que usar estadística oficial, usar **cruces ocupación × industria** (OEWS en EE.UU.) o encuestas de arreglos de trabajo (ABS Working Arrangements), nunca la tabla de contratos por industria, y **siempre condicionando por tamaño de empresa**. Y escribir en cada celda si la cifra es *industry-of-record del trabajador* o *industry-of-workplace*: en logística difieren mucho.

### Error 3 bis (honorífico, pero es el que más plata destruye)
**Dejar que cada proyecto de la cartera reclame el 100 % de `Ω·τ·N_base`.** La capacidad de atrición es un **presupuesto compartido y finito**. Un CD argentino de 150 permanentes con `Ω`=0,45 libera ~16 FTE/año; tres o cuatro proyectos medianos ya la consumen. En Chile, con `τ` corregido a 18–22 % para permanentes, un CD de 150 tiene **11–15 FTE/año**, no 21. Este doble conteo **no es visible desde adentro de ningún proyecto individual** — sólo aparece cuando alguien suma la cartera. Requiere un registro central de asignación por CD y por año.

---

## Cierre honesto sobre la calidad del estudio

**Lo que quedó sólido:** la evidencia de V2 en Australia (`s_OT` de ANZSIC 53 = 3,74 %, el único `s_OT` genuinamente medido sobre almacenamiento en los cuatro países); la evidencia de V3 y V4 en EE.UU. (JOLTS reproducido exacto, régimen at-will verificado contra el estatuto, 19,5 % de layoffs como evidencia revelada); el registro administrativo censal chileno del INE; y la serie mensual de la EIL argentina, que es la única fuente del estudio que permite aproximar `Ω` desde dato público.

**Lo que quedó flojo y hay que decirlo:** el `s_OT` de Chile y Argentina es un supuesto, no una medición — **ninguno de los dos países publica horas extras por rama, y Argentina no publica horas en absoluto**. El `s_TEMP` en horas no existe en ningún país. Los valores de EPL de la OCDE quedaron sin verificar en los cuatro casos. Y `Ω`, que es el parámetro que decide el resultado, no está medido en ninguna parte del mundo.

**Por eso los rangos son anchos.** Un intervalo angosto sobre un parámetro dominante que no tiene fuente pública en ningún país no es precisión: es una afirmación que la evidencia no respalda. Los dos números que decidirían cualquier caso real **no salen de estadística pública** — salen de la nómina y de la cuenta de proveedores del cliente.

---

# Anexo — marco metodologico

# Marco de medición: `labor_flex_share`
**Rol: metodología + benchmarks globales del sector. No incluye hallazgos de país.**
Fecha de extracción de todos los datos: **2026-08-01**.

---

## 0. Definición formal y unidad de medida

**Constructo:** dado un proyecto que libera `H` horas de trabajo directo al año en un centro de distribución, `labor_flex_share` es la fracción de `H` que se convierte en **egreso de caja evitado dentro de 12 meses**.

Tres decisiones de alcance que hay que fijar antes de medir nada:

**A0.1 — La base es la hora, no el sitio.** `labor_flex_share` es una propiedad **de las horas liberadas**, no del centro. Si el proyecto toca el turno noche de picking, los parámetros se miden sobre el turno noche de picking, no sobre el CD completo. Un CD con 30% de eventuales puede tener 0% de eventuales en el turno que el proyecto ataca.

**A0.2 — `H` se mide contra horas efectivamente pagadas (nómina), no contra horas estándar ni dotación presupuestada.** Los CD operan crónicamente con vacantes abiertas. Horas liberadas que hoy nadie trabaja no generan caja: generan cierre de vacante (evitación de costo, no reducción de nómina).

**A0.3 — Dos salidas, no una.** Hay que reportar ambas o el número es ambiguo:
- `flex_run_rate` = ahorro anualizado en régimen al mes 12 (para valorización / NPV)
- `flex_cash_y1` = caja efectivamente ahorrada entre el mes 1 y el 12 (para payback y P&L)

Regla práctica: cuando las reducciones llegan repartidas a lo largo del año, `flex_cash_y1 ≈ 0,45–0,55 × flex_run_rate`. Reportar un run-rate como si fuera caja del año 1 es el sobreestimador silencioso más común.

---

## 1. Fórmula

### 1.1 Paso 1 — Partición exhaustiva y excluyente de `H` (esto es lo que elimina el doble conteo)

Toda hora liberada pertenece a **exactamente un** bucket. La partición se hace por atributo de la hora, no por atributo de la persona:

| Bucket | Definición | Regla de prioridad |
|---|---|---|
| `h_OT` | Horas pagadas con recargo (por encima del umbral legal/convencional de jornada), **sin importar quién las trabaje** | **El recargo domina al contrato.** Una hora extra trabajada por un eventual va a `h_OT`, no a `h_TEMP` |
| `h_TEMP` | Horas a tarifa normal ejecutadas por trabajo no permanente: casual (AU), agencia (US), suministro transitorio/EST y plazo fijo (CL), agencias de servicios eventuales (AR) | Segunda prioridad |
| `h_PERM` | Horas a tarifa normal de empleados permanentes de planilla | Residual |

$$H = h_{OT} + h_{TEMP} + h_{PERM}$$
$$s_{OT}+s_{TEMP}+s_{PERM}=1,\qquad s_i = h_i/H$$

**Por qué la prioridad va al recargo:** eliminar una hora extra de un eventual ahorra la tarifa completa con recargo (1,25–2,0×). Si esa hora se clasificara como `h_TEMP` se le asignaría 1,0× y se subestimaría. Y si se contara en ambos buckets, se contaría dos veces. La prioridad `OT > TEMP > PERM` resuelve las dos cosas a la vez.

### 1.2 Paso 2 — Tasas de conversión por bucket

$$\boxed{\;\texttt{labor\_flex\_share} \;=\; s_{OT}\,c_{OT} \;+\; s_{TEMP}\,c_{TEMP} \;+\; s_{PERM}\,(a_{ATT} + a_{SEV})\;}$$

con todos los términos en base **horas**, resultado en `[0, 1]`.

| Parámetro | Qué es | Cómo se estima | Valor típico |
|---|---|---|---|
| `c_OT` | Fracción del sobretiempo que realmente se puede apagar en 12 meses | `1 − (fracción de OT garantizado por convenio/EA/roster fijo)` | 0,85–1,00 |
| `c_TEMP` | Fracción de horas eventuales cancelables en 12 meses | Casual semanal → ≈1,0. Plazo fijo con `k` meses restantes → `(12−k)/12`. Agencia con volumen comprometido o preaviso `p` semanas → `1 − p/52` | 0,6–1,0 |
| `a_ATT` | Fracción de `h_PERM` absorbible por rotación sin reemplazo (V3) | Ver §1.3 y §4 | 0–1 |
| `a_SEV` | Fracción **residual** de `h_PERM` que se elimina por despido con caja neta positiva (V4) | `(1 − a_ATT) × f_SEV` | 0–1 |

### 1.3 Paso 3 — Desagregación de `h_PERM` (V3 y V4)

Convertir horas a cabezas:
$$N_{req} = \frac{h_{PERM}}{A}$$
donde `A` = horas pagadas por FTE-año en el sitio (jornada legal − feriados − vacaciones + ausentismo pagado). **`A` es un parámetro de país y debe documentarse con fuente**; usar 2.080 en todos lados introduce un sesgo de 8–15%.

**V3 — capacidad de atrición (restricción de flujo × restricción de cobertura):**
$$N_{ATT}^{max} = \Omega \cdot \tau \cdot N_{base}$$

- `τ` = tasa anual de separación **voluntaria de la población permanente afectada** (no del sitio, no nacional)
- `N_base` = dotación permanente de la población afectada
- `Ω` = **tasa de captura sin reemplazo** ∈ [0,1]: fracción de las bajas que efectivamente se puede dejar sin cubrir dada la cobertura de turnos, la dotación mínima por turno, licencias (montacarguista, reach truck, HACCP, hazmat) y restricciones de convenio. Ver §4.

$$a_{ATT} = \min\!\left(1,\; \frac{\Omega \cdot \tau \cdot N_{base}}{N_{req}}\right)$$

**V4 — despido, con la regla de quiebre:** una cabeza permanente despedida en el mes `m`, con costo total de salida `S` expresado **en meses de costo cargado** (indemnización + preaviso + vacaciones proporcionales + cargas sobre la indemnización):

$$\text{caja neta año 1} = C_{anual}\left[\frac{12-m}{12} - \frac{S}{12}\right]$$

$$\Rightarrow \text{genera caja en 12 meses solo si } m < 12 - S$$

**Mes de quiebre `m* = 12 − S`.** Con `S = 5` meses, un despido ejecutado en el mes 8 destruye caja en el año 1 aunque mejore el run-rate. Esta es la mecánica que separa a Estados Unidos de Chile y Argentina, y es donde el índice EPL de la OCDE **no** sirve como input directo (§2.4).

$$f_{SEV} = \frac{\max(0,\; 12 - S - m_{ejec})}{12}\quad\text{(0 si el proyecto no autoriza despidos)}$$

### 1.4 Multiplicador de caja (separado, para no contaminar la share)

`labor_flex_share` es en horas. La caja no es proporcional a las horas porque una hora extra vale más que una normal y una hora de agencia vale más que una interna (markup de la agencia). Se reporta **aparte**:

$$\text{Caja}_{12m} = H\cdot \bar{w}\Big[s_{OT}c_{OT}\mu_{OT} + s_{TEMP}c_{TEMP}\lambda_{TEMP} + s_{PERM}(a_{ATT}+a_{SEV})\Big]\cdot\theta \;-\; N_{SEV}\cdot S\cdot\frac{C_{anual}}{12}$$

- `w̄` = costo cargado por hora normal de un permanente
- `μ_OT` = recargo efectivo (legal + convenio) — **cada investigador debe verificarlo y citarlo con URL, no asumirlo**
- `λ_TEMP` = tarifa de facturación de agencia ÷ costo cargado interno. Habitualmente **> 1**: apagar una hora de agencia ahorra más que una hora interna. Ignorar esto subestima V1 sistemáticamente.
- `θ` = factor de timing (≈0,5 para caja año 1 con llegada uniforme; 1,0 para run-rate)

### 1.5 Reglas anti-doble-conteo (obligatorias)

| # | Regla |
|---|---|
| **R0** | `H` se mide contra horas pagadas reales. Horas cubiertas por vacantes abiertas → evitación, no ahorro. Se reportan en línea separada. |
| **R1** | **Particionar, no sumar.** Nunca tomar "30% eventual" de una fuente y "10% sobretiempo" de otra y sumarlos: son porcentajes sobre bases solapadas. Cada hora se etiqueta una vez con prioridad `OT > TEMP > PERM`. |
| **R2** | **Disciplina de denominador.** `s_OT` y `s_TEMP` deben calcularse sobre el **mismo** total de horas del mismo centro de trabajo. Si vienen de fuentes distintas (nómina vs. encuesta nacional), renormalizar a suma ≤1 y mandar el residuo a `s_PERM`. Declarar la renormalización. |
| **R3** | `a_ATT` y `a_SEV` son mutuamente excluyentes por cabeza. `a_SEV` se aplica **solo al residuo**: `a_SEV = (1 − a_ATT) × f_SEV`. |
| **R4** | **La atrición es un presupuesto compartido y finito.** `Ω·τ·N_base` se reparte entre *todos* los proyectos concurrentes que tocan la misma población en el mismo año. Si tres proyectos reclaman cada uno el 100% de la capacidad de atrición del CD, la cartera está sobrevendida ~3×. Asignar explícitamente. |
| **R5** | No contar el ahorro de reclutamiento/onboarding evitado dentro de `labor_flex_share`. Va en línea aparte, y solo la parte que es caja real (fee de agencia, examen preocupacional, EPP), no horas internas de RRHH. |
| **R6** | Si el CD está en crecimiento de volumen, "no reemplazar" **no** baja la nómina: la hace subir menos. Separar **hard savings** (línea de nómina baja contra año anterior) de **cost avoidance**. Finanzas normalmente solo banca lo primero. |

### 1.6 Ejemplo aritmético — ILUSTRATIVO, NO ES UN RESULTADO

*Números inventados para mostrar la mecánica. Ningún dígito de abajo es un hallazgo.*

`H = 1.000 h/año`. Partición medida en nómina del turno afectado: `s_OT = 0,08`, `s_TEMP = 0,25`, `s_PERM = 0,67`.
`c_OT = 0,95`; `c_TEMP = 0,90`; `A = 1.850 h` → `N_req = 670/1.850 = 0,36 FTE`.
`N_base = 40`, `τ = 0,35`, `Ω = 0,45` → `N_ATT_max = 6,3 FTE` ≫ `0,36` → `a_ATT = 1,0` → `a_SEV = 0`.

`labor_flex_share = 0,08(0,95) + 0,25(0,90) + 0,67(1,0) = 0,076 + 0,225 + 0,670 = 0,97` **(run-rate)**
`flex_cash_y1 ≈ 0,076 + 0,225 + 0,670×0,5 ≈ 0,64`

Lección de la mecánica: con `H` chico frente a `N_base`, V3 casi nunca es la restricción y `labor_flex_share` tiende a 1 en run-rate. La restricción real aparece cuando `N_req` se acerca a `Ω·τ·N_base` — es decir, en proyectos grandes o en carteras de proyectos (R4). **El número interesante del estudio va a estar en `Ω` y en `S`, no en `τ`.**

### 1.7 Qué debe devolver cada investigador de país (contrato de datos)

Por país, con URL y año en cada celda, y `no encontrado` cuando corresponda:

`s_TEMP` sectorial (almacenamiento, no promedio nacional) · figura legal exacta y su nombre local · preaviso y costo de terminar el vínculo eventual · `s_OT` sectorial + umbral legal de jornada + `μ_OT` legal y convencional · `τ` sectorial (separaciones totales y voluntarias, anual) · `A` (horas pagadas por FTE-año) · `S` (fórmula de indemnización + preaviso + tope + tratamiento de cargas sobre la indemnización) · plazos procesales de despido individual y colectivo · reformas 2020–2026 con fecha de vigencia · EPL OCDE como *contexto*, no como input.

---

## 2. Benchmarks globales del sector almacenamiento / logística

### 2.1 V3 — Rotación

| Métrica | Valor | Año | Fuente | Conf. |
|---|---|---|---|---|
| Separaciones totales, *Transportation, warehousing, and utilities* (US) | **4,00%/mes → 48,0% anualizado** | 2025 | BLS JOLTS, serie `JTS480099000000000TSR` | Alta |
| idem | 3,94%/mes → 47,3% | 2024 | idem | Alta |
| Renuncias (quits), mismo sector | **2,17%/mes → 26,0% anualizado** | 2025 | `JTS480099000000000QUR` | Alta |
| Despidos y bajas (layoffs & discharges), mismo sector | 1,62%/mes → 19,5% anualizado | 2025 | `JTS480099000000000LDR` | Alta |
| Separaciones totales, *total nonfarm* (US) | 3,29%/mes → 39,5% anualizado | 2025 | `JTS000000000000000TSR` | Alta |
| Separaciones totales, *total private* (US) | 3,63%/mes → 43,5% anualizado | 2025 | `JTS100000000000000TSR` | Alta |

Fuente: https://www.bls.gov/jlt/ — extraído vía `https://api.bls.gov/publicAPI/v2/timeseries/data/JTS480099000000000TSR?startyear=2024&endyear=2025` (la API pública funciona sin key; `www.bls.gov` devuelve 403 a fetchers).

**Advertencias que hay que trasladar al informe:**
- **No existe serie JOLTS solo-almacenamiento.** Verificado: `JTS493000000000000TSR`, `JTS490000000000000TSR` y `JTS480000000000000TSR` devuelven *"Series does not exist"*. El corte más fino publicado es `480099` = transporte + almacenamiento + **utilities**. Utilities tiene rotación muy baja y camioneros tienen un patrón distinto al del piso del CD.
- El ratio logística/economía es **1,22× nonfarm** y **1,10× privado** — no el "1,5×" que circula. Un número solo-almacén sería mayor, pero **no lo publica ninguna agencia oficial de EE.UU.**
- Anualizar ×12 una tasa mensual JOLTS cuenta repetidamente el churn de eventuales de corta permanencia y **sobrestima** cuántas *posiciones permanentes presupuestadas* quedan vacantes. Para `τ` usar el HRIS del cliente restringido a permanentes; JOLTS es banda de sanidad, no input.

**Benchmark sectorial propio de la industria (metodología publicada, valores de pago):** WERC *DC Measures* define **"annual workforce turnover"** entre sus 38 métricas de benchmarking de centros de distribución — https://werc.org/page/ASSESS-DC_Measures · release 2025: https://werc.org/news/702949/WERC-Releases-2025-DC-Measures-Report-with-a-Focus-on-Combining-Vision-with-Vigilance-.htm · marco general: https://werc.org/page/ASSESS-Benchmarking_Overview

**Cifra a NO usar:** el "43% de rotación en warehousing" que aparece en gitnux.org, opensend.com y similares **no tiene fuente primaria rastreable**. Si aparece en un borrador de país, rechazarlo.

### 2.2 V2 — Sobretiempo como % de horas pagadas

**El mejor benchmark warehouse-específico disponible en el mundo** (ningún organismo publica esto para EE.UU., Australia, Chile ni Argentina):

**ONS · Annual Survey of Hours and Earnings 2025 (provisional, abril 2025), Reino Unido, todos los empleados, medias semanales:**

| SIC 2007 | Total pagadas | Básicas | Sobretiempo | **OT / total** |
|---|---|---|---|---|
| **52 — Warehousing and support activities for transportation** | 39,0 | 37,1 | **1,9** | **4,9%** |
| 49 — Land transport | 39,8 | 37,0 | 2,8 | 7,0% |
| 53 — Postal and courier | 37,3 | 34,5 | 2,7 | 7,2% |
| H — Transportation and storage (agregado) | 38,5 | 36,2 | 2,3 | 6,0% |
| C — Manufacturing | 38,2 | 36,9 | 1,3 | 3,4% |
| 78 — Employment activities (agencias) | 29,3 | 28,6 | 0,7 | 2,4% |
| Todos los empleados | 32,8 | 32,2 | 0,7 | 2,1% |

Fuente: ASHE Table 4 (industry 2-digit SIC), tablas 4.9a (total), 4.10a (básicas), 4.11a (sobretiempo) — https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/industry2digitsicashetable4 (archivo `ashetable42025provisional.zip`). **Verificación interna hecha: básicas + sobretiempo = total en cada fila**, lo que confirma que las medias están calculadas sobre todos los empleos (la columna "Median" de la tabla de sobretiempo NO es comparable con la media y no debe usarse). Confianza alta. Es UK, no es ninguno de los cuatro países.

**EE.UU. — único dato oficial de horas extra, y es de manufactura, no de almacén:**

| Serie CES | Métrica | 2025 | 2024 |
|---|---|---|---|
| `CES3000000004` / `CES3000000002` | OT / horas totales, manufactura, todos los empleados | 2,90 / 40,08 = **7,2%** | 2,91 / 40,03 = 7,3% |
| `CES3000000009` / `CES3000000007` | OT / horas totales, manufactura, producción y no supervisorios | 3,72 / 41,02 = **9,1%** | 3,60 / 40,68 = 8,8% |
| `CES4349300002` | Horas semanales medias, **NAICS 493 Warehousing and storage**, todos los empleados | **40,17** | 40,36 |
| `CES4349300007` | idem, producción y no supervisorios | **38,51** | 38,73 |

https://www.bls.gov/ces/ — **verificado que `CES4349300004` y `CES4349300009` no existen: BLS publica horas extra solo para manufactura.**

**Trampa aritmética que hay que bloquear:** en NAICS 493 las horas medias de producción/no supervisorios son **38,51 < 40**, y sin embargo hay sobretiempo. Nunca estimar `s_OT = max(0, horas_medias − 40)/horas_medias`: la media mezcla part-timers (que tiran hacia abajo) con full-timers en overtime (que tiran hacia arriba). La distribución es bimodal. `s_OT` **solo** se mide sobre horas pagadas con recargo en nómina.

**Triangulación cruzada, marcada como derivada (no es una medición):** ratio UK almacén/manufactura = 4,9/3,4 = **1,44**. Aplicado a la manufactura de EE.UU. (7,2% todos los empleados / 9,1% producción) sugiere un prior de **~10–13% de horas pagadas en sobretiempo para almacenamiento en EE.UU.** El investigador de EE.UU. debe usar esto solo como banda de plausibilidad contra la nómina del cliente, y decir que es derivado.

### 2.3 V1 — Penetración de trabajo eventual / de agencia

**EE.UU. — OEWS mayo 2025 (BLS), cruce ocupación × industria.** Esta es la vía correcta y evita el error de clasificación (§3.1):

| | Total nacional | En NAICS 493 (Warehousing and storage) | En NAICS 561320 (Temporary help services) |
|---|---|---|---|
| 53-7062 Laborers and freight, stock, and material movers, hand | 2.950.280 | 433.060 | **394.220 (13,4% de la ocupación)** |
| 53-7065 Stockers and order fillers | 2.833.810 | 457.740 | 39.500 (1,4%) |
| **Todas las ocupaciones** | — | **1.963.680** | **2.593.250** |

https://www.bls.gov/oes/ — extraído vía `https://api.bls.gov/publicAPI/v2/timeseries/data/OEUN000000056132053706201` (formato de serie OEWS: `OEU` + `N` + `0000000` + industria(6) + ocupación(6) + `01`).
Consistencia verificada contra CES: OEWS NAICS 493 = 1.963.680 vs CES media 2025 = 1.865.300; OEWS 561320 = 2.593.250 vs CES 56132 media 2025 = 2.496.970. Coherente.

**Banda derivada (marcada como derivada):** si se define "trabajo de piso de almacén" como 53-7062 + 53-7065, la cota superior de penetración de agencia es `(394.220+39.500) / (890.800+433.720) = **32,7%**` — supuesto de que *todos* los movedores de material de agencia están colocados en almacenes, lo que es falso (también van a manufactura y retail). Cota inferior defendible: **13,4%** (share de la ocupación en payroll de agencia a nivel nacional). **Reportar como banda 13%–33%, no como punto.**

**EE.UU. — American Staffing Association** (encuesta de la asociación, metodología publicada): ~**2,2 millones** de empleados temporales y por contrato en una semana promedio de 2024; **12,7 millones** contratados a lo largo de 2023; mezcla por segmento: **36% Industrial** (el mayor), 24% oficina-administrativo, 21% profesional-gerencial, 11% ingeniería/TI/científico, 8% salud; 73% trabaja tiempo completo.
https://americanstaffing.net/research/fact-sheets-analysis-staffing-industry-trends/staffing-industry-statistics/ · metodología: https://americanstaffing.net/research/asa-staffing-industry-data/staffing-employment-sales-survey/ — **Confianza media** (asociación de industria). Nota: no cuadra con CES NAICS 56132 (2.611k en 2024, 2.497k en 2025) porque el universo es distinto; no mezclar.

**Unión Europea — Eurostat LFS 2024, empleados temporales como % de empleados 15–64:**

| País/agregado | NACE H (Transportation and storage) | Todas las NACE | NACE N (Administrative & support, contiene N78 agencias) |
|---|---|---|---|
| **EU27** | **10,1%** | **12,8%** | **15,4%** |
| Países Bajos | 24,5% | 26,0% | 29,1% |
| Polonia | 16,1% | 14,9% | 32,0% |
| Portugal | 14,4% | — | — |
| Italia | 12,4% | 14,8% | 19,9% |
| Francia | 12,3% | 15,2% | 16,1% |
| España | 10,4% | 16,0% | 14,0% |
| Alemania | 9,0% | 11,4% | 11,7% |
| Hungría / Lituania | 1,7% / 1,7% | — | — |

Datasets `lfsa_etgan2` (empleados temporales) y `lfsa_eegan2` (empleados totales), share calculado por mí como cociente. https://ec.europa.eu/eurostat/databrowser/view/lfsa_etgan2/ · https://ec.europa.eu/eurostat/databrowser/view/lfsa_eegan2/ · API: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/lfsa_etgan2?format=JSON&sex=T&age=Y15-64&nace_r2=H&time=2024`. Confianza alta. Sin desagregación disponible a H52 (verificado: `nace_r2=H52` devuelve vacío).

**Este cuadro es la evidencia dura del error nº1**: en la UE, transporte y almacenamiento (10,1%) aparece **por debajo** del promedio de toda la economía (12,8%). No es que la logística use menos trabajo eventual — es que los trabajadores de agencia se codifican en NACE N (15,4%), no en H.

**Australia — ABS, Working Arrangements, agosto 2025:** 19% de todos los empleados son casual (2,4 millones); 20% sin licencia paga por vacaciones ni enfermedad; **Transport, postal and warehousing: 125.600 empleados casual** (nivel; el porcentaje requiere el denominador del mismo data cube). Industrias más casualizadas: alojamiento y comida 58%, agricultura 38%, artes y recreación 37%.
https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/working-arrangements/latest-release
**Nota crítica de continuidad:** la ABS indica que agosto 2025 fue la última aplicación de la Characteristics of Employment survey en su forma actual. **El investigador de Australia debe sacar numerador y denominador del mismo data cube** — no dividir 125.600 por empleados de Labour Force Detailed (universos distintos: empleados vs. personas ocupadas incl. owner-managers).

**Global (SIN VERIFICAR):** World Employment Confederation, *Economic Report 2025* — https://wecglobal.org/uploads/2025/02/WEC-Economic-Report-2025.pdf (6,3 MB). Publica la *agency work penetration rate* (FTE de agencia / empleo total) por país. **No pude extraer el texto del PDF, así que no reporto ningún valor.** Un snippet de buscador mencionaba 1,8% global para 2023; **tratarlo como no verificado** hasta leerlo en el PDF. Landing page: https://weceurope.org/publication-post/economic-report-2025/

### 2.4 V4 — Protección del empleo (contexto, no input)

**OCDE, Indicators of Employment Protection, escala 0–6, valores vigentes 2025 (extraídos 2026-08-01):**

| País | EPL_R v4 (despido individual, contrato regular) | EPL_T v3 (contratos temporales) | EPL_CD v4 (despido colectivo) |
|---|---|---|---|
| **Estados Unidos** | **0,75** | 0,33 | 0,81 |
| **Australia** | **1,66** | **1,54** (subió de 1,04 en 2024) | 1,81 |
| **Chile** | **2,45** | 2,42 | 2,06 |
| **Argentina** | **2,57** (bajó de 2,62 en 2025) | **2,54** (bajó de 3,04 en 2025) | 2,54 |
| Promedio OCDE (2024) | 2,16 | 2,22 | 2,35 |
| México / España / Francia / Alemania / Reino Unido | 2,38 / 2,43 / 2,45 / 2,22 / 1,74 | 4,25 / 3,98 / 3,62 / 1,67 / 0,54 | 2,55 / 2,43 / 3,25 / 2,61 / 2,31 |

Dataflow SDMX `OECD.ELS.JAI:DSD_EPL@DF_EPL(1.0)`; descarga: `https://sdmx.oecd.org/public/rest/data/OECD.ELS.JAI,DSD_EPL@DF_EPL,1.0/all?startPeriod=2019&format=csvfilewithlabels` · página oficial: https://www.oecd.org/en/data/datasets/oecd-indicators-of-employment-protection.html (devuelve 403 a fetchers; la API funciona).
**Para Chile y Argentina existe además la base OCDE-BID para América Latina y el Caribe:** https://www.oecd.org/en/data/datasets/oecd-idb-database-on-summary-indicators-of-employment-protection-legislation-epl-in-latin-american-and-the-caribbean.html · metodología: https://www.oecd.org/els/emp/EPL-Document-LAC-Methodology-ENG.pdf

**Advertencias operativas:**
1. **Argentina no tiene EPL_T versión 4.** Para comparar contratos temporales entre los cuatro países usar **versión 3** (única con cobertura completa). Mezclar versiones es un error de comparabilidad.
2. **Las series están congeladas salvo reforma legislativa.** Verifiqué el movimiento 2019→2025: EE.UU. y Chile constantes en todo el período; Australia sube EPL_T en 2024; Argentina baja EPL_R y EPL_T en 2025. Es un **índice de rigidez legal, no una medición anual**. Documentar la fecha de vigencia de la reforma detrás de cada cambio.
3. **EPL no es dinero.** El índice ordena países; no da `S`. Para `S` hacen falta la fórmula de indemnización (meses por año de servicio), el tope, el preaviso, el tratamiento tributario/previsional de la indemnización y los plazos procesales. Un país puede tener EPL alto y `S` bajo (proceso lento pero barato) o al revés.

---

## 3. Los tres errores metodológicos más probables

### Error 1 — Desplazamiento de clasificación: el trabajo eventual no está en el código industrial del almacén

**Qué pasa.** El trabajador de agencia que hace picking en un CD es, estadísticamente, empleado de la agencia. Su industria es "servicios de empleo", no "almacenamiento". Cualquier estadística de penetración temporal leída sobre el código industrial del almacén **excluye por construcción a la mayor parte de la flexibilidad que estamos tratando de medir**.

**Evidencia dura de dos sistemas estadísticos independientes:**
- EE.UU.: **394.220** *laborers and freight, stock and material movers* están en NAICS **561320** (temp help services) — cero de ellos aparece en NAICS 493, cuyo total es 1.963.680 (OEWS mayo 2025).
- UE: NACE H muestra **10,1%** de empleados temporales en 2024, **menos** que el 12,8% de toda la economía, mientras NACE N (donde viven las agencias) marca 15,4%. Leer el 10,1% y concluir "la logística usa menos trabajo eventual que el promedio" es exactamente el error.

**Cómo evitarlo.**
1. Estimar `s_TEMP` **bottom-up**: horas de agencia/casual facturadas al CD ÷ horas totales del CD. La factura de la agencia es el mejor dato que existe.
2. Cuando se usa estadística oficial, usar **cruces ocupación × industria** (OEWS en EE.UU.) o encuestas de arreglos de trabajo (ABS Working Arrangements), no la tabla de contratos por industria.
3. Escribir explícitamente en cada celda del informe si la cifra es *industry-of-record del trabajador* o *industry-of-workplace*. Son cosas distintas y en logística difieren mucho.

### Error 2 — Agregación: el "sector" publicado está dominado por otra actividad

**Qué pasa.** Los cortes sectoriales disponibles bundlean el piso del CD con camioneros, correo, ferrocarril, aéreo y (en EE.UU.) utilities. Esas poblaciones tienen rotación, mezcla contractual y patrón de sobretiempo distintos.

**Evidencia dura.** UK ASHE 2025, dentro del mismo encabezado "Transportation and storage": sobretiempo medio de **2,8 h/semana en SIC 49 (transporte terrestre)** vs **1,9 h/semana en SIC 52 (almacenamiento)** — **47% de diferencia dentro del mismo agregado**. En EE.UU. el problema es peor: verifiqué que JOLTS **no publica** almacenamiento por separado (`JTS493000000000000TSR` → *"Series does not exist"*); el corte más fino es transporte + almacenamiento + **utilities**, y utilities es de rotación estructuralmente baja, lo que **deprime** el `τ` observado.

**Cómo evitarlo.**
1. Bajar un dígito siempre que la agencia lo permita (SIC 52, NAICS 493, ANZSIC 53) y decir explícitamente qué queda adentro.
2. Cuando solo hay agregado, **decirlo, ampliar la banda de incertidumbre y estimar el sesgo de dirección** (¿el agregado sube o baja el parámetro respecto del almacén puro?). No usarlo en silencio.
3. Preferir siempre la ocupación sobre la industria cuando la ocupación identifica mejor al trabajador de piso (movedores de material, stockers, order fillers).

### Error 3 — Doble conteo entre canales, y confusión stock/flujo en la atrición

Tiene dos formas y las dos son frecuentes:

**(a) Sumar shares sobre bases solapadas.** Tomar "30% de las horas las hacen eventuales" y "10% de las horas son extras" de dos fuentes distintas y sumar 40% de flexibilidad. Las horas extras de los eventuales están en los dos números. Se corrige con la partición de §1.1 y la regla de prioridad `OT > TEMP > PERM`.

**(b) Tratar la rotación (flujo) como capacidad disponible (stock), y no repartirla.** Tres sub-errores concretos:
- Multiplicar una tasa mensual JOLTS ×12 y usarla como `τ` de permanentes: los ~48%/año de *transportation, warehousing and utilities* incluyen churn repetido de gente de muy corta permanencia; sobreestima cuántas **posiciones permanentes presupuestadas** quedan vacantes.
- Dejar que cada proyecto de la cartera reclame el 100% de `Ω·τ·N_base`. La capacidad de atrición es un presupuesto compartido (R4). Con tres proyectos concurrentes sobre la misma población, la cartera está sobrevendida ~3×. **Este es el doble conteo que más plata destruye en la práctica**, porque no es visible dentro de ningún proyecto individual.
- Confundir run-rate con caja del año 1 (A0.3).

**Cómo evitarlo.** Partición única por hora + registro central de asignación de capacidad de atrición por CD y por año + reportar siempre `flex_run_rate` y `flex_cash_y1` por separado.

**Menciones honoríficas** (menores pero reales): mezclar base-horas con base-costo (§1.4); asumir que las horas liberadas se reparten uniformemente entre turnos cuando el proyecto ataca un solo turno/zona; usar 2.080 h/FTE-año en los cuatro países en vez de un `A` de país documentado.

---

## 4. Qué significa el horizonte de 12 meses para V3 (rotación sin reemplazo)

El horizonte de 12 meses impone **dos restricciones simultáneas y una condición de timing**. Solo la primera es la que la gente ve.

### 4.1 Restricción de flujo — cota superior dura

No se puede achicar más que la gente que se va. En 12 meses:
$$N_{ATT}^{max} \le \tau \cdot N_{base}$$

Con `τ = 40%` y `N_base = 100`, se van 40 personas; achicar por atrición está acotado a 40 cabezas en 12 meses, no más. La lectura mensual (~3,3%/mes) es correcta como ritmo pero engañosa como planificación: es un flujo que llega repartido, no una palanca que se acciona.

### 4.2 Restricción de cobertura — el factor `Ω`, y es la que realmente muerde

Un CD no corre con FTEs fraccionarios. Corre con **turnos, con dotación mínima por turno y con licencias**. La baja que ocurre tiene que ser *la baja correcta, en el turno correcto, en el rol correcto*, o hay que reemplazarla igual.

`Ω` es la fracción de las bajas que efectivamente se puede dejar sin cubrir. Drivers a documentar sitio por sitio:

| Driver | Efecto sobre `Ω` |
|---|---|
| Número de turnos y dotación mínima viable por turno | ↓ fuerte. Con turno de 12 personas mínimo, la baja 13 se puede no cubrir; la 12 no. Cuanto más chico el turno, más lumpy y menor `Ω` |
| Roles licenciados (montacargas, reach truck, HACCP, hazmat, cámara de frío) | ↓ fuerte. Casi siempre hay que reemplazar |
| Concentración de la rotación en el rol que el proyecto liberó | ↑ fuerte. Suele ser favorable: la rotación es máxima justo en picking/packing de baja calificación, que es donde los proyectos liberan horas |
| Colchón de ausentismo | ↓ si no se reduce en proporción. El CD sobredota para absorber ausencias; si baja el requerimiento y el colchón no baja, el ahorro se evapora |
| Convenio / EA: garantías de horas mínimas, reglas de roster, seniority en la reasignación | ↓ |
| Alineación geográfica y de turno entre las bajas y las horas liberadas | ↓ si el proyecto libera turno noche y la rotación está en turno día |

Regla operativa: **`Ω` se estima observando 6–12 meses de bajas reales del sitio y clasificando cada una como "se pudo no cubrir" / "hubo que cubrir"**, no con un supuesto. Si no hay datos, reportar `Ω` como rango y hacer sensibilidad, no como punto.

Combinando ambas restricciones:
$$a_{ATT} = \min\!\left(1,\;\frac{\Omega\,\tau\,N_{base}}{h_{PERM}/A}\right)$$

### 4.3 Timing — el año 1 cobra la mitad

Las bajas llegan repartidas. Si se necesitan `n` cabezas y el flujo utilizable es `Ω·τ·N_base/12` por mes, la `n`-ésima baja aprovechable aparece en el mes:
$$m_n \approx \frac{n}{\Omega\,\tau\,N_{base}/12}$$

Caja del año 1 = `Σᵢ (12 − mᵢ)/12 × C_anual`. Si se consume exactamente toda la capacidad del año con llegada uniforme, **la caja del año 1 es ≈50% del run-rate del mes 12**. Si se consume la mitad de la capacidad, se llega antes y la caja del año 1 sube a ~75%.

$$\theta_{ATT} \approx 1 - \frac{a_{ATT}}{2}\quad\text{(llegada uniforme; }\theta=1\text{ para run-rate)}$$

### 4.4 Cuatro consecuencias que hay que escribir en el informe

1. **V3 rara vez es la restricción para un proyecto individual; es la restricción para la cartera.** Con `H` de 1.000 h (≈0,5 FTE) y un CD de 200 permanentes con `τ=35%`, la capacidad de atrición es enorme comparada con el requerimiento. El problema aparece cuando 10 proyectos comparten esos 70 leavers al año (R4).
2. **Con crecimiento de volumen, V3 deja de ser ahorro y pasa a ser evitación** (R6). Alta rotación en un CD que crece no baja la nómina; baja la contratación. Hay que decidir explícitamente si el estudio banca cost avoidance, y decirlo.
3. **`τ` alto no implica flexibilidad alta si `Ω` es bajo.** Un CD con 60% de rotación pero turnos chicos y roles licenciados puede tener menos capacidad efectiva de achicar que uno con 30% de rotación y turnos grandes de picking manual. **La rotación por sí sola no es un proxy de flexibilidad** — es la mitad de la historia, y probablemente la mitad menos interesante.
4. **La frontera V3/V4 se define por el mes de quiebre.** Lo que no absorbe la atrición pasa a V4, y ahí el criterio no es "¿se puede despedir?" sino **`m < 12 − S`**. Cuanto más grande `S`, más chica es la ventana del año en la que un despido produce caja en 12 meses — hasta desaparecer cuando `S ≥ 12`, punto en el cual **V4 aporta 0 al horizonte de 12 meses aunque sea perfectamente legal**. Ese es el resultado que hay que buscar país por país.

---

## Anexo — Endpoints verificados (funcionan / no funcionan al 2026-08-01)

| Fuente | Estado | Nota |
|---|---|---|
| `api.bls.gov/publicAPI/v2/timeseries/data/{SERIES}` | ✅ funciona sin key | JOLTS, CES y OEWS. Máx. ~3 años por request sin key |
| `www.bls.gov` (HTML) | ❌ 403 a fetchers | Usar la API |
| `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}` | ✅ JSON-stat | `lfsa_etgan2`, `lfsa_eegan2` |
| `sdmx.oecd.org/public/rest/data/OECD.ELS.JAI,DSD_EPL@DF_EPL,1.0/all?format=csvfilewithlabels` | ✅ CSV | EPL completo 2019–2025 |
| `www.oecd.org` (HTML) | ❌ 403 en algunas páginas | La página OCDE-BID LAC sí responde 200 |
| `www.abs.gov.au` | ✅ | Páginas de release; data cubes en xlsx |
| `www.ons.gov.uk` | ✅ | Enlaces de archivo bajo `/file?uri=...` |
| `wecglobal.org` PDF | ⚠️ descarga pero no pude extraer texto | Ningún valor del WEC reportado en este documento |

**Cifras que NO reporté por no poder verificarlas:** penetración de agencia global del WEC · % de casuals sobre empleados en Transport/postal/warehousing de Australia (solo el nivel: 125.600) · cualquier valor de rotación de WERC DC Measures (de pago) · el "43% de rotación en warehousing" de blogs (sin fuente primaria rastreable — **rechazar si reaparece**).