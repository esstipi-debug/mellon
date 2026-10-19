# Casos y fuentes para el guion v2: qué se puede afirmar en público

Revisé el repo (`knowledge-graph/`) y busqué en la web (19-oct-2026). Estado de verificación: **verificado** = lo confirmé en una fuente; **parcial** = existe, pero faltan detalles o hay cifras en disputa; **no usable** = inventado o no verificable.

## 1. Lo que hay en el repo, y su límite

- `graph.json` (193 nodos, 8 libros): su propio `meta.source` dice *"Synthesized from general knowledge of the books (no book text ingested). Descriptions are paraphrases, not quotes."* → sirve para **estructurar ideas y atribuirlas** (libro + autor). **No** para citar frases textuales ni páginas sin comprobarlas contra el libro.
- `scenarios.json`, casos Palantir (Airbus, Tyson, NHS, PG&E, Jacobs, Cleveland Clinic): el README los define como *"training syntheses inspired by publicly reported deployment patterns… stakeholder quotes and decisions are constructed"*. → **no usable como hechos.** Las citas del VP, "15 sistemas aislados", "18 meses de Data Lake", "$200M", "18% de registros duplicados" son material de entrenamiento. Si aparecen en el video, solo como *"composite / ilustrativo"* y sin nombre de empresa.
- `docs/HANDOFF.md` y `docs/HISTORIA.md`: aún no los usé para hechos del proyecto Mytra; los leo si el video va a hablar de Mytra.

## 2. Casos reales con fuente

| Caso | Qué se puede decir | Estado | Fuente |
|---|---|---|---|
| **Minas de carbón, 1951 (Trist y Bamforth, Tavistock)** | La mecanización del *longwall* desarmó los equipos pequeños de trabajo, y con ellos la base social de la seguridad y la productividad; origen del enfoque sociotécnico. Ya está en el manifiesto. | **Parcial:** confirmé el paper y su tesis por resumen secundario; **no** pude leer el artículo ni confirmar cifras. No usar números. | [Human Relations, 1951](https://journals.sagepub.com/doi/10.1177/001872675100400101) · [resumen](https://explore.psychsafety.com/n/trist-bamforth-1951/) |
| **Vietnam, "bright spots" / desviación positiva (Jerry y Monique Sternin, Save the Children, años 90)** | Buscaron familias pobres con niños bien nutridos y copiaron lo que ya hacían (comer más veces al día, añadir camarones y cangrejos del arrozal); las madres lo practicaron en sesiones de dos semanas en vez de recibir charlas. Es el ejemplo de *Switch* (Heath) que ya está en el grafo. | **Parcial:** el método está bien documentado. Evaluaciones tempranas reportaron una caída del 74 % en desnutrición severa de menores de tres años, pero una revisión posterior dice que el diseño era débil para probar causalidad. Decir "reportaron", no "logró". No confirmé el detalle de la comuna (Quang Trach). | [Positive deviance](https://en.wikipedia.org/wiki/Positive_deviance) · [Oxfam](https://frompoverty.oxfam.org.uk/?p=16533) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC527707) |
| **El modelo Echo/Delta de Palantir** | Palantir usa "Deltas" (técnicos) y "Echos" (estrategia/producto); el término Delta viene de los equipos nombrados con letras del alfabeto OTAN. | **Parcial:** el blog de Palantir confirma "Dev" vs "Delta"; la historia del origen en los 2010 viene de blogs de terceros. | [Palantir: Dev versus Delta](https://blog.palantir.com/dev-versus-delta-demystifying-engineering-roles-at-palantir-ad44c2a6e87) |
| **Cleveland Clinic + Palantir** | Se anunció en enero de 2023 un "Virtual Command Center" sobre Foundry, con módulos Hospital 360, Staffing Matrix y OR Stewardship. | **Parcial:** el anuncio es público. Una cifra de "+8 % de traslados" vino de una fuente secundaria. No usarla. | [HealthITAnalytics](https://healthitanalytics.com/news/cleveland-clinic-to-improve-hospital-operations-through-ai-command-center) · [Cleveland Clinic](https://consultqd.clevelandclinic.org/how-ai-assists-with-staffing-scheduling-and-once-tedious-tasks) |
| **NHS England, plataforma federada de datos** | Existe un contrato con Palantir; los resultados están **en disputa** (NHS England y Palantir reportan mejoras, otros organismos las discuten y hay una investigación del regulador de estadísticas). | **No usar resultados.** Tema políticamente sensible; una cifra equivocada o sesgada en un video público es un riesgo. | [City AM](https://www.cityam.com/?p=2449669) · [Palantir blog](https://blog.palantir.com/ready-set-build-with-the-nhs-federated-data-platform-41405fa4c226) |
| **Airbus + Palantir (Skywise)** | Airbus es un cliente emblemático de Foundry. | **Parcial:** el detalle de A350 y el "+33 %" que circula viene de un post agregador sin fuente primaria. No usar cifras. | [Frenchweb](https://www.frenchweb.fr/inside-airbus-comment-palantir-diagnostique-la-maintenance-de-la350/373148) |
| **Cifras del propio manifiesto** (758 consultores BCG, +40 %, 84 % vs 60–70 %, ~2×) | Se pueden usar tal cual, citando a Mollick/Dell'Acqua y a Uzzi et al. | **Verificado en el manifiesto**; conviene contrastar con las fuentes originales antes de publicar. | Lista de lecturas del manifiesto |

## 3. Cómo cambia el guion
1. **Palantir como oficio, no como caso de éxito.** Mostrar la dupla Echo/Delta (estratega + ingeniero), que es lo que describe el manifiesto, y no repetir resultados que el propio cliente o sus críticos discuten.
2. **Escena de terreno = Vietnam, no una bodega inventada.** Es real, tiene fuente y encaja con "ir adonde ocurren las cosas y buscar lo que ya funciona" (*Switch*, bright spots). Se presenta como "reportaron", con el matiz del diseño débil.
3. **Escena de "lo humano es la mitad" = minas de 1951**, sin cifras, tal como está en el manifiesto.
4. **Los casos del Dojo** quedan como material de entrenamiento: se pueden usar como "situación compuesta" rotulada, sin nombre de empresa.
5. **Los libros del grafo** (Switch, Mom Test, Trusted Advisor, etc.) aparecen como créditos de las ideas ("idea de *Switch*, Heath & Heath"), sin citas textuales.

## Pendiente de verificar antes de publicar
- Texto del paper de 1951 y de la evaluación de Vietnam (cifras exactas).
- Fuentes originales de Mollick/Dell'Acqua y Uzzi (para las cifras del manifiesto).
- Si el video habla de Mytra: hechos desde `docs/HANDOFF.md` y `docs/HISTORIA.md`.
