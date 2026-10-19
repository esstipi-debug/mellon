# BRIEF: "Five reasonable requests" (video v5)

**Idea a explicar (la tesis):** un polímata solo vale si cada rama de su saber *cambia una decisión*. El Strategist Deployed (SD) es el rol cuyo trabajo es decidir qué NO construir y qué construir antes de que el ingeniero (FDE) escriba una línea. No se demuestra nombrando disciplinas: se demuestra que, en un caso, cada petición razonable de un especialista habría sido un error, y cada error lo detecta una rama distinta, con un número.

**Para quién:** líderes que despliegan tecnología/IA en operaciones (LinkedIn/X). Sin límite de duración estricto; objetivo ~3:15 para explicar bien.

**Qué debe poder decir el espectador al final (sin sonido también):** "el SD evita que construyan lo equivocado combinando varias disciplinas, y deja a alguien a cargo de que funcione cuando él se va".

**Acción siguiente (CTA):** pregunta, no promesa: "¿Tu despliegue tiene a alguien que decida qué no construir?"

## Lo verdadero y lo sintético
- El caso es un **centro de distribución sintético** generado por `fdekit demo` (800 pedidos, 1.800 SKUs). Se rotula. No es un cliente real.
- Cada cifra sale de `hallazgos.json` / `A3.md` del demo y es reproducible. Cifras usadas:
  - 54,12 % de pedidos siguen el flujo declarado; 31 caminos.
  - Simulación (7 recolectores = situación actual), ciclo medio por nº de recolectores: 4→90,5 min; 5→39,4; 6→12,0; 7→9,6; 8→9,6; 9→8,7.
  - Operarios: medianas 67,3–71,4 s (dentro de ~6 %); p90 de ~76 a ~99 min en los siete.
  - Excepción de ubicación en 16,6 % de pedidos; reproceso de cartón en 30,75 %; defecto de maestro 25,6 % (IC 21,1–30,8) con muestra de 317 SKUs; riesgo de reproceso 2,26× (59,8 % vs 26,5 %); arreglar maestros elimina ~13,8 % del reproceso.
  - Caminata mediana 157,2 m por pedido. Re-slotting (estimación del modelo): 49,4 m → 34,6 m ponderados (−29,8 %); 67,6 % de las visitas son a clase A y solo 13,5 % de la clase A está en zona dorada.
  - Diseño de piloto: n ingenuo 343 por grupo; efecto de diseño 36,48; n ajustado 12.512; ~16 días por grupo (con ICC medido en 6 días, muy incierto).
- Las ideas de libros se atribuyen (título + autor), parafraseadas, sin citas.
- Hecho histórico: 1951, Trist y Bamforth (viene del manifiesto); no se afirman cifras.
- Nada se afirma sobre clientes reales ni sobre Palantir.

## Nunca afirmar
Resultados de un cliente real; que Mytra o fdekit ya fue usado en producción; cifras no listadas arriba; que las reglas del A3 "funcionan" fuera de la simulación del kit.

## Restricciones de forma (de la skill motion-video-kit, adaptadas a un explicativo largo)
- Cada beat con un aterrizaje legible y una salida que acelera; sin campo vacío; el sujeto principal ocupa 60–85 % del cuadro.
- Composiciones distintas por beat (gráfico, diagrama, plano, tipografía de impacto).
- Un actor persistente (el punto ámbar del SD) y un camino continuo; los objetos se transfieren entre beats.
- Subtítulos y sonido: se entiende en mudo; locución EN + música discreta.
- Derivar el método de `echris6/motion-video-kit` (MIT). Del repo `feitangyuan/onetake` (PolyForm Noncommercial) se toma la idea de "carry" y "concepto antes de beats", no el código.
