# HUECOS DE COMPLETITUD — lista priorizada

Criterio de orden: primero lo que invalida el diseño o lo hace no falsable; después lo que lo mata en la semana 6; después lo que lo mata en el mes 6. Cada hueco es algo que **ninguno de los cuatro enfoques ni los tres juicios cubre**, no una preferencia entre ellos.

---

## TIER 0 — Sin esto, el proyecto no es evaluable ni defendible

### H1. No hay línea base ni contrafactual. El proyecto es infalsable.
**Qué falta:** los cuatro enfoques miden cosas *del sistema* (drafts en cola, tasa de resolución, minutos circulares, TTD) y ninguno mide la **variable dependiente**: horas-persona de reunión por semana en el scope. Sin una medición previa, cualquier resultado es narrable como éxito. Es una violación directa de la doctrina del propio kit ("lo que no está cuantificado no entra al análisis").
**Cómo cerrarlo:**
- Dos semanas **antes** de escribir código: exportar el calendario del scope (Graph API o CSV de Outlook) y calcular `horas_persona_semana = Σ(duración × asistentes)` por serie. Son ~30 líneas y datos que ya existen.
- Tres números más, del mismo export: nº de reuniones/semana, nº de series recurrentes, y `%` de reuniones sin agenda escrita en el invite.
- Encuesta de 3 preguntas al inicio y cada mes (ver H2), n≈8, 60 segundos.
- Elegir **una serie de control** que no adopte el sistema durante 8 semanas. Sin grupo de control, el efecto es indistinguible del efecto Hawthorne — que en este tipo de intervención es grande y real.
- **Criterio de muerte declarado antes de empezar:** si a la semana 10 las horas-persona del scope tratado no bajaron ≥15% respecto del control, se apaga.
**Costo:** 1 día-persona, cero código de producto.

### H2. Todas las métricas propuestas miden ESCRITURA. Ninguna mide LECTURA.
**Qué falta:** los cuatro sistemas se juzgan por cuánto capturan. El registro que nadie consulta es un pasivo, no un activo — y es el modo de falla estadísticamente dominante de los sistemas de gestión de conocimiento. Ni las 8 métricas del enfoque 2, ni la métrica de salud del enfoque 1, ni los tripwires del enfoque 3 tocan el consumo.
**Cómo cerrarlo:**
- Log de consultas append-only (`queries.jsonl`: timestamp, operación, actor, símbolo, si hubo resultado). 15 líneas dentro del CLI.
- Tres métricas semanales, en la misma hoja donde vive todo lo demás:
  - **Lectores únicos/semana** (objetivo: > nº de FDEs; si el único que consulta es quien escribe, el sistema es una libreta personal cara).
  - **Consultas fuera de la sala / consultas totales** (si es ≈0, el registro solo sirve de ceremonia).
  - **Tasa de consulta fallida**: `find`/`why` que devolvieron vacío o AMBIGUOUS. Es la señal temprana de que la cobertura es peor de lo que la gente cree, y hoy nadie la tiene.
- Métrica de resultado, no de proceso: **nº de re-discusiones cortadas** — contador manual de una tecla cuando alguien corre `why()` en la sala y el tema se cierra. Es la única evidencia directa del mecanismo que los cuatro enfoques prometen.
**Costo:** 0.5 días.

### H3. Nadie mide RECALL del registro. `referencing()` miente con cara de autoridad.
**Qué falta:** el juicio 3 detecta el problema (falsa completitud) pero ningún enfoque propone cómo medirlo. Precisión se puede estimar mirando lo registrado; recall requiere saber lo que **no** se registró, y eso no está en ninguna propuesta.
**Cómo cerrarlo:**
- **Auditoría ciega semanal, 10 minutos:** a los 3 días de una reunión, pedir a 2 participantes distintos por separado que escriban de memoria "las 3 cosas que se decidieron". Contrastar contra el registro. `recall ≈ decisiones nombradas que están en el registro / decisiones nombradas`. Con 6 reuniones ya hay señal.
- Publicar **cobertura estimada junto a toda salida de `referencing()`**: "14 referencias (cobertura estimada 70% ± 15, n=6 auditorías)". Una salida sin barra de error hereda la promesa de completitud del LSP sin heredar la garantía.
- Contador de **falsos positivos que llegaron a producción** (decisiones registradas que un participante desconoce). Se publica al lado de la cobertura, siempre las dos juntas, por la misma razón que TTD va con tasa de reapertura.
**Costo:** 10 min/semana de humano, 0 de código.

