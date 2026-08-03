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

## 9. Accesibilidad

El canal HABLADA se ofrece como **accesibilidad**, no como vigilancia: el
transcripto queda disponible para todos los participantes. Para quien tiene
discapacidad auditiva, para el participante remoto con mal audio y para el
no-hispanohablante del equipo global, es la diferencia entre participar y
asistir.

No cuesta nada técnicamente y cambia la política de la conversación de
consentimiento. Es probablemente el argumento más fuerte que tiene el proyecto
para que le dejen grabar.
