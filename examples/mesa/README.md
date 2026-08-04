# Demo de mesa — `fdekit field` en cinco minutos

Los tres CSV mínimos para correr `fdekit field` sin cámara, sin OpenCV y sin un
centro de distribución. La geometría es un escritorio de 10 × 10 m; el "operario"
es un marcador que se queda quieto 6 s en un punto, se mueve, y se queda 6 s en
otro.

```bash
fdekit field \
  --detections examples/mesa/det.csv \
  --refs examples/mesa/refs.csv \
  --log examples/mesa/wms.csv \
  --out out/mesa \
  --fps 10 --aisles 4 --bays 10 --aisle-pitch 2.5 --bay-pitch 0.7
```

## Qué hay en cada archivo

| Archivo | Qué es | De dónde sale en terreno |
|---|---|---|
| `det.csv` | El marcador visto en el video: `frame`, `x_px`, `y_px` | `fdekit.field.vision` sobre un video (necesita OpenCV) |
| `refs.csv` | Cuatro puntos con píxel **y** metro conocidos | Se miden con cinta en el piso, una vez |
| `wms.csv` | El log del WMS para el mismo pedido | Export del cliente |

La primera línea de `det.csv` es `# frames_total=200`. No es decorativa: es el
**denominador** de la cobertura. Sin ella el comando falla y dice qué falta, en
vez de asumir que el último frame visto es el total — que daría 100 % de
cobertura por casualidad.

## Qué tiene que salir

Este ejemplo está elegido para que el residual salga **mal**, porque el caso
interesante no es el que cierra:

```json
"residual_pct": -84.0,
"residual_flag": "sospechoso",
"dock_legs_pct_of_modeled": 62.6
```

El modelo rutea 19,8 m para el único pedido (andén → parada → parada → andén).
La cámara midió 3,2 m: el salto entre las dos paradas, y **ninguno de los dos
tramos al andén**, que quedan fuera del escritorio.

Residual negativo es tentador de leer como "el modelo clavó". Es lo contrario, y
el kit lo dice: el modelo sólo puede **subestimar** (asume ruta óptima), así que
un residual negativo apunta a un problema de medición —pistas cortadas,
cobertura baja, homografía mal calibrada— y no a precisión. `coverage_note`
declara 24/200 frames (12 %) y `dock_legs_pct_of_modeled` dice que el 62,6 % de
la brecha son los tramos al andén.

## Por qué no se escribe el PNG

Con el `--k 3` por defecto el espagueti **no** sale a disco, y el JSON explica
por qué: hay 1 sujeto y el umbral de anonimato son 3. El gráfico de espagueti es
el itinerario completo de una persona, dibujado — retener la lista de
ubicaciones en el JSON y dejar el PNG al lado sería teatro.

Para verlo, hay que pedirlo a sabiendas:

```bash
fdekit field ... --k 1
```

## Este ejemplo no se puede pudrir

`tests/test_ejemplo_mesa.py` corre **estos archivos**, no una copia inline, y
verifica los números de arriba. Si alguien los edita o los borra, la suite falla.
Un ejemplo que dejó de funcionar es peor que no tener ejemplo.