---

## TIER 1 — Matan la adopción antes de la semana 8

### H4. Arranque en frío. El día 1 el registro está vacío y compite contra 3 años de historial.
**Qué falta:** los cuatro enfoques arrancan con el store vacío: tabla de alias vacía (enfoque 1: L0+L1 no cubren nada hasta la sesión 5-8), sin premisas, sin decisiones vigentes que citar. Justo en las 4 semanas donde se juega la adopción, `why()` y `referencing()` devuelven vacío y el sistema se ve inútil. Además, el problema real del FDE en la semana 1 no es capturar lo nuevo: es que **ya hay 20 decisiones vigentes** tomadas antes de que el sistema existiera, y son las que se van a re-discutir.
**Cómo cerrarlo:**
- **Sesión de siembra de 90 minutos en el kickoff**, con el sponsor y el líder operativo: declarar las 15-30 decisiones vigentes que gobiernan hoy, con dueño, fecha aproximada, criterio y —crítico— **supuesto del que colgaban**. Van con `status=VIGENTE`, `origen=SIEMBRA`, `evidencia=null`, marcadas como no auditables.
- Salida secundaria de la misma sesión, y probablemente la más valiosa: la **lista de alias iniciales** ("lo del slotting", "el tema del EDI", "la regla de Fabián") y el **glosario de jerga** de la cuenta. Precarga la tabla de alias y la memoria de serie el día 1 en vez de la sesión 8.
- Ingesta de bajo esfuerzo del historial: los últimos 6 meses de actas existentes pasadas por el mismo `draft_decisions()` con `only_ready=False` — todo va a cola, se revisa una vez, se descarta el 80%. Aunque rescate 10 decisiones, es la diferencia entre un `why()` que responde y uno que no.
**Costo:** 90 min de cliente + 1 día de FDE por cuenta. Es el mejor retorno del proyecto entero y ningún enfoque lo tiene.

### H5. El canal asíncrono no existe en ningún diseño, y es donde se toma la mayoría de las decisiones operativas.
**Qué falta:** el enfoque 3 lo nombra y lo declara pérdida estructural; los otros tres lo ignoran. En operaciones de supply chain, el grupo de WhatsApp del CD, el hilo de Teams y el correo de las 22:00 concentran probablemente más decisiones que las reuniones. Peor caso, no cubierto por nadie: **la decisión del pasillo contradice la registrada en la sala**, y el registro queda confiadamente equivocado — que es estrictamente peor que estar vacío.
**Cómo cerrarlo:**
- `fdekit decide add` de una línea (enfoque 3) es el piso, no la solución.
- **Ingesta de export de chat**: WhatsApp exporta `.txt` con `[fecha, hora] Autor: mensaje`; Teams exporta vía Graph. Parser de ~60 líneas → mismo `draft_decisions()`, mismo léxico, misma cola de revisión. El texto de chat es **mejor input que el habla**: sin ASR, sin diarización, con autor resuelto y timestamp exacto. Es el canal más barato de todos y nadie lo consideró.
- **Regla de precedencia explícita, escrita en el registro:** la evidencia más reciente gana, pero una decisión tomada fuera de la sala que contradice una `VIGENTE` no la supersede automáticamente — genera un **`CONFLICTO`** que bloquea y entra como primer punto de la agenda siguiente. Sin esta regla, el canal asíncrono corrompe el canal decidido en vez de alimentarlo.
- **Decisión por inacción**: la más frecuente en operaciones y la más invisible. Cerrarla con un tipo `NO_DECISION` que se escribe cuando un punto de agenda se aplaza por segunda vez: "no se decidió; el status quo continúa; costo de seguir sin decidir = X". Es lo que convierte el silencio en un objeto.

