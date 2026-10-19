# Guion v3.2: el estratega con "maletín de libros" (reemplaza a v3 y v3.1)

**Formato:** 16:9, ~2:15, narración en inglés + subtítulos, LinkedIn/X.
**Tesis que demuestra:** la polimatía del siglo XXI no es saber un poco de todo, es **llevar varios oficios a la misma sala y usarlos sobre un solo problema**. Un consultor de diapositivas usa uno (estructurar la presentación); un analista usa otro (medir); el estratega desplegado usa los ocho del repo, y por eso es quien responde por la adopción. El FDE sigue siendo su aliado: pone la solución técnica.
**Recurso visual constante:** una *tarjeta de herramienta* aparece al pie en cada escena ("TOOL · Past specifics · The Mom Test, Fitzpatrick") y un *estante* arriba a la derecha va encendiendo, uno por uno, los 8 libros. Al final están los 8 encendidos: ese es el polímata.
**Caso:** el centro de distribución **sintético** de `fdekit demo` (se rotula: *"Synthetic case. Data generated with fdekit; reproducible."*). Cifras: A3.md / hallazgos.json.
**Atribución:** las ideas se presentan como técnicas de cada libro (título + autor), **parafraseadas, sin citas textuales**. El grafo del repo se declara a sí mismo como síntesis de memoria (sin texto de los libros ingerido), así que antes de publicar hay que contrastar cada nombre de técnica con el libro.

## Locución, herramienta y visual

| # | Tiempo | Locución (EN) | Herramienta (libro) | Principios | Visual / evidencia |
|---|---|---|---|---|---|
| 0 | 0:00–0:09 | "The client's system says every order goes release, pick, consolidate, pack, check, ship. You open the log. Fifty-four percent do. Why do the rest find thirty other ways?" | **Situación-Complicación-Pregunta**, *The Pyramid Principle* (Minto) | Preámbulo | Línea limpia que se rompe; `dfg.mmd` (54,12 %, 31 variantes) |
| 1 | 0:09–0:21 | "That's the fog. So before any analysis, you define the decision: cut the waiting in half, at one site, in twelve weeks. If it matters, it can be observed. If it can be observed, it can be measured." | **Definir la decisión primero / Clarification Chain**, *How to Measure Anything* (Hubbard) | I | Niebla → A3 con "−50 % espera"; el plan de 12 semanas del A3 |
| 2 | 0:21–0:38 | "Three people arrive with the same problem. One writes a fifty-page deck. It's good. Nothing changes. One builds the perfect dashboard. Nobody opens it. The third carries more than one book, and brings an engineer." | Los dos primeros usan *una* herramienta cada uno (Minto, Hubbard); el SD, varias | II, III | Tres carriles en pantalla dividida; en el tercero se encienden libros del estante; entra el ingeniero |
| 3 | 0:38–0:54 | "You don't ask what they would want. You ask for the last time it went wrong. You talk less. A compliment is not data. Then the floor answers: a hundred and fifty-seven meters walked per order." | **Preguntar por especificidades del pasado; desviar cumplidos**, *The Mom Test* (Fitzpatrick) · **Entrevista basada en historias**, *Continuous Discovery Habits* (Torres) | IX | Junto al operario; `spaghetti.png`; 157,2 m por pedido (A3) |
| 4 | 0:54–1:08 | "Then you doubt. A quarter of the products have bad data, give or take five points, checked on the floor, not on the screen. AI drafts the analysis, and someone on your side is paid to argue against it." | **Intervalo de confianza 90 %** (Hubbard) · **Equipo rojo / obligación de disentir**, *Bulletproof Problem Solving* (Conn y McLean) | V, VI | Auditoría física; barra 25,6 % (IC 21,1–30,8); IA propone, la estratega elige |
| 5 | 1:08–1:20 | "You draw the tree, and you prune it. Sixty-one percent of the wait sits in one queue. Undersized at the peak, not slow. You fix the structure, not the people." | **Árbol de hipótesis + 2×2 impacto/influencia** (Conn y McLean) | IV | `heatmap.png`, árbol que se poda hasta una rama; cola resaltada (A3 §2 y §4) |
| 6 | 1:20–1:36 | "The operators hear 'automation' and feel replacement. You name it, without judgment, and wait. You find the picker whose way already works, and shrink the change to one move. The director gets the answer first, on one page." | **Nombrar la resistencia** (*Flawless Consulting*, Block) · **Bright spots y achicar el cambio** (*Switch*, Heath y Heath) · **Respuesta primero** (Minto) | VII, VIII | Operarios; tres lenguas (piso, ingeniería, directorio); hoja de una página |
| 7 | 1:36–1:52 | "You test the riskiest assumption first, in one zone, with a control group agreed in advance. A meeting only counts if someone commits to something. And you ask: can we, should we, who does it affect?" | **Probar la suposición más riesgosa** (Torres) · **Compromiso y avance** (Fitzpatrick) · **Contratación 50/50** (Block) | X | Zona piloto con control; el kit se niega a cotizar gainshare sin contrafactual medido |
| 8 | 1:52–2:08 | "At week twelve you leave a runbook and signed sheets. Trust is credibility, reliability and closeness, divided by how much it's about you. Success is what they do without you." | **Ecuación de confianza**, *The Trusted Advisor* (Maister, Green y Galford) | XI, XII | Sale de la sala; el equipo sigue; `xmr.png`; vuelve la niebla con un mapa nuevo |
| 9 | 2:08–2:20 | "One person. Eight books. Where the rules are clear, let the machine win. Where there are none, you are there. And when you leave, the map stays." | Los 8 libros encendidos | Cierre | Estante completo + mapa con ruta ámbar + título |

~315 palabras. Los 12 principios están cubiertos; los 8 libros aparecen todos (Minto, Hubbard, Fitzpatrick, Torres, Conn y McLean, Block, Heath y Heath, Maister et al.).

## Por qué esto responde a "el SD debe representar la polimatía"
- El contraste ya no es contra una profesión, es **cuántos oficios lleva a la sala**. El consultor y el analista usan uno; el SD encadena ocho sobre el mismo caso.
- Los libros del repo son literalmente el material que el SD debe dominar: descubrimiento (Fitzpatrick, Torres), decisión bajo incertidumbre (Hubbard), estructura (Minto, Conn y McLean), cambio (Heath, Block) y confianza (Maister). El video los muestra funcionando, no solo nombrándolos.
- El FDE no sale mal parado: su aporte (la solución técnica) está en la escena 2 y en la 6 como aliado.

## Cifras (todas del demo; reproducibles con `fdekit demo`)
54,12 % flujo declarado · 31 variantes · 157,2 m por pedido · 25,6 % SKUs con defecto (IC 21,1–30,8) · 61,2 % de la espera en una cola · objetivo −50 % · traspaso en la semana 12.

## Material generado
~8 imágenes y 4–5 clips cortos (entrada, pasillo, salida). Referencia: ~370 créditos (económica) o ~620 (equilibrada) en OpenArt. Los gráficos del kit y el estante son gratis.

## Pendiente de decidir
1. ¿A quién convence: empresas que contratan un SD, personas que quieren serlo, o ambos?
2. ¿Firma Mytra FDE y aparece `fdekit`?
3. ¿Económica o equilibrada?
