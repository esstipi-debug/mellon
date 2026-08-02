"""Video -> CSV de detecciones. La UNICA pieza del toolkit que toca cv2.

El import va adentro de la funcion, nunca a nivel de modulo: `import
fdekit.field` tiene que funcionar en el notebook prestado del CD, donde no hay
OpenCV ni permiso para instalarlo (regla 2). Es el mismo patron que
`gemba/transcribe.py` con torch.

Este archivo no tiene logica: detecta y escribe. Todo lo demas -- homografia,
pistas, cobertura, privacidad -- vive en la capa pura y se testea sin camara.

Contrato de metadatos con `tracks.py`: `write_detections` guarda el total de
frames del video en la primera linea del CSV, comentada, con el formato
`# frames_total=<int>`, antes de la cabecera. `tracks.parse_detections` y
`tracks.load_detections` saltean y leen esa linea si esta presente. Sin esa
linea, `frames_total` es `None` -- no se rellena con una suposicion, porque un
CSV sin metadatos es un CSV del que no se puede afirmar cobertura (regla 3).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .tracks import Detection

_MENSAJE_SIN_CV2 = (
    "esta funcion necesita OpenCV, que no es dependencia del nucleo. "
    "pip install \"fde-field-kit[vision]\". Si ya tenes el CSV de "
    "detecciones grabado, no hace falta OpenCV: usa "
    "fdekit.field.tracks.load_detections directamente sobre ese archivo."
)


def _tiene_cv2() -> bool:
    try:
        import cv2  # noqa: F401

        return True
    except ImportError:
        return False


def detect_markers(
    video_path: str | Path, dictionary: str = "DICT_4X4_50"
) -> tuple[list[Detection], int]:
    """Detecta marcadores ArUco cuadro a cuadro.

    Devuelve tambien el total de frames del video, que NO se puede derivar de
    las detecciones: si se derivara, la cobertura daria siempre 100% y el
    tramo que el marcador no mostro desapareceria en silencio. Quien llame
    tiene que pasarle este numero a `write_detections` para que no se pierda
    al guardar el CSV.
    """
    try:
        import cv2
    except ImportError as e:
        raise ImportError(_MENSAJE_SIN_CV2) from e

    aruco_dict = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"no se pudo abrir el video: {video_path}")

    detecciones: list[Detection] = []
    frame_idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            corners, ids, _ = detector.detectMarkers(frame)
            if ids is not None:
                for esquinas, marker_id in zip(corners, ids.flatten()):
                    centro = esquinas.reshape(4, 2).mean(axis=0)
                    detecciones.append(
                        Detection(
                            marker_id=f"ARUCO-{int(marker_id)}",
                            frame=frame_idx,
                            x_px=float(centro[0]),
                            y_px=float(centro[1]),
                        )
                    )
            frame_idx += 1
    finally:
        cap.release()

    return detecciones, frame_idx


def write_detections(
    detections: list[Detection], path: str | Path, frames_total: int
) -> None:
    """Escribe las detecciones a CSV, con `frames_total` en la primera linea.

    `frames_total` es obligatorio y no opcional: es exactamente el numero que
    `detect_markers` devuelve junto con las detecciones y que se pierde si no
    se guarda ahora -- ver el contrato de metadatos en el docstring del
    modulo. `tracks.build_tracks` lo exige como argumento obligatorio, y un
    CSV sin esta linea no permite reconstruirlo (queda como `None` al leerlo).
    """
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"# frames_total={frames_total}\n")
        w = csv.writer(fh)
        w.writerow(["marker_id", "frame", "x_px", "y_px"])
        for d in detections:
            w.writerow([d.marker_id, d.frame, d.x_px, d.y_px])