### H6. Silencio indistinguible de salud: una reunión sin capturas se ve igual que una reunión sana.
**Qué falta:** en los cuatro enfoques, cero decisiones registradas puede significar (a) no hubo nada que decidir, (b) el facilitador no dijo la frase, (c) Whisper falló, (d) el audio era inutilizable, (e) nadie revisó la cola. Los cinco casos producen el mismo output: nada. La falla es **silenciosa**, que es la peor propiedad posible en un sistema del que después se van a leer conclusiones.
**Cómo cerrarlo:**
- Toda sesión **escribe siempre un registro**, aunque no capture nada: `sesion_id, duración, asistentes, estado_captura ∈ {CAPTURADA, SIN_AUDIO, ASR_DEGRADADO, SIN_RITUAL, COLA_NO_REVISADA}, n_decisiones, n_candidatos, mediana_confianza_asr`.
- **Compuerta de calidad de ASR**: si la mediana de `confianza_asr` de los segmentos < umbral (calibrar en las primeras 6 reuniones), el sistema **se niega a producir drafts** y emite `ASR_DEGRADADO` con la razón. Producir un recall del 20% sin avisar es cómo el registro empieza a mentir.
- En la hoja semanal, una línea que hoy no existe en ninguna propuesta: **"3 de 7 sesiones sin captura, motivos: 2 SIN_RITUAL, 1 ASR_DEGRADADO"**. Eso es lo que permite arreglar el proceso; un tablero de métricas sobre las 4 que sí capturaron es una muestra sesgada.

### H7. Modalidades de reunión no consideradas: el diseño solo sirve para la recurrente de comité.
**Qué falta:** los cuatro asumen reunión recurrente, con agenda, con facilitador, con roster de invite, en sala, en español, de 60 min. Cinco modalidades reales quedan fuera y cada una rompe una premisa distinta:

| Modalidad | Qué premisa rompe | Cómo cerrarlo |
|---|---|---|
| **1:1** | Consentimiento (contenido sensible: desempeño, quejas sobre terceros), ritual absurdo con 2 personas, y es donde más decisiones no registradas viven | Perfil `1:1`: **nunca se graba**, solo `decide` manual post-reunión, sin canal HABLADA. Registro DECIDIDA privado por defecto, promoción explícita a scope de serie |
| **Kickoff con cliente** | Densidad máxima de supuestos y definiciones, corpus cero, roster inestable | Es la sesión de siembra de H4. Perfil con léxico volcado a `SUPUESTO` y `CRITERIO`, no a `DECISION` |
| **Terreno / gemba walk** | Sin sala, sin agenda, sin facilitador, ruido, de pie, roster = quien esté | Reusar `fdekit.gemba` tal cual: `meeting_id=null`, `origen=TERRENO`, dueño siempre `missing` → cola. Es el caso para el que el kit ya está calibrado y ningún enfoque lo conectó |
| **Cambio de turno / daily** | 15 min, 0 decisiones, altísimo volumen de compromisos, repetición extrema; el presupuesto de 7 y el gate de agenda lo asfixian | Perfil `HANDOVER`: sin gate, sin ritual, solo captura de `Commitment` con dueño del turno entrante. Es donde más compromisos abiertos viven en un CD |
| **Crisis / incidente** | No hay agenda que gatear, decisiones por minuto, y es donde el "por qué" más importa después | Perfil `INCIDENTE`: gate desactivado, presupuesto suspendido, captura permisiva, **ritual diferido a T+24h**. Sin este perfil, el gate se bypassea de facto y el hábito de bypassear se contagia al resto |

**Regla general que falta:** el perfil de reunión debe ser un campo de primera clase (`Reunion.clase`) que gobierna gate, presupuesto, política de grabación y léxico. El enfoque 4 tiene `clase` en el schema pero no la usa para nada.

### H8. La decisión condicional y el aprobador ausente.
**Qué falta:** ningún enfoque modela el caso más común en una cuenta con cliente: **se decide en la sala pero sujeto a aprobación de alguien que no estuvo** ("dale, pero lo tengo que pasar por compras / lo confirmo con mi jefe / depende de si el gerente firma"). Hoy eso se registra como `VIGENTE` (miente) o no se registra (se pierde). Y el aprobador —que es el actor que decide de verdad— no existe en ningún modelo de datos.
**Cómo cerrarlo:**
- Estado `PROVISORIA` con campos obligatorios `ratifica_por: persona`, `ratifica_antes_de: fecha`, `si_no_ratifica: {CAE | SIGUE_VIGENTE}`.
- Una `PROVISORIA` vencida sin ratificar entra automáticamente a la agenda siguiente y bloquea todo compromiso que la implementa (`estado=BLOQUEADO`, no `ABIERTO` — gente trabajando contra algo no aprobado es desperdicio puro y hoy es invisible).
- El aprobador recibe **un solo mensaje**: enunciado, criterio, qué cuelga, y dos botones. No la minuta, no el grafo.

---

