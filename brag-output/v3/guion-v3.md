# Manifiesto del Polímata: guion v3 (un caso, un estratega, los 12 puntos)

**Formato:** 16:9, ~2:20, narración en inglés + subtítulos, para LinkedIn/X.
**Idea:** un solo caso contado en segunda persona ("tú"), así el espectador es el estratega y no hace falta darle género ni nombre. Entras a un centro de distribución donde nadie sabe qué está fallando, y sales con un mapa. Cada beat del caso encarna uno o dos principios, y una etiqueta pequeña en pantalla los nombra ("04 · Think in systems").

## Qué es real y qué es sintético (se rotula en pantalla)
- El caso es un **centro de distribución sintético** generado por `fdekit demo` (800 pedidos, 1.800 SKUs). **No es un cliente real.** Rótulo fijo: *"Synthetic case. Data generated with fdekit; reproducible."*
- Todas las cifras salen de `A3.md` / `hallazgos.json` del demo (copiados en `assets/`). Cualquiera puede reproducirlas con `fdekit demo`.
- Los gráficos (diagrama de espagueti, mapa de calor, flujo real vs declarado) son **salidas reales del kit**: se muestran tal cual, no se redibujan.

## Locución y visuales

| # | Tiempo | Locución (EN) | Principios | Visual | Origen |
|---|---|---|---|---|---|
| 0 | 0:00–0:10 | "The client's system says every order goes: release, pick, consolidate, pack, check, ship. You open the log. Fifty-four percent of orders actually do. The rest found thirty other ways." | Preámbulo | Línea limpia (flujo declarado) que se rompe en una maraña (flujo real) | Kit: `dfg.mmd` (54,12 %, 31 variantes) |
| 1 | 0:10–0:24 | "This is the fog. No rulebook, and a problem that changes while you look at it. Your job is not to describe it. It is to walk out with a map: a scope, a deadline, one number that must move. Cut the waiting in half." | I | La estratega entra al centro; niebla; el A3 en blanco con "objetivo −50 % espera" | Video/imagen generado + A3 |
| 2 | 0:24–0:38 | "You were never just a data person. Your roots are on the warehouse floor. Your branches reach into statistics, simulation, psychology. And the connections come from there: a wrong product dimension in the master data, and a carton that gets repacked." | II, III | Árbol de raíces profundas (ya hecho en v1) que termina en dos puntos que se unen: SKU y cartón | Diagrama (reutilizar) |
| 3 | 0:38–0:52 | "But you don't start at the dashboard. You start at the shift change, standing next to a picker. Show me how you really do it. A hundred and fifty-seven meters walked per order. The spaghetti is on the floor before it is on the screen." | IX | Alguien junto a un operario en el pasillo; corte a `spaghetti.png` sobre el plano | Video generado + kit real |
| 4 | 0:52–1:06 | "Then you doubt. A quarter of the products have bad master data, give or take five points, and you checked it with a physical sample, not with the system. AI transcribes the shift and drafts the analysis. You decide what to believe." | V, VI | Auditoría física en el pasillo; barra "25,6 % (IC 21,1–30,8)"; la IA propone, la estratega elige | Imagen generada + gráfico |
| 5 | 1:06–1:20 | "Nobody is slow. Sixty-one percent of all the waiting sits in one queue, before picking. The resource is undersized at the peak. You don't fix people. You fix the structure that produces the wait." | IV | `heatmap.png`; el cuello de botella resaltado; lazo de retroalimentación | Kit real + diagrama |
| 6 | 1:20–1:36 | "The operators have heard 'automation' before. They hear 'replacement.' So the work sheet gets written with them. The director gets one page: value and risk. The engineer gets the contract and the time zones. One truth, three languages." | VII, VIII | Tres mundos (piso, ingeniería, directorio) y la hoja de trabajo firmada | Imagen generada + diagrama |
| 7 | 1:36–1:52 | "You don't present a deck. You pilot one zone, one wave, with a control group signed in advance. And before quoting any price, the model refuses to promise gainshare without a measured counterfactual. Can we? Should we? Who does it affect?" | X | Zona piloto; grupo de control; las tres preguntas | Imagen generada + diagrama |
| 8 | 1:52–2:08 | "Week twelve, you hand over a runbook and signed sheets. The control limits are frozen, so degradation shows up before the complaint does. Success is what the team does when you are gone. And what you learned goes back as method, for the next fog." | XI, XII | La estratega sale; el equipo sigue; `xmr.png`; vuelve la niebla y un nuevo mapa | Video generado + kit real |
| 9 | 2:08–2:22 | "Where the rules are clear, let the machine win. Where there are none, you are there. And when you leave, the map stays." | Cierre | Mapa completo con la ruta ámbar (v1); título | Diagrama (reutilizar) |

