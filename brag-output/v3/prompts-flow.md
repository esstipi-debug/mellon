# Pack de prompts para Google Flow (Nano Banana = imágenes, Veo = clips)

Sirve para cualquier camino: generarlos a mano en Flow con tu cuenta, o con una herramienta local. Cada prompt corresponde a una escena del guion v3.3.

## Guía de estilo (pegar al inicio de cada prompt)
`Cinematic documentary photography, 16:9, natural light, cool blue-gray ambient with small warm amber accents, shallow depth of field, realistic, unbranded, no readable text, no logos, no watermarks.`

**Reglas de consistencia**
- **Segunda persona = plano subjetivo (POV) o manos y espalda.** Así no hace falta un personaje con rostro ni género, y los clips encajan entre sí.
- Sin marcas, sin logotipos, sin texto legible en pantallas o cajas (se superpone después con gráficos reales del kit).
- Equipo de operarios diverso, retratado con dignidad (nada de caricaturas de "obrero").
- Audio desactivado: la narración se añade en el montaje.

## Clips de video (Veo, 16:9, 6–8 s)
| Id | Escena | Prompt |
|---|---|---|
| C1 | 1 · Niebla | `POV walking slowly into a vast distribution center at dawn, low haze drifting between tall shelving rows that recede into the distance, forklifts parked, cold blue light with a faint warm glow far ahead, steady forward camera movement.` |
| C2 | 3 · Terreno | `POV sitting down on an upturned crate beside an order picker at shift change in a warehouse aisle, the picker's gloved hands holding a handheld scanner and a pallet jack handle, close shallow focus, calm, handheld camera feel.` |
| C3 | 8 · Salida | `POV leaving a warehouse floor toward large open dock doors with morning light, behind the camera a team of workers continues their shift smoothly without looking back, a hand places a thin folder on a table at the exit, warm light, slow push toward the doors.` |

## Imágenes (Nano Banana, 16:9)
| Id | Escena | Prompt |
|---|---|---|
| I1 | 2 · Consultor | `A tall stack of printed presentation slides on a polished boardroom table, empty leather chairs, untouched, late afternoon light through glass walls, no text legible.` |
| I2 | 2 · Analista | `A large monitor in an empty open office showing a glowing abstract chart, dark room, nobody around, a coffee cup long cold beside the keyboard, no text legible.` |
| I3 | 3 · Antropología | `A hand holding a notebook with a hand-drawn floor map and sticky notes, standing at the end of a warehouse aisle, shelving blurred behind, POV, no text legible.` |
| I4 | 4 · Duda | `Close-up of hands measuring a cardboard carton with a tape measure next to a shelf, a handheld scanner on the shelf edge, warehouse background out of focus, no text legible.` |
| I5 | 6 · Psicología | `Warehouse workers in a candid huddle at shift start, diverse, high-visibility vests, relaxed and attentive, warm lamp light, documentary framing, respectful.` |
| I6a/b/c | 6 · Tres lenguas | Tres imágenes con el mismo estilo: `a glass boardroom with a few executives around a table`, `an engineering desk area with two developers at dual monitors, screens abstract`, `a warehouse floor aisle with a worker and a pallet jack`. |
| I7 | 7 · Piloto | `Top-down view of a warehouse floor with two zones separated by yellow floor tape, one zone with a few workers and a lit tablet stand, the other quiet, geometric, no text legible.` |
| I8 | 8 · Historia | `Black-and-white archival-style illustration of a small crew of coal miners working together at a low seam, headlamps, shared effort, 1950s documentary look.` (rotular "illustration") |

## Cantidad y costo
3 clips + 10 imágenes. En Flow, las imágenes son gratis en cuentas normales y los clips gastan créditos (según el README de las herramientas que lo conectan: 50 créditos diarios gratis por cuenta Google; un plan Google AI de pago suma más y habilita 1080p). **Verifica los números en tu cuenta antes de generar**: son lo que dice un README de terceros, no lo comprobé.

## Siguiente paso
Subes las imágenes y clips al repo en `brag-output/v3/media/` (o a Drive) con los ids de arriba (`C1.mp4`, `I3.png`…) y yo hago el montaje: narración, subtítulos, estante de libros, gráficos reales del kit, música y mezcla, con el mismo pipeline del video largo.