## TIER 2 — Matan el sistema entre el mes 2 y el mes 6

### H9. El actor que no estuvo: onboarding, rotación y compromisos huérfanos.
**Qué falta:** el enfoque 2 mide la ausencia como factor de riesgo; ninguno resuelve la necesidad. Tres actores concretos sin ruta:
- **El que se incorpora en la semana 10** (nuevo FDE, nuevo jefe de proyecto del cliente). Necesita "qué está decidido, en qué orden, qué sigue vivo, qué supuestos sostienen todo". Falta `onboarding_brief(scope)`: cadena de decisiones estratégicas → operativas, supuestos vigentes con edad, compromisos abiertos. Es una consulta sobre datos que ya existen: **medio día de trabajo, y es el único artefacto que un recién llegado va a leer entero**.
- **El que se va.** Rotación de FDE y de contraparte es la norma, no la excepción. Faltan `reassign_owner(persona_sale, persona_entra)` y un **barrido de offboarding** que liste compromisos y decisiones cuyo dueño ya no existe. Sin esto, a los 6 meses una fracción alta del registro apunta a gente que se fue y el registro se vuelve ruido.
- **El ejecutor de piso** (supervisor de turno noche) que debe ejecutar la decisión, no estuvo en ninguna reunión y no lee correo durante el turno. El canal de entrega es un hueco total: el output del sistema es markdown en git y ninguna propuesta define cómo llega a él. Mínimo viable: mensaje de WhatsApp de 3 líneas generado desde el `Commitment`, o una línea impresa en la hoja de trabajo estándar (`fdekit.standardwork` ya está ahí).

### H10. No hay superficie de lectura para el cliente. El registro vive donde el cliente no entra.
**Qué falta:** el enfoque 4 nombra que el cliente no va a hacer commit; nadie resuelve que **tampoco va a leer markdown en git**. El jefe de operaciones del CD —el consumidor más importante del canal DECIDIDA— no tiene acceso al repo, no sabe qué es un diff, y su herramienta es Teams o SharePoint. Un registro que solo el FDE puede leer es una libreta personal.
**Cómo cerrarlo:**
- Render estático HTML de una página por scope (decisiones vigentes, compromisos por dueño, supuestos vencidos), regenerado en cada commit, publicado donde el cliente ya vive (SharePoint del proyecto, canal de Teams, o un PDF adjunto). Cero autenticación nueva, cero herramienta nueva. `graphify` ya exporta HTML; acá se usa como **renderizador**, no como grafo.
- **Idioma:** el registro se escribe en español y el reporte a la matriz suele ser en inglés. Campo `enunciado_en` opcional, traducido una vez al promover. Barato ahora, imposible de retrofitear a las 200 decisiones.

### H11. El compromiso renegociado en privado: el momento exacto en que el registro empieza a mentir.
**Qué falta:** solo el enfoque 4 tiene `renegociado_en`, y ninguno tiene la ruta de auto-servicio. Lo que pasa en la realidad: dueño y solicitante acuerdan por chat una fecha nueva; el registro sigue mostrando `VENCIDO`; a la tercera vez el dueño concluye que el registro está mal, deja de mirarlo, y a partir de ahí el tablero de vencidos es ruido que todos ignoran. **Es la muerte más común de estos sistemas y ningún enfoque la nombra.**
**Cómo cerrarlo:**
- `fdekit decide slip C-112 --nueva-fecha 2026-09-05 --motivo "..."` desde el móvil o por respuesta al digest. Nunca edita la fecha original: crea versión y conserva la anterior visible al lado.
- **Contador de slips por compromiso.** Un `Commitment` con 3 slips no es un atraso: es una decisión que no se tomó, y debe escalar como `NO_DECISION` (ver H5) en vez de seguir corriendo la fecha.
- Regla dura: **renegociar es siempre más barato que incumplir en silencio**, y el sistema tiene que hacerlo literalmente más barato (una línea, desde el teléfono) o la gente elegirá el silencio.

