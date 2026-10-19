# Manifiesto del Polímata: guion v2 (borrador para aprobar antes de gastar créditos)

**Formato:** 16:9, ~2:00, narración en inglés + subtítulos, para LinkedIn/X (hook en los primeros 3 s).
**Idea central:** no recitar los 12 principios. Seguir a *una* persona entrando a la niebla y saliendo con un mapa. Los principios aparecen como momentos de la historia (etiqueta pequeña "04 · Think in systems" en pantalla), así que los 12 quedan cubiertos sin convertirse en lista.
**Aviso:** la escena del centro de distribución es una situación ilustrativa. Va rotulada como tal; no se presentan cifras ni clientes inventados. Las únicas cifras son las del manifiesto (758 consultores, +40 %, 84 % vs 60–70 %, ~2×, 1951).

## Tensión (lo que el v1 no tenía)
Las máquinas ganan donde hay reglas claras. Entonces, ¿qué queda para las personas? El video responde mostrando el trabajo concreto que queda, no definiéndolo.

## Arco y locución

| # | Tiempo | Locución (EN) | Principios | Visual | Tipo |
|---|---|---|---|---|---|
| 1 | 0:00–0:08 | "Machines are about to win every game that has clear rules. So what is left for us?" | Preámbulo | Tablero de ajedrez que se desvanece en niebla; una figura entra caminando | **Video generado** (hook) |
| 2 | 0:08–0:22 | "The problems that matter have no rulebook. A company that must adopt a technology its people resist. A region deciding what to do with its land and its energy. The problem changes while you solve it." | Preámbulo, I | Dos escenas rápidas (sala de operaciones con gente cruzada de brazos; paisaje de campo con torres) y la niebla que lo cubre todo | Imagen + movimiento |
| 3 | 0:22–0:34 | "That is the work of the polymath: someone with deep roots in one or two fields, and branches into many. Not a dabbler. Depth gives judgment." | II, III | El diagrama del árbol (ya existe) pero con textura cálida; transición a manos tocando un mapa | Diagrama (reutilizar) |
| 4 | 0:34–0:50 | "So we go where the work happens. We sit next to the person doing it. We watch the floor, not the report. The real problem is never only in the report." | IX | Pasillo de bodega, alguien sentándose junto a un operario; manos, cajas, tablet | **Video generado** |
| 5 | 0:50–1:04 | "The board speaks value and risk. The engineer, feasibility. The operator, daily reality. We translate between all three, and we make the case." | VIII, VII | Tres mundos (sala de directorio, laboratorio, piso) conectados por una línea ámbar | Imagen + diagrama |
| 6 | 1:04–1:18 | "We use AI as a lever. In a test with 758 consultants it made some tasks 40 percent better. On a task outside its frontier, accuracy fell from 84 to 60 or 70. So we verify, and we never hand over judgment." | V, VI | Gráfico del experimento (ya existe), con la figura eligiendo una conexión entre mil | Diagrama (reutilizar) |
| 7 | 1:18–1:32 | "Then we build. Small prototypes, tested with real users, in days, not months. An idea never tested is no different from a hallucination." | X, XII | Prototipo en una pantalla; usuarios reales probándolo; hojas anotadas | **Video generado** |
| 8 | 1:32–1:46 | "And the measure of the work is what happens after we leave. If people don't use it, the failure is ours. We train, we document, we hand over." | XI, VII | Ella sale de la sala; el equipo sigue sin ella; la curva de uso sigue subiendo | Video generado + diagrama |
| 9 | 1:46–2:00 | "Where the rules are clear, let the machine win. Where there are none, we are there. And when we leave, the map stays." | Cierre | Mapa completo con la ruta ámbar; título "The Polymath Manifesto"; llamada a leerlo | Diagrama + título |

~330 palabras. A la velocidad de la voz actual caben en ~2:00 con pausas.

## Qué mejora respecto al v1
1. **Hay una persona y una situación**, no solo conceptos.
2. **Hay imagen de verdad** en los momentos humanos (4, 7, 8) y diagramas solo donde un diagrama explica mejor (3, 6, 9).
3. Las cifras del manifiesto se cuentan **una sola vez**, en su sitio.
4. El hook es una pregunta que el espectador se hace, no un lema.

## Plan de generación y costo (precios de OpenArt a configuración por defecto; verificar con `openart_model_cost` antes de cada tanda)

Necesito **~6 clips de video (6–8 s)** y **~12 imágenes**:

| Opción | Modelo | Créditos aprox. | Notas |
|---|---|---|---|
| Económica | Imágenes Seedream 5 Lite / Wan 2.7 Image (15 c) + clips PixVerse V6 (50 c) | ~12×15 + 6×50 = **~480** | Clips menos realistas; funciona con encuadres sobrios |
| Equilibrada | Imágenes Wan 2.7 Image (15 c) + clips Wan 3.0 (100 c) o MiniMax H3 Max Turbo (75 c) | **~780–1.080** | Mejor movimiento; Wan 3.0 permite clips largos |
| Alta calidad | Clips Veo 3.1 / Seedance 2.0 (120–400 c) | **1.000–2.600** | Solo si el resultado va a pantalla grande |

Tu plan Free tiene 10 créditos, así que no alcanza para ninguna opción. Los créditos que incluye cada suscripción los ves en https://openart.ai/pricing. No sé cuántos trae cada plan hoy.

**Higgsfield u otras:** no tengo conexión con ellas desde aquí. Se pueden usar igual (tú generas con mis prompts y yo monto), pero en OpenArt yo genero directamente, repito tomas y controlo el costo.

## Antes de generar, necesito que decidas
1. ¿El guion funciona o cambiamos el arco? (Escenas 2 y 4 son las que más pueden cambiar.)
2. ¿Quién firma el video (Mytra FDE, tú, el autor del manifiesto)? Define el cierre y qué llamada a la acción lleva.
3. ¿Opción económica, equilibrada o alta?
