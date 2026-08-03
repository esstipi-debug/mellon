# Política de datos del proyecto

> Página del kickoff. Se firma **antes de la primera grabación**, no después.
> Cierra los huecos H13 (jurisdicción) y H15 (propiedad, salida y uso punitivo)
> en la única forma en que se pueden cerrar: escritos y anunciados.
>
> **Esto no es el contrato.** Es lo que el sistema hace y lo que el equipo se
> obliga a hacer. Media jornada con legal del cliente lo convierte en cláusula.

---

## 1. Qué se guarda, y en qué canal

El registro tiene **dos canales con reglas distintas**, y la distinción es el
diseño entero del sistema:

| canal | qué es | cuánto vive |
|---|---|---|
| **DECIDIDA** | lo que se decidió: enunciado, dueño, criterio, por qué | todo el proyecto, y se **entrega al cierre** |
| **HABLADA** | el transcripto de la conversación | `retention_days` declarado por sesión, y se **destruye** |

La cita textual que justifica una decisión se **copia** al canal DECIDIDA, no se
enlaza. Por eso el registro entregado sigue siendo legible después de que el
canal HABLADA ya no existe.

## 2. Base de licitud

**No es "consentimiento" a secas.** El consentimiento de un trabajador a ser
grabado por el consultor de su empleador **no es libre**, y por lo tanto es una
base de licitud débil. La base declarada por defecto es **interés legítimo, con
información previa y posibilidad real de no ser grabado sin quedar excluido de
la reunión**.

`Consent.basis` es un campo obligatorio del sistema, no una casilla: una reunión
sin él no se registra. Y hay clases de sesión que **nunca se graban** —el
uno-a-uno, por contenido sensible sobre terceros que no consintieron— y eso lo
impone el código, no la buena voluntad.

## 3. Jurisdicción y fechas

- **Ley 19.628**, vigente hoy.
- **Ley 21.719** (protección de datos, Chile): rige desde el **1-dic-2026**.
  Obliga a base de licitud, derechos de acceso/rectificación/supresión/
  portabilidad, notificación de brechas y sanciones. La política de retención ya
  tiene ejecutor (`fdekit decide tick`), que destruye de verdad y deja lápida.
- **Medidas de control laboral:** la doctrina de la Dirección del Trabajo exige
  que sean generales, impersonales, idóneas y estén en el RIOHS. Ver el punto 6.

**Verificar con legal del cliente antes de la primera grabación.** Si hay
sindicato, probablemente requiere consulta.

## 4. Terceros mencionados

El mayor riesgo del sistema y el que menos se ve: *"el problema es que Fulano no
da abasto en el turno noche"*. Fulano no estuvo, no consintió, y quedaría un dato
personal suyo —negativo, atribuible, fechado y firmado— en un registro que
sobrevive al proyecto.

**Regla: una decisión o un compromiso no puede nombrar a una persona que no sea
su dueño.** El dueño es la única persona nombrable, porque su nombre es
constitutivo de la obligación. "Reasignar la ruta de Fulano" se registra como
"reasignar la ruta del turno noche".

Todo lo que sale del equipo —la página HTML del cliente, la tarjeta de piso, la
entrega de cierre— redacta contra el **directorio completo de la cuenta**, no
contra el roster de la sesión: el tercero mencionado suele ser justo el que no
estuvo.

## 5. Los datos no salen de la máquina

El paso de extracción es la ruta de salida que ningún diseño de este tipo
declara. Acá **el clasificador es 100% léxico y determinista**: reconoce formas
verbales ("queda decidido", "se compromete a") y no consulta ningún modelo
remoto.

Eso dejó de ser una promesa: `tests/test_decide_cierre.py` falla si cualquier
módulo de `fdekit.decide` importa una librería capaz de abrir una conexión. La
transcripción, cuando se usa, corre local.

## 6. Uso punitivo — la norma que sostiene todo lo demás

**El registro no se usa para evaluación individual de desempeño.**

No es una cortesía. El día que el registro de compromisos se usa en una
evaluación o para culpar al cliente, la gente deja de declarar decisiones y el
sistema muere en dos semanas — **sin ninguna señal técnica**. Los números siguen
saliendo; lo que se apaga es la declaración, que es lo único que el sistema no
puede producir solo.

En consecuencia:

- Los compromisos vencidos **se leen agrupados por decisión, no por persona**,
  en cualquier presentación fuera del equipo. Un compromiso vencido casi siempre
  dice algo de la decisión que lo generó —que estaba mal dimensionada, que
  dependía de algo que no llegó— y muy poco de quien lo tomó.
- La página HTML del cliente y la entrega de cierre están construidas así, y
  **llevan esta norma escrita adentro**. Una norma que vive en un anexo aparte no
  la lee nadie.
- No hay ni va a haber un tablero de cumplimiento por persona.

**Renegociar es siempre más barato que incumplir en silencio**, y el sistema lo
hace literalmente más barato: `fdekit decide slip` es una línea desde el
teléfono. Correr una fecha con motivo escrito es el comportamiento deseado, no
una falta.

## 7. Descubribilidad