### H12. Fallas técnicas concretas sin ruta definida.
Cinco, todas baratas de cerrar y ninguna cubierta:
- **Code-switching español/inglés.** En supply chain es la norma, no la excepción ("hay que hacer el *cutover* el viernes", "el *slotting* del *picking* de *fast movers*"). Whisper con `language="es"` degrada notoriamente en frases mixtas, y el léxico de decisión y los slots están escritos solo en español. Cerrar con: vocabulario técnico en inglés inyectado en el prompt inicial de Whisper (ya soportado), y `SLOT_LEXICON`/`DECISION_LEXICON` **bilingües por término** desde el día 1 (`("slotting","ubicación","acomodo")` como un solo término). Costo: cero adicional si se hace ahora.
- **Números mal transcritos dentro del criterio de aceptación.** "El corte es 500" → "5000" es un error silencioso, de alto costo, y el criterio es justamente donde el enfoque 4 exige que haya un número. Regla dura: **ningún número entra al criterio desde ASR**; se tipea o se lee de vuelta en voz alta al ratificar. Y validación: si el criterio contiene un número que no aparece verbatim en la cita congelada, va a cola.
- **Colisión de IDs offline / multi-FDE.** Dos personas trabajando offline en la misma cuenta asignan `D-041` las dos; el lock file del enfoque 3 no funciona sin filesystem compartido. Cerrar con ID de autor + monotónico (`D-JM-041`) o ULID. Trivial ahora, doloroso después.
- **Fallo del pipeline** (Whisper crashea, notebook muere, audio corrupto): hoy produce un hueco indistinguible. Cerrar con el registro obligatorio de sesión de H6.
- **El hash que ya no verifica nada.** El enfoque 4 congela `sha256` del transcripto y después lo borra por TTL. Cerrar declarándolo: el hash sirve para detectar *mutación* mientras la fuente vive, no para reauditar después del vencimiento. Si se quiere reauditabilidad post-TTL, hay que conservar el segmento citado —no el transcripto entero— fuera del TTL, y eso hay que decidirlo antes, no después.

---

## TIER 3 — Legal y ético: pasado por alto casi entero

### H13. Nadie nombró la jurisdicción. Chile tiene una ley nueva que entra en vigencia en meses.
**Qué falta:** el enfoque 4 construye TTL, lápidas y cifrado sin nombrar **qué norma** determina la retención, la base de licitud o los derechos del titular. Los otros tres tratan el consentimiento como una casilla. Para un despliegue en Chile (RUT en el hook pre-commit del enfoque 4 lo delata) esto es concreto y con fecha:
- **Ley 19.628** vigente hoy, y **Ley 21.719** (protección de datos, publicada fines de 2024, con vigencia diferida ~24 meses y creación de la Agencia de Protección de Datos): base de licitud obligatoria, derechos de acceso/rectificación/supresión/portabilidad, notificación de brechas, sanciones. **Verificar la fecha exacta de entrada en vigencia con legal antes de diseñar la retención** — si es inminente, la política de retención hay que escribirla ya, no retrofitearla.
- **Asimetría de poder empleador-trabajador:** el "consentimiento" de un operario a ser grabado por el consultor de su empleador no es libre y por lo tanto es una base de licitud débil. La base correcta es probablemente interés legítimo + información previa + posibilidad real de no ser grabado sin quedar excluido de la reunión.
- **Medidas de control laboral:** en Chile, la doctrina de la Dirección del Trabajo exige que sean generales, impersonales, idóneas y estén en el RIOHS. Un tablero de **cumplimiento de compromisos por persona** (enfoque 2, `commit_ledger(person_id)`; enfoque 3, agenda agrupada por dueño) es defendible como gestión de proyecto y cuestionable como control laboral individualizado. Si hay sindicato, probablemente requiere consulta.
**Cómo cerrarlo:** una página de "política de datos del proyecto" firmada en el kickoff, con: base de licitud, finalidad, retención por tipo de dato, quién accede, ruta de ejercicio de derechos, y qué pasa al cierre. Media jornada con legal del cliente, **antes** de la primera grabación. Y `Consentimiento.base_licitud` como campo, no `consent: bool`.

### H14. Terceros mencionados: el agujero de privacidad más grande y el único que nadie vio.
**Qué falta:** los cuatro anonimizan **participantes**. Ninguno cubre al **tercero mencionado**: "el problema es que Fabián no da abasto en el turno noche", "el proveedor nos está cagando con los plazos". Fabián no estuvo, no consintió, y ahora hay un dato personal suyo —negativo, atribuible, fechado y firmado— en un registro versionado que sobrevive al proyecto. Es simultáneamente el mayor riesgo legal y la vía más rápida a que la gente deje de hablar.
**Cómo cerrarlo:**
- `_redact()` debe aplicarse contra el **directorio completo de la cuenta**, no solo contra el roster de la sesión.
- Regla de promoción: **una decisión o compromiso no puede nombrar a una persona que no es su dueño.** "Reasignar la ruta de Fabián" se registra como "reasignar la ruta del turno noche". El dueño es la única persona nombrable, porque su nombre es constitutivo de la obligación.
- Comando en la sala: **`no queda`** — marca la ventana de ±60s como no promovible y la excluye de la cita congelada. Sin una válvula de escape explícita, la gente se autocensura de forma difusa y el canal HABLADA pierde exactamente el desacuerdo que justifica su existencia.