Cobertura: I (1), II (2), III (2), IV (5), V (4), VI (4), VII (6), VIII (6), IX (3), X (7), XI (8), XII (8). Los doce están.

## Cifras usadas y su trazabilidad
| Cifra en el video | Dónde sale |
|---|---|
| 54,12 % de pedidos siguen el flujo declarado; 31 variantes | A3 §2 / `conformance` |
| −50 % de espera como objetivo | A3 §3 |
| 157,2 m caminados por pedido (mediana) | A3 §2 / `travel` |
| 25,6 % de SKUs con defecto, IC95 21,1–30,8 % | A3 §2 / `data_quality` |
| 61,2 % de toda la espera, entre ORDER_RELEASED y PICK; recurso subdimensionado en el pico | A3 §2 y §4 |
| El kit se niega a cotizar gainshare sin contrafactual medido | README (`fdekit.value`) |

Quitadas a propósito: el 2,26× de reproceso y el 14 % de cartón; se pueden volver a incluir en la escena 2 si quieres más datos.

## Material generado que hace falta (solo lo humano)
Aprox. **8 imágenes** (centro de distribución, pasillo con operario, auditoría física, sala de directorio, laboratorio/ingeniería, zona piloto, equipo sin la estratega, niebla/mapa) y **4–5 clips de 6–8 s** (entrada, pasillo, salida).
Referencia de costo en OpenArt (a configuración por defecto): económica ≈ 8×15 + 5×50 = **~370 créditos**; equilibrada ≈ 8×15 + 5×100 = **~620**. Los gráficos del kit son gratis.

## Para decidir
1. ¿Firma Mytra FDE en el cierre y se menciona `fdekit`? (Entonces la escena 7 puede mostrar el comando.)
2. ¿Dejamos la estratega sin género ni nombre (segunda persona), o quieres un personaje con nombre?
3. ¿Opción económica o equilibrada?

---

# v3.1: el contraste que demuestra la tesis ("tres llegadas")

**Decisión:** no se contrasta al SD contra el FDE (son una dupla en el manifiesto y el kit es para FDEs). Se contrasta *el mandato*: tres perfiles llegan al mismo problema el mismo día. Primero se muestra la fortaleza de cada uno; la falla es de mandato, no de competencia.

| Perfil | Qué hace bien | Por qué no cambia nada | Qué le falta (principio) |
|---|---|---|---|
| Consultor de diapositivas | 50 páginas, claras, el viernes | Nadie responde por que algo cambie | Raíces: sin profundidad no hay criterio (II) |
| Analista / especialista | Dashboard exacto: 54 % | Nadie lo abre; el operario no está en el modelo | Amplitud y mandato de adopción (III, VII) |
| SD (con ingeniero) | Se sienta en el turno, sale con un mapa | Responde por el problema **y** la adopción | Es la dupla: el FDE construye (X) |

La IA hace en minutos lo de las dos primeras filas; eso lo une con el hilo "donde hay reglas claras, que gane la máquina".

**Escena nueva (≈22 s, tras la niebla):** *"Three people arrive with the same problem. The first writes a fifty-page deck by Friday. It's good. Nothing changes. The second builds the perfect dashboard. It says fifty-four percent. Nobody opens it. The third doesn't open a laptop. You take a seat at the shift change, and you bring an engineer."* Visual: tres carriles en pantalla dividida; el tercero se sale del cuadro hacia el pasillo.

**Línea de tiempo v3.1 (≈2:20):** 0 gancho 10 s · 1 niebla 14 s · **2 tres llegadas 22 s** (absorbe raíces y conexión SKU→cartón) · 3 terreno + duda + IA 28 s · 4 estructura/cola 12 s · 5 humanos y tres lenguas, con el FDE como aliado 14 s · 6 piloto y ética 14 s · 7 salida y aprendizaje 14 s · 8 cierre 12 s.

**Riesgos y cómo se evitan:** (a) hombres de paja → mostrar el "está bien" de cada uno; (b) tono arrogante → la frase es "nadie responde por el cambio", no "ellos son peores"; (c) el FDE como villano → aparece como aliado en la escena 2 y en la 5.

**Pregunta abierta:** ¿a quién queremos que convenza el video: a empresas que deberían contratar un SD, a personas que quieren ser SD, o a ambos? Cambia el cierre y la llamada a la acción.