Un reparo registrado con autor y fecha ("X advirtió que esto iba a fallar") es
excelente para la verdad y **potencialmente tóxico en una disputa contractual**.

Hay que decidirlo con el cliente **conscientemente y en el kickoff**, no
descubrirlo el día que aparece un abogado. Las dos opciones son defendibles; la
que no es defendible es no haberlo hablado.

## 8. Qué pasa al cierre

Ejecutado por `fdekit decide handover --out <carpeta> --por <quien> --apply`:

1. El canal **DECIDIDA se entrega al cliente** en HTML y markdown. Dos formatos,
   no uno: el HTML es para leerlo, el markdown es para que el cliente lo meta en
   su propio sistema sin depender de nosotros.
2. El canal **HABLADA se destruye**, y queda `constancia-destruccion.json` con
   fecha, firma, y el `sha256` de cada sesión destruida — prueba de *qué* se
   destruyó sin conservarlo.
3. **El FDE conserva a lo sumo conteos y su propio léxico.** Ningún enunciado,
   ningún nombre, ningún scope, ningún alias, ningún identificador del registro.
   Volúmenes, tarifas, proveedores y el vocabulario interno del cliente son
   suyos y están cubiertos por el NDA.

El orden no es negociable y está impuesto por el código: **se escribe la
entrega, se verifica que quedó escrita, y recién ahí se destruye.** Al revés,
un fallo al escribir deja al cliente sin registro y sin habla, y de eso no se
vuelve. La operación además se niega a correr si queda cola de borradores sin
revisar.

## 9. Qué prueba el hash, y qué no

Cada cita congelada guarda el `sha256` del transcripto del que salió. Sirve para
detectar **mutación mientras la fuente vive**: si alguien reprocesa el audio, la
cita queda marcada como no verificable.

**No sirve para reauditar después del vencimiento.** Cuando la retención destruye
el transcripto, queda un hash que no verifica contra nada — y un hash presente se
lee como si verificara algo. El sistema devuelve explícitamente *"la fuente ya no
existe (retención): la cita sobrevive, el audio no"* en vez de callarlo.

**Decisión del kickoff:** si el proyecto necesita reauditabilidad después del
vencimiento, la única forma es conservar **el segmento citado** —no el
transcripto entero— fuera del TTL. Retrofitearlo es imposible: para cuando se
nota el problema, la fuente ya no está.

## 10. Idioma

El registro se escribe en español, el reporte a la matriz suele ser en inglés, y
en la sala se habla mezclado — *"hay que hacer el cutover el viernes"*. Tres
consecuencias:

- El léxico y los slots son **bilingües por término**: "reslotear" y "slotting"
  producen el mismo valor canónico. Si produjeran valores distintos, dos
  menciones del mismo proceso no se reconocerían como la misma cosa.
- El vocabulario técnico en inglés va en el prompt inicial de la transcripción.
  Whisper con `language="es"` degrada notoriamente en frases mixtas y ésta es la
  contramedida que el modelo ya soporta.
- La traducción de un enunciado se carga **una vez, al promover**
  (`Decision.enunciado_en`). No se traduce automáticamente: una traducción
  automática de un enunciado de decisión cambia justo el matiz que lo hace útil.
  Sin traducción se muestra el original y se dice.

## 11. Ningún número entra al criterio desde el ASR

*"El corte es 500"* transcrito como *"5000"* es un error silencioso, de alto
costo, y cae justo en el único campo donde el diseño exige que haya un número.

**Regla: el número del criterio se tipea o se lee de vuelta en voz alta al
ratificar.** El sistema avisa cuando el criterio trae un número que no aparece en
la cita congelada — avisa, no bloquea: la cita viene del canal HABLADA, que es de
peor calidad por construcción, y bloquear le daría autoridad al canal equivocado.

## 12. Accesibilidad

El canal HABLADA se ofrece como **accesibilidad**, no como vigilancia: el
transcripto queda disponible para todos los participantes. Para quien tiene
discapacidad auditiva, para el participante remoto con mal audio y para el
no-hispanohablante del equipo global, es la diferencia entre participar y
asistir.

No cuesta nada técnicamente y cambia la política de la conversación de
consentimiento. Es probablemente el argumento más fuerte que tiene el proyecto
para que le dejen grabar.

Pero sólo cuenta si se puede **ejercer**, y por eso son dos cosas del sistema y
no una frase del kickoff:

- `fdekit decide transcript --meeting <id>` entrega el transcripto legible a
  quien estuvo, con su fecha de destrucción escrita arriba. Si la sesión no
  autorizó grabar, no hay nada que entregar y lo dice: la accesibilidad no es
  una puerta trasera al consentimiento.
- La página del cliente **nunca señala nada sólo con color**. Riesgo y
  vencimiento llevan su etiqueta en texto, declara su idioma para el lector de
  pantalla, no salta niveles de encabezado y respeta el esquema de color del
  sistema. La mitad de las veces esa página se imprime en blanco y negro, y
  alrededor del 8% de los hombres no distingue rojo de verde: para los dos
  casos, un borde de color es exactamente cero información.