### H15. Propiedad, salida y uso punitivo del registro.
Tres huecos que nadie tocó y que se pagan al final:
- **¿De quién es el registro al cierre del proyecto?** Contiene datos comerciales del cliente (volúmenes, tarifas, proveedores) y probablemente está cubierto por el NDA. Guardarlo en el repo del FDE puede ser incumplimiento. Falta una **cláusula de entrega**: al cierre, el canal DECIDIDA se entrega al cliente en formato legible (HTML + markdown), el HABLADA se destruye con constancia, y el FDE conserva a lo sumo el léxico y los patrones anonimizados. Definirlo en el kickoff, no en la última semana.
- **Descubribilidad.** El enfoque 4 lo nombra pero no saca la consecuencia incómoda: un `reparo` registrado con autor y fecha ("X advirtió que esto iba a fallar") es excelente para la verdad y potencialmente tóxico en una disputa contractual. Hay que decidirlo con el cliente conscientemente, no descubrirlo.
- **Uso punitivo.** El día que el registro de compromisos se usa en una evaluación de desempeño o para culpar al cliente, la gente deja de declarar decisiones y el sistema muere en dos semanas — sin ninguna señal técnica. Falta una **norma escrita y anunciada**: el registro no se usa para evaluación individual, y los compromisos vencidos se leen agrupados por decisión, no por persona, en cualquier presentación fuera del equipo.
- **Egreso de datos, no señalado por nadie:** los enfoques 1, 2 y 3 mencionan "un LLM sobre una ventana de segmentos" para la extracción. Whisper es local; **ese paso probablemente no**. Es una ruta de salida del transcripto del cliente que ninguna propuesta declaró. O el clasificador es 100% léxico y determinista (viable: es lo que hace `classify_waste`), o hay que declarar el egreso y obtener autorización.

### H16. Accesibilidad — la única palanca que convierte la conversación de consentimiento en un beneficio.
**Qué falta:** nadie mencionó al participante con discapacidad auditiva, ni al participante remoto con mal audio, ni al no-hispanohablante nativo del equipo global. El transcripto y el pre-read son, para ellos, la diferencia entre participar y asistir.
**Cómo cerrarlo:** framear el canal HABLADA como accesibilidad desde el kickoff (transcripción disponible para todos los participantes) en vez de como vigilancia. Cambia la política de la conversación de consentimiento sin costo técnico, y es probablemente el argumento más fuerte que tiene el proyecto para que le dejen grabar.

---

## Lo que cambiaría en el plan, en una línea cada uno

1. **Antes de la primera línea de código:** medir horas-persona de reunión del scope (H1), definir grupo de control, y firmar la página de política de datos con jurisdicción chilena (H13).
2. **Primera sesión con cliente:** siembra de 15-30 decisiones vigentes + tabla de alias inicial + glosario (H4). Es el mayor retorno del proyecto y ninguna de las cuatro propuestas lo tiene.
3. **Agregar al MVP, en orden de costo/beneficio:** registro obligatorio de sesión con `estado_captura` (H6, medio día) → log de consultas y lectores únicos (H2, medio día) → `Reunion.clase` con 5 perfiles (H7, 1 día) → ingesta de export de WhatsApp/Teams (H5, 1 día) → estado `PROVISORIA` con aprobador ausente (H8, medio día) → `slip` de compromiso desde el teléfono (H11, medio día) → `onboarding_brief` (H9, medio día) → render HTML para el cliente (H10, medio día).
4. **Reglas duras sin código:** ningún número al criterio desde ASR (H12); ninguna persona nombrada salvo el dueño (H14); el registro no se usa para evaluación individual (H15); comando `no queda` disponible siempre (H14).
5. **Publicar siempre en pares:** cobertura con falsos positivos, TTD con reapertura, capturas con sesiones sin captura. Cualquier número solo es propaganda.