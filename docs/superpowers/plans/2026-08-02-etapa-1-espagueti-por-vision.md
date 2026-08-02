# Etapa 1 — Espagueti por visión (maqueta de mesa)

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usar
> `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans` para implementar tarea por tarea. Los pasos usan
> checkbox (`- [ ]`) para seguimiento.

**Goal:** medir el recorrido real de un carro con una cámara y marcadores
impresos, y producir un `EventLog` que las herramientas existentes del kit ya
saben analizar — todo demostrable sobre un escritorio en menos de dos minutos.

**Architecture:** tres capas con el mismo corte que `transcribe()` vs
`draft_observations()`. `vision.py` (pesada, `cv2`) sólo detecta marcadores y
escribe un CSV de detecciones crudas. Todo lo demás —homografía, pistas,
pseudonimización, cobertura, comparación contra el modelo— es Python puro sobre
ese CSV, y por eso se desarrolla y se testea entero sin cámara y sin `cv2`.

**Tech Stack:** Python 3.11, numpy, pandas, pytest. `opencv-contrib-python` sólo
en el extra `vision`. La homografía se resuelve con numpy (DLT), **no** con
`cv2.findHomography`, para que la capa pura no dependa de OpenCV.

**Spec:** [`docs/superpowers/specs/2026-08-02-toolkit-hardware-design.md`](../specs/2026-08-02-toolkit-hardware-design.md)

## Global Constraints

- **Regla 2** — `cv2` no entra al núcleo. Sólo `src/fdekit/field/vision.py` puede
  importarlo, y sólo adentro de la función, nunca a nivel de módulo.
- **Regla 3** — toda función que mide devuelve su cobertura al lado. Nunca un
  número de terreno sin `MeasurementCoverage`.
- **Regla 4** — `today`/`t0` como argumento. Prohibido `datetime.now()`,
  `date.today()` o `time.time()` dentro de una función de análisis.
- **Regla 8** — ningún campo `*_annual` en estos módulos. Todo en la ventana
  observada, con su denominador al lado.
- **Regla 9 (nueva)** — ninguna identidad cruza el borde. `marker_id` crudo nunca
  se escribe a disco ni sale de `tracks.py`.
- **Regla 10 (nueva)** — ningún agregado por debajo de `k=3` sujetos distintos.
- **Estilo del repo** — comentarios en castellano sin tildes dentro del código
  (el resto del repo es así); docstrings que explican **por qué**, no qué.
- **Tests** — `pytest -q` verde antes de cada commit. Hoy: 423.

---

## Estructura de archivos

| archivo | responsabilidad | pesado? |
|---|---|---|
| `src/fdekit/field/__init__.py` | exporta lo que consume el resto del kit | no |
| `src/fdekit/field/coverage.py` | `MeasurementCoverage` — la honestidad de una medición | no |
| `src/fdekit/field/privacy.py` | sal de sesión, pseudonimización, compuerta *k* | no |
| `src/fdekit/field/homography.py` | píxeles → metros del sistema de `Layout` | no |
| `src/fdekit/field/tracks.py` | detecciones → pistas → `EventLog` | no |
| `src/fdekit/field/vision.py` | video → CSV de detecciones. Único que toca `cv2` | **sí** |
| `src/fdekit/groundtruth.py` | modelo vs medición, con cobertura | no |
| `tests/test_field_coverage.py` | | |
| `tests/test_field_privacy.py` | | |
| `tests/test_field_homography.py` | | |
| `tests/test_field_tracks.py` | | |
| `tests/test_groundtruth.py` | | |
| `tests/test_field_vision.py` | marcado `@pytest.mark.vision`, excluido por defecto | |
| `pyproject.toml` | extra `vision`, marker `vision` | |

**Desviación consciente del spec:** el spec pone `groundtruth.py` en la etapa 3.
Lo traigo a la etapa 1 (tarea 8) porque es Python puro, se testea entero con
datos sintéticos, y sin él la etapa 1 entrega "otro diagrama de espagueti" — que
el kit ya dibuja. El residual es el entregable diferenciador y no hay razón
técnica para esperarlo. Si el revisor no está de acuerdo, la tarea 8 se corta
sin tocar las otras siete.

---

## Task 1: Resolver D1 — ¿hay OpenCV compatible?

Investigación, no código. Bloquea la tarea 7 y **sólo** la tarea 7.

**Files:**
- Modify: `docs/superpowers/specs/2026-08-02-toolkit-hardware-design.md` (fila D1)

**Interfaces:**
- Consumes: nada.
- Produces: la decisión de qué versión declarar en el extra `vision` de la tarea 7.

**Contexto:** el venv tiene numpy 2.4.6. Las ruedas de `opencv-contrib-python`
tuvieron mucho tiempo un pin a `numpy<2`. Si no hay rueda compatible, la tarea 7
cambia de dependencia, y las tareas 2-6 y 8 no se enteran.

- [ ] **Step 1: Ver qué ruedas existen sin instalarlas**

```bash
python -m pip index versions opencv-contrib-python
python -m pip download opencv-contrib-python --no-deps --dest /tmp/cvprobe --no-binary :none:
```

- [ ] **Step 2: Instalar en un venv descartable, NO en el del kit**

```bash
python -m venv /tmp/cvprobe-venv
/tmp/cvprobe-venv/Scripts/python -m pip install -q "numpy==2.4.6" opencv-contrib-python
/tmp/cvprobe-venv/Scripts/python -c "import cv2, numpy; print(cv2.__version__, numpy.__version__, hasattr(cv2,'aruco'))"
```

Esperado: imprime versión, `2.4.6`, y `True`.

- [ ] **Step 3: Registrar el resultado en el spec**

Reemplazar la fila D1 de la tabla de la sección 11 por la respuesta concreta:
versión mínima de `opencv-contrib-python` que funciona con numpy 2.4, o el
motivo por el que no hay ninguna.

**Si NO hay rueda compatible**, el plan B es `pupil-apriltags` (marcadores
AprilTag en vez de ArUco, sin OpenCV). Anotarlo como D1-bis y seguir: las tareas
2-6 y 8 no cambian, porque el contrato entre `vision.py` y `tracks.py` es un CSV
de detecciones, no un objeto de OpenCV. **Ese es el motivo del corte.**

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-02-toolkit-hardware-design.md
git commit -m "docs: cerrar D1 — compatibilidad de opencv-contrib con numpy 2.4"
```

---

## Task 2: `MeasurementCoverage`

**Files:**
- Create: `src/fdekit/field/__init__.py`
- Create: `src/fdekit/field/coverage.py`
- Test: `tests/test_field_coverage.py`

**Interfaces:**
- Consumes: nada.
- Produces: `MeasurementCoverage(frames_total: int, frames_with_marker: int, tracks_seen: int, tracks_expected: int | None = None, discarded_low_confidence: int = 0)`, con propiedades `frame_pct: float`, `track_pct: float | None`, `is_complete: bool`, y método `note() -> str`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_field_coverage.py
"""La cobertura de una medicion de terreno.

Es el analogo de `Coverage` en `decide/query.py`: la promesa del repo no es
resolver siempre, es no mentir nunca en silencio. Una camara que no vio la
mitad de los viajes tiene que decirlo al lado del numero, no despues.
"""

from fdekit.field import MeasurementCoverage


def test_reporta_el_porcentaje_de_frames_con_marcador():
    c = MeasurementCoverage(frames_total=1000, frames_with_marker=750, tracks_seen=8)
    assert c.frame_pct == 75.0


def test_nunca_se_declara_completa():
    # Igual que Coverage: is_complete es False SIEMPRE, y por eso se muestra.
    c = MeasurementCoverage(frames_total=100, frames_with_marker=100, tracks_seen=1)
    assert c.is_complete is False


def test_track_pct_es_none_cuando_no_se_sabe_cuantos_viajes_hubo():
    # Sobre la mesa no hay WMS que diga cuantos pedidos habia. Inventar un
    # denominador seria peor que no tenerlo.
    c = MeasurementCoverage(frames_total=100, frames_with_marker=90, tracks_seen=3)
    assert c.track_pct is None

    c2 = MeasurementCoverage(
        frames_total=100, frames_with_marker=90, tracks_seen=3, tracks_expected=4
    )
    assert c2.track_pct == 75.0


def test_no_divide_por_cero_con_cero_frames():
    c = MeasurementCoverage(frames_total=0, frames_with_marker=0, tracks_seen=0)
    assert c.frame_pct == 0.0


def test_la_nota_menciona_lo_descartado():
    c = MeasurementCoverage(
        frames_total=1000,
        frames_with_marker=600,
        tracks_seen=5,
        discarded_low_confidence=12,
    )
    n = c.note()
    assert "60" in n
    assert "12" in n
    assert "no tratar" in n.lower()
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_coverage.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.field'`

- [ ] **Step 3: Implementación mínima**

```python
# src/fdekit/field/coverage.py
"""Honestidad de una medicion de terreno.

Analogo de `Coverage` en `decide/query.py`, y por la misma razon: una camara
ve lo que ve. Un residual calculado sobre el 40% de los viajes es un numero
util SOLO si va acompanado del 40%. Sin eso es la mentira silenciosa que este
repo persigue.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MeasurementCoverage:
    """Que fraccion de la realidad vio efectivamente el sensor.

    tracks_expected es opcional a proposito: sobre la mesa no hay WMS que diga
    cuantos viajes hubo, y fabricar un denominador para poder mostrar un
    porcentaje lindo es exactamente lo que no hacemos.
    """

    frames_total: int
    frames_with_marker: int
    tracks_seen: int
    tracks_expected: int | None = None
    discarded_low_confidence: int = 0

    @property
    def frame_pct(self) -> float:
        if self.frames_total <= 0:
            return 0.0
        return round(self.frames_with_marker / self.frames_total * 100, 1)

    @property
    def track_pct(self) -> float | None:
        if not self.tracks_expected:
            return None
        return round(self.tracks_seen / self.tracks_expected * 100, 1)

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def note(self) -> str:
        partes = [
            f"{self.frames_with_marker}/{self.frames_total} frames con marcador "
            f"({self.frame_pct}%)",
            f"{self.tracks_seen} viajes reconstruidos",
        ]
        if self.track_pct is not None:
            partes.append(f"{self.track_pct}% de los viajes esperados")
        if self.discarded_low_confidence:
            partes.append(f"{self.discarded_low_confidence} tramos descartados por baja confianza")
        return (
            ", ".join(partes)
            + ". No tratar esta medicion como exhaustiva: lo que el marcador no "
            "mostro no esta en el numero."
        )
```

```python
# src/fdekit/field/__init__.py
"""Toolkit de terreno — sensores que miden lo que el WMS infiere.

El corte que gobierna el paquete: `vision` es la unica pieza que toca cv2, y
solo produce detecciones crudas. Todo lo demas es Python puro sobre un CSV, y
por eso se testea sin camara.
"""

from .coverage import MeasurementCoverage

__all__ = ["MeasurementCoverage"]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_coverage.py -q && python -m pytest -q`
Expected: PASS, y la suite completa sigue verde.

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/field/ tests/test_field_coverage.py
git commit -m "feat: MeasurementCoverage — la honestidad de una medicion de terreno"
```

---

## Task 3: `privacy.py` — el borde que la identidad no cruza

**Files:**
- Create: `src/fdekit/field/privacy.py`
- Modify: `src/fdekit/field/__init__.py`
- Test: `tests/test_field_privacy.py`

**Interfaces:**
- Consumes: nada.
- Produces: `new_session_salt() -> bytes`; `pseudonymize(raw_id: str, salt: bytes) -> str` (devuelve `"sub-<12 hex>"`); `AnonymityGate(k: int = 3)` con `allows(n_subjects: int) -> bool` y `check(n_subjects: int, what: str) -> None`; `AnonymityError(ValueError)`; `IDENTITY_FIELDS: frozenset[str]`; `assert_no_identity(payload: object) -> None`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_field_privacy.py
"""Regla 9: la identidad no cruza el borde del dispositivo.

Esto no es una politica escrita en un PDF, es una propiedad del codigo. Los
tests de abajo SON la garantia que se muestra en la sala del cliente.
"""

import pytest

from fdekit.field.privacy import (
    IDENTITY_FIELDS,
    AnonymityError,
    AnonymityGate,
    assert_no_identity,
    new_session_salt,
    pseudonymize,
)


def test_el_seudonimo_es_estable_dentro_de_la_sesion():
    salt = new_session_salt()
    assert pseudonymize("MARKER-07", salt) == pseudonymize("MARKER-07", salt)


def test_el_seudonimo_cambia_entre_sesiones():
    # La sal no se persiste: manana nadie —ni nosotros— puede revertir el mapeo
    # de ayer. Es lo que hace que la anonimizacion no sea reversible por diseno.
    a = pseudonymize("MARKER-07", new_session_salt())
    b = pseudonymize("MARKER-07", new_session_salt())
    assert a != b


def test_el_seudonimo_no_contiene_el_original():
    salt = new_session_salt()
    p = pseudonymize("PICK-MARCELA", salt)
    assert "MARCELA" not in p.upper()
    assert p.startswith("sub-")


def test_dos_sujetos_distintos_no_colisionan():
    salt = new_session_salt()
    assert pseudonymize("MARKER-07", salt) != pseudonymize("MARKER-08", salt)


def test_la_compuerta_bloquea_bajo_k():
    g = AnonymityGate(k=3)
    assert g.allows(3) is True
    assert g.allows(2) is False

    with pytest.raises(AnonymityError, match="3"):
        g.check(2, "zona A turno noche")


def test_la_compuerta_nombra_que_bloqueo():
    # Un error que no dice que agregado se bloqueo obliga a adivinar.
    with pytest.raises(AnonymityError, match="zona A"):
        AnonymityGate(k=3).check(1, "zona A")


def test_ningun_campo_de_identidad_sobrevive_el_borde():
    ok = {"subject": "sub-a1b2c3d4e5f6", "distance_m": 41.2}
    assert_no_identity(ok) is None

    for campo in IDENTITY_FIELDS:
        with pytest.raises(AnonymityError, match=campo):
            assert_no_identity({campo: "lo que sea", "distance_m": 1.0})


def test_la_deteccion_de_identidad_es_recursiva():
    # Un identificador escondido tres niveles abajo es igual de identificador.
    payload = {"zonas": [{"tracks": [{"marker_id": "MARKER-07"}]}]}
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(payload)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_privacy.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.field.privacy'`

- [ ] **Step 3: Implementación mínima**

```python
# src/fdekit/field/privacy.py
"""Regla 9: el sensor ve al operador; el archivo que sale del sensor, no.

La agregacion no es una promesa en un documento: es una propiedad del codigo,
verificada por `tests/test_field_privacy.py`. Esa distincion es el argumento
central del toolkit — casi todos los vendors venden vigilancia disfrazada de
productividad; aca la medicion viene con olvido disenado.

Limite conocido: con dos operadores por zona el umbral k no impide deducir
quien es quien. Lo mitiga, no lo elimina. Ver seccion 6 del spec.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

SALT_BYTES = 16
_PSEUDONYM_HEX = 12

# Nombres de campo que, si aparecen en una salida, significan que algo se
# escapo. La lista es deliberadamente amplia: un falso positivo cuesta un
# renombre, un falso negativo cuesta el despliegue.
IDENTITY_FIELDS = frozenset(
    {"marker_id", "sensor_id", "resource_raw", "operator", "operator_id", "name", "rut"}
)


class AnonymityError(ValueError):
    """Se intento emitir algo que identifica a una persona."""


def new_session_salt() -> bytes:
    """Sal de sesion, en memoria y nunca persistida.

    Que no se guarde es el punto: sin la sal, el mapeo seudonimo -> marcador no
    se puede reconstruir manana. La irreversibilidad es por diseno, no por
    promesa.
    """
    return os.urandom(SALT_BYTES)


def pseudonymize(raw_id: str, salt: bytes) -> str:
    digest = hashlib.blake2b(raw_id.encode("utf-8"), salt=salt, digest_size=8).hexdigest()
    return f"sub-{digest[:_PSEUDONYM_HEX]}"


@dataclass(frozen=True)
class AnonymityGate:
    """Analoga a la compuerta de volumen de la fase 4 de `decide`.

    Bajo k sujetos distintos, un "agregado por zona" es un individuo con otro
    nombre. k=3 es un default sin evidencia — ver D3 en el spec.
    """

    k: int = 3

    def allows(self, n_subjects: int) -> bool:
        return n_subjects >= self.k

    def check(self, n_subjects: int, what: str) -> None:
        if not self.allows(n_subjects):
            raise AnonymityError(
                f"'{what}' cubre {n_subjects} sujeto(s) y el umbral es {self.k}. "
                "Un agregado bajo el umbral identifica; no se emite."
            )


def assert_no_identity(payload: object) -> None:
    """Recorre la salida completa y falla si sobrevivio un identificador.

    Recursivo a proposito: el modo de falla real no es olvidarse de anonimizar
    el campo principal, es dejar el crudo enterrado en una estructura anidada.
    """
    if isinstance(payload, dict):
        for clave, valor in payload.items():
            if clave in IDENTITY_FIELDS:
                raise AnonymityError(
                    f"el campo '{clave}' identifica y no puede cruzar el borde "
                    "(regla 9). Pseudonimizar con privacy.pseudonymize antes de emitir."
                )
            assert_no_identity(valor)
    elif isinstance(payload, (list, tuple, set)):
        for item in payload:
            assert_no_identity(item)
```

Agregar a `src/fdekit/field/__init__.py`:

```python
from .privacy import AnonymityError, AnonymityGate, assert_no_identity, new_session_salt, pseudonymize

__all__ = [
    "MeasurementCoverage",
    "AnonymityError",
    "AnonymityGate",
    "assert_no_identity",
    "new_session_salt",
    "pseudonymize",
]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_privacy.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/field/privacy.py src/fdekit/field/__init__.py tests/test_field_privacy.py
git commit -m "feat: regla 9 — la identidad no cruza el borde del dispositivo"
```

---

## Task 4: `homography.py` — píxeles a metros, con numpy solo

**Files:**
- Create: `src/fdekit/field/homography.py`
- Modify: `src/fdekit/field/__init__.py`
- Test: `tests/test_field_homography.py`

**Interfaces:**
- Consumes: nada.
- Produces: `FloorHomography` con `FloorHomography.from_points(px: list[tuple[float, float]], meters: list[tuple[float, float]]) -> FloorHomography` y `to_meters(x_px: float, y_px: float) -> tuple[float, float]`.

**Por qué numpy y no `cv2.findHomography`:** si la homografía dependiera de
OpenCV, la capa pura dejaría de ser pura y la regla 2 se rompería. Son ocho
ecuaciones lineales; `np.linalg.lstsq` las resuelve.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_field_homography.py
"""Píxeles -> metros del sistema de coordenadas de `Layout`.

Es el punto de enchufe entre la camara y todo lo que el kit ya sabe hacer: si
la proyeccion cae en el mismo sistema que `Layout.xy`, `travel_report` y el
espagueti funcionan sin tocarse.
"""

import numpy as np
import pytest

from fdekit.field.homography import FloorHomography

# Cuadrado de 100x100 px que en el piso son 10x10 m.
PX = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
M = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def test_recupera_una_escala_pura():
    h = FloorHomography.from_points(PX, M)
    assert h.to_meters(50.0, 50.0) == pytest.approx((5.0, 5.0), abs=1e-6)


def test_clava_las_esquinas_que_se_le_dieron():
    h = FloorHomography.from_points(PX, M)
    for (xp, yp), (xm, ym) in zip(PX, M):
        assert h.to_meters(xp, yp) == pytest.approx((xm, ym), abs=1e-6)


def test_recupera_una_homografia_con_perspectiva_real():
    # Una camara en diagonal no da una escala pura: da perspectiva. Se genera
    # una homografia conocida, se proyectan 4 puntos, y se verifica que
    # from_points la reconstruye para un QUINTO punto que no vio.
    verdad = np.array([[0.10, 0.01, 0.0], [0.00, 0.09, 0.0], [0.0012, 0.0004, 1.0]])

    def proyectar(x, y):
        v = verdad @ np.array([x, y, 1.0])
        return (v[0] / v[2], v[1] / v[2])

    px = [(0.0, 0.0), (120.0, 5.0), (130.0, 95.0), (10.0, 110.0)]
    metros = [proyectar(x, y) for x, y in px]

    h = FloorHomography.from_points(px, metros)
    assert h.to_meters(60.0, 55.0) == pytest.approx(proyectar(60.0, 55.0), abs=1e-4)


def test_error_bajo_5_cm_en_el_centro_de_la_escena():
    # Criterio de la seccion 8 del spec.
    h = FloorHomography.from_points(PX, M)
    x, y = h.to_meters(50.0, 50.0)
    assert abs(x - 5.0) < 0.05 and abs(y - 5.0) < 0.05


def test_exige_exactamente_cuatro_correspondencias():
    with pytest.raises(ValueError, match="cuatro"):
        FloorHomography.from_points(PX[:3], M[:3])

    with pytest.raises(ValueError, match="misma cantidad"):
        FloorHomography.from_points(PX, M[:3])


def test_puntos_colineales_fallan_con_mensaje_util():
    # Cuatro puntos sobre una recta no definen un plano. Es el error que comete
    # todo el mundo la primera vez que pega las marcas en el piso.
    colineales = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    with pytest.raises(ValueError, match="colineales|degenerad"):
        FloorHomography.from_points(colineales, M)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_homography.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.field.homography'`

- [ ] **Step 3: Implementación mínima**

```python
# src/fdekit/field/homography.py
"""Proyeccion del plano de la imagen al plano del piso.

Cuatro puntos del piso con coordenadas conocidas en metros bastan para mapear
cualquier pixel a metros. Se resuelve con numpy —ocho ecuaciones lineales— y
no con cv2.findHomography, porque esta capa tiene que seguir corriendo en el
notebook prestado del CD, sin OpenCV instalado (regla 2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_MIN_AREA_M2 = 1e-6


@dataclass(frozen=True)
class FloorHomography:
    matrix: tuple[tuple[float, float, float], ...]

    @staticmethod
    def from_points(
        px: list[tuple[float, float]], meters: list[tuple[float, float]]
    ) -> "FloorHomography":
        if len(px) != len(meters):
            raise ValueError(
                f"px y meters tienen que tener la misma cantidad de puntos "
                f"({len(px)} vs {len(meters)})"
            )
        if len(px) != 4:
            raise ValueError(f"hacen falta exactamente cuatro correspondencias, llegaron {len(px)}")

        a, b = [], []
        for (x, y), (bigx, bigy) in zip(px, meters):
            a.append([x, y, 1, 0, 0, 0, -bigx * x, -bigx * y])
            b.append(bigx)
            a.append([0, 0, 0, x, y, 1, -bigy * x, -bigy * y])
            b.append(bigy)

        amat = np.asarray(a, dtype=float)
        if np.linalg.matrix_rank(amat) < 8:
            raise ValueError(
                "los cuatro puntos son colineales o degenerados: no definen un plano. "
                "Pegar las marcas formando un cuadrilatero, no una linea."
            )

        h, *_ = np.linalg.lstsq(amat, np.asarray(b, dtype=float), rcond=None)
        m = np.append(h, 1.0).reshape(3, 3)
        return FloorHomography(matrix=tuple(tuple(float(v) for v in fila) for fila in m))

    def to_meters(self, x_px: float, y_px: float) -> tuple[float, float]:
        m = np.asarray(self.matrix, dtype=float)
        v = m @ np.array([float(x_px), float(y_px), 1.0])
        if abs(v[2]) < _MIN_AREA_M2:
            raise ValueError(
                f"el punto ({x_px}, {y_px}) cae en el horizonte de la homografia y "
                "no tiene proyeccion finita en el piso"
            )
        return (float(v[0] / v[2]), float(v[1] / v[2]))
```

Agregar `FloorHomography` a los imports y `__all__` de `src/fdekit/field/__init__.py`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_homography.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/field/homography.py src/fdekit/field/__init__.py tests/test_field_homography.py
git commit -m "feat: homografia piso/imagen resuelta con numpy, sin OpenCV"
```

---

## Task 5: `tracks.py` — detecciones a pistas, con cobertura

**Files:**
- Create: `src/fdekit/field/tracks.py`
- Modify: `src/fdekit/field/__init__.py`
- Test: `tests/test_field_tracks.py`

**Interfaces:**
- Consumes: `FloorHomography` (tarea 4), `MeasurementCoverage` (tarea 2), `new_session_salt`/`pseudonymize` (tarea 3).
- Produces: `Detection(marker_id: str, frame: int, x_px: float, y_px: float)`; `TrackPoint(t_s: float, x_m: float, y_m: float)`; `load_detections(path: str | Path) -> list[Detection]`; `build_tracks(detections, homography, fps, salt, min_points=3) -> tuple[dict[str, list[TrackPoint]], MeasurementCoverage]`; `track_distance_m(points: list[TrackPoint]) -> float`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_field_tracks.py
"""Detecciones crudas -> pistas en metros.

Toda esta capa se testea con detecciones sinteticas: sin camara, sin cv2 y sin
video. Ese es el motivo del corte de la regla 2, y el motivo por el que la
etapa 1 se puede terminar antes de comprar nada.
"""

import pytest

from fdekit.field.homography import FloorHomography
from fdekit.field.privacy import new_session_salt
from fdekit.field.tracks import Detection, build_tracks, load_detections, track_distance_m

# 100 px = 10 m, escala 0.1.
H = FloorHomography.from_points(
    [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
)


def _linea(marker: str, n: int, paso_px: float = 10.0) -> list[Detection]:
    """Un marcador que avanza en linea recta, un paso por frame."""
    return [Detection(marker, f, f * paso_px, 0.0) for f in range(n)]


def test_reconstruye_la_distancia_de_una_recta_conocida():
    # 10 frames avanzando 10 px = 90 px recorridos = 9 m.
    tracks, _ = build_tracks(_linea("M1", 10), H, fps=10.0, salt=new_session_salt())
    (puntos,) = tracks.values()
    assert track_distance_m(puntos) == pytest.approx(9.0, abs=0.02)


def test_la_distancia_no_depende_de_la_tasa_de_cuadros():
    """Invariante prioritario del spec, seccion 8.

    Si duplicar los fps cambiara la distancia, el numero dependeria de la
    camara y no del CD — que es la version de camara del bug de anualizacion.
    """
    lenta = _linea("M1", 10, paso_px=10.0)
    rapida = [Detection("M1", f, f * 5.0, 0.0) for f in range(19)]

    d_lenta = track_distance_m(list(build_tracks(lenta, H, 10.0, new_session_salt())[0].values())[0])
    d_rapida = track_distance_m(
        list(build_tracks(rapida, H, 20.0, new_session_salt())[0].values())[0]
    )
    assert d_lenta == pytest.approx(d_rapida, abs=0.02)


def test_el_tiempo_sale_de_los_frames_y_del_fps():
    tracks, _ = build_tracks(_linea("M1", 5), H, fps=10.0, salt=new_session_salt())
    (puntos,) = tracks.values()
    assert puntos[0].t_s == pytest.approx(0.0)
    assert puntos[-1].t_s == pytest.approx(0.4)  # frame 4 a 10 fps


def test_separa_marcadores_distintos_en_pistas_distintas():
    dets = _linea("M1", 5) + _linea("M2", 5)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt())
    assert len(tracks) == 2
    assert cov.tracks_seen == 2


def test_las_claves_son_seudonimos_y_no_el_marcador_crudo():
    # Regla 9: el marker_id no sale de esta funcion.
    tracks, _ = build_tracks(_linea("MARKER-07", 5), H, 10.0, new_session_salt())
    (clave,) = tracks.keys()
    assert clave.startswith("sub-")
    assert "MARKER-07" not in clave


def test_una_pista_demasiado_corta_se_descarta_y_baja_la_cobertura():
    # Dos detecciones sueltas no son un viaje: son ruido. Descartarlas en
    # silencio seria mentir; van al contador de descartes.
    dets = _linea("M1", 10) + _linea("M2", 2)
    tracks, cov = build_tracks(dets, H, 10.0, new_session_salt(), min_points=3)
    assert len(tracks) == 1
    assert cov.discarded_low_confidence == 1


def test_la_oclusion_baja_la_cobertura_pero_no_la_distancia_en_silencio():
    """El invariante que mas importa de todos.

    Si el marcador se pierde 5 frames en el medio, la distancia medida baja
    —porque el tramo tapado no se vio— pero la cobertura TIENE que reflejarlo.
    Una distancia menor con cobertura del 100% seria el bug de la clase
    'no falla, miente' en su version de camara.
    """
    completa = _linea("M1", 20)
    con_hueco = [d for d in completa if not (8 <= d.frame < 13)]

    _, cov_ok = build_tracks(completa, H, 10.0, new_session_salt(), frames_total=20)
    _, cov_hueco = build_tracks(con_hueco, H, 10.0, new_session_salt(), frames_total=20)

    assert cov_ok.frame_pct == 100.0
    assert cov_hueco.frame_pct == 75.0


def test_load_detections_lee_el_csv_del_detector(tmp_path):
    csv = tmp_path / "detecciones.csv"
    csv.write_text(
        "marker_id,frame,x_px,y_px\nM1,0,10.5,20.5\nM1,1,11.5,20.5\n", encoding="utf-8"
    )
    dets = load_detections(csv)
    assert dets == [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]


def test_load_detections_rechaza_un_csv_sin_las_columnas():
    import io

    from fdekit.field.tracks import parse_detections

    with pytest.raises(ValueError, match="falta"):
        parse_detections(io.StringIO("marcador,cuadro\nM1,0\n"))
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_tracks.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.field.tracks'`

- [ ] **Step 3: Implementación mínima**

```python
# src/fdekit/field/tracks.py
"""Detecciones crudas -> pistas en metros, con cobertura.

Frontera del toolkit: de aca para abajo no hay camara, no hay cv2 y no hay
video — hay una lista de tuplas. Un CSV de detecciones grabado una vez permite
desarrollar y testear el 100% de la logica sin hardware.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterable

from .coverage import MeasurementCoverage
from .homography import FloorHomography
from .privacy import pseudonymize

_COLUMNAS = ("marker_id", "frame", "x_px", "y_px")


@dataclass(frozen=True)
class Detection:
    marker_id: str
    frame: int
    x_px: float
    y_px: float


@dataclass(frozen=True)
class TrackPoint:
    t_s: float
    x_m: float
    y_m: float


def parse_detections(handle: IO[str]) -> list[Detection]:
    reader = csv.DictReader(handle)
    faltan = [c for c in _COLUMNAS if c not in (reader.fieldnames or [])]
    if faltan:
        raise ValueError(f"al CSV de detecciones le falta(n) la(s) columna(s): {faltan}")
    return [
        Detection(r["marker_id"], int(r["frame"]), float(r["x_px"]), float(r["y_px"]))
        for r in reader
    ]


def load_detections(path: str | Path) -> list[Detection]:
    with open(path, encoding="utf-8", newline="") as fh:
        return parse_detections(fh)


def build_tracks(
    detections: Iterable[Detection],
    homography: FloorHomography,
    fps: float,
    salt: bytes,
    min_points: int = 3,
    frames_total: int | None = None,
) -> tuple[dict[str, list[TrackPoint]], MeasurementCoverage]:
    """Agrupa detecciones por marcador y las proyecta a metros.

    `frames_total` es el largo del video. Se pasa por afuera porque las
    detecciones solo contienen los frames donde SE VIO algo: derivarlo de ellas
    daria siempre 100% de cobertura, que es justo la mentira que hay que evitar.
    """
    if fps <= 0:
        raise ValueError(f"fps tiene que ser positivo, llego {fps}")

    dets = sorted(detections, key=lambda d: (d.marker_id, d.frame))
    por_marcador: dict[str, list[Detection]] = {}
    for d in dets:
        por_marcador.setdefault(d.marker_id, []).append(d)

    tracks: dict[str, list[TrackPoint]] = {}
    descartadas = 0
    for marker_id, grupo in por_marcador.items():
        if len(grupo) < min_points:
            descartadas += 1
            continue
        puntos = []
        for d in grupo:
            x_m, y_m = homography.to_meters(d.x_px, d.y_px)
            puntos.append(TrackPoint(t_s=d.frame / fps, x_m=x_m, y_m=y_m))
        tracks[pseudonymize(marker_id, salt)] = puntos

    frames_vistos = len({d.frame for d in dets})
    total = frames_total if frames_total is not None else frames_vistos
    cobertura = MeasurementCoverage(
        frames_total=total,
        frames_with_marker=frames_vistos,
        tracks_seen=len(tracks),
        discarded_low_confidence=descartadas,
    )
    return tracks, cobertura


def track_distance_m(points: list[TrackPoint]) -> float:
    """Distancia recorrida, en linea entre muestras consecutivas.

    A diferencia de `Layout.route_distance`, aca NO se rutea por el layout: la
    camara ve el camino que el operador efectivamente hizo, incluidos los que
    el modelo no contempla. Esa diferencia es todo el punto del toolkit.
    """
    return float(
        sum(
            math.dist((a.x_m, a.y_m), (b.x_m, b.y_m))
            for a, b in zip(points, points[1:])
        )
    )
```

Agregar `Detection`, `TrackPoint`, `build_tracks`, `load_detections`,
`track_distance_m` a los imports y `__all__` de `src/fdekit/field/__init__.py`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_tracks.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/field/tracks.py src/fdekit/field/__init__.py tests/test_field_tracks.py
git commit -m "feat: detecciones -> pistas en metros, con cobertura explicita"
```

---

## Task 6: Pistas a `EventLog` — enchufar con el kit existente

**Files:**
- Modify: `src/fdekit/field/tracks.py`
- Modify: `src/fdekit/field/__init__.py`
- Test: `tests/test_field_tracks.py` (agregar al final)

**Interfaces:**
- Consumes: `TrackPoint`, `Layout`, `EventLog`.
- Produces: `nearest_location(layout: Layout, x_m: float, y_m: float, level: int = 1) -> str`; `dwell_events(points: list[TrackPoint], layout: Layout, min_dwell_s: float = 4.0, radius_m: float = 1.5) -> list[tuple[float, str]]`; `tracks_to_eventlog(tracks: dict[str, list[TrackPoint]], layout: Layout, t0: pd.Timestamp, min_dwell_s: float = 4.0) -> EventLog`.

**Simplificación consciente de la etapa 1:** una pista = un caso. Segmentar
viajes por cercanía al `DOCK` es lógica de etapa 3 con un CD real; sobre la mesa
el carro hace un viaje. Queda documentado en el docstring, no escondido.

- [ ] **Step 1: Escribir el test que falla**

**Los imports van al tope del archivo, no acá.** Agregar `import pandas as pd`,
`from fdekit.layout import Layout`, `from fdekit.timestudy import travel_report`
y `dwell_events, nearest_location, tracks_to_eventlog` al bloque de imports
existente de `tests/test_field_tracks.py` (tarea 5); las constantes `LAY` y `T0`
van junto a `H`. Sólo las funciones de test se agregan al final. Un import a
mitad de archivo es un defecto de rúbrica y no hay razón para incurrirlo.

```python
# al tope de tests/test_field_tracks.py, junto a los imports de la tarea 5
import pandas as pd

from fdekit.field.tracks import TrackPoint, dwell_events, nearest_location, tracks_to_eventlog
from fdekit.layout import Layout
from fdekit.timestudy import travel_report

LAY = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)
T0 = pd.Timestamp("2026-09-14 10:00:00")

# --- y de aca para abajo, al FINAL del archivo, solo las funciones de test:


def test_nearest_location_cae_en_la_ubicacion_del_layout():
    # Layout.xy("01-002-1") = (1*3.0, 2*1.0) = (3.0, 2.0)
    assert nearest_location(LAY, 3.05, 2.05) == "01-002-1"
    assert nearest_location(LAY, 6.0, 3.0) == "02-003-1"


def test_dwell_events_ignora_el_paso_y_marca_la_parada():
    # Pasa cerca de 01-002-1 medio segundo y se queda 6 s en 02-003-1.
    puntos = [TrackPoint(0.0, 3.0, 2.0), TrackPoint(0.5, 4.5, 2.5)]
    puntos += [TrackPoint(1.0 + i, 6.0, 3.0) for i in range(7)]

    paradas = dwell_events(puntos, LAY, min_dwell_s=4.0)
    assert [loc for _, loc in paradas] == ["02-003-1"]


def test_tracks_to_eventlog_produce_algo_que_travel_report_ya_sabe_leer():
    """El enchufe: si el EventLog es valido, el kit entero funciona sin cambios."""
    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    puntos += [TrackPoint(10.0 + i, 6.0, 3.0) for i in range(6)]

    log = tracks_to_eventlog({"sub-abc123": puntos}, LAY, t0=T0)
    t = travel_report(log, LAY)

    assert len(t) == 1
    assert t.loc[0, "n_stops"] == 2
    assert t.loc[0, "distance_m"] > 0


def test_tracks_to_eventlog_no_lee_el_reloj():
    """Regla 4: t0 es argumento. Dos llamadas con el mismo t0 dan lo mismo."""
    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    a = tracks_to_eventlog({"sub-abc123": puntos}, LAY, t0=T0)
    b = tracks_to_eventlog({"sub-abc123": puntos}, LAY, t0=T0)
    assert a.df["timestamp"].tolist() == b.df["timestamp"].tolist()


def test_el_eventlog_no_lleva_identidad():
    from fdekit.field.privacy import assert_no_identity

    puntos = [TrackPoint(0.0 + i, 3.0, 2.0) for i in range(6)]
    log = tracks_to_eventlog({"sub-abc123": puntos}, LAY, t0=T0)
    assert_no_identity(log.df.to_dict("records"))
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_tracks.py -q`
Expected: FAIL con `ImportError: cannot import name 'nearest_location'`

- [ ] **Step 3: Implementación mínima**

```python
# agregar a src/fdekit/field/tracks.py

import pandas as pd

from ..layout import Layout
from ..processmining.log import EventLog


def nearest_location(layout: Layout, x_m: float, y_m: float, level: int = 1) -> str:
    """Ubicacion del layout mas cercana a un punto del piso.

    El nivel se fija en 1 porque una camara cenital no ve altura: la pista dice
    en que modulo estuvo el carro, no a que altura estiro el brazo el operador.
    """
    mejor, mejor_d = None, float("inf")
    for a in range(1, layout.aisles + 1):
        for b in range(1, layout.bays + 1):
            code = layout.location_code(a, b, level)
            lx, ly = layout.xy(code)
            d = (lx - x_m) ** 2 + (ly - y_m) ** 2
            if d < mejor_d:
                mejor, mejor_d = code, d
    return mejor


def dwell_events(
    points: list[TrackPoint],
    layout: Layout,
    min_dwell_s: float = 4.0,
    radius_m: float = 1.5,
) -> list[tuple[float, str]]:
    """Paradas reales, no lugares por los que se paso.

    Un picker cruza medio CD sin tocar nada. Contar cada ubicacion por la que
    pasa como una visita infla el conteo y despues infla el caso economico.
    """
    if not points:
        return []

    paradas: list[tuple[float, str]] = []
    ancla = points[0]
    inicio = points[0].t_s
    for p in points[1:]:
        if math.dist((p.x_m, p.y_m), (ancla.x_m, ancla.y_m)) <= radius_m:
            continue
        if p.t_s - inicio >= min_dwell_s:
            paradas.append((inicio, nearest_location(layout, ancla.x_m, ancla.y_m)))
        ancla, inicio = p, p.t_s

    if points[-1].t_s - inicio >= min_dwell_s:
        paradas.append((inicio, nearest_location(layout, ancla.x_m, ancla.y_m)))
    return paradas


def tracks_to_eventlog(
    tracks: dict[str, list[TrackPoint]],
    layout: Layout,
    t0: pd.Timestamp,
    min_dwell_s: float = 4.0,
) -> EventLog:
    """Pistas medidas -> el contrato de datos que el kit entero ya come.

    `t0` es argumento y no `pd.Timestamp.now()` (regla 4): una funcion que lee
    el reloj no se puede testear.

    Simplificacion consciente de la etapa 1: una pista = un caso. Segmentar
    viajes por cercania al DOCK necesita un CD real con dock; sobre la mesa el
    carro hace un viaje. Queda para la etapa 3.
    """
    filas = []
    for subject, puntos in tracks.items():
        for t_s, loc in dwell_events(puntos, layout, min_dwell_s=min_dwell_s):
            filas.append(
                {
                    "case_id": subject,
                    "activity": "PICK",
                    "timestamp": t0 + pd.Timedelta(seconds=float(t_s)),
                    "resource": subject,
                    "location": loc,
                }
            )
    if not filas:
        filas = []
    return EventLog(pd.DataFrame(filas, columns=["case_id", "activity", "timestamp", "resource", "location"]))
```

Agregar `nearest_location`, `dwell_events`, `tracks_to_eventlog` al `__init__.py`.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_tracks.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/field/tracks.py src/fdekit/field/__init__.py tests/test_field_tracks.py
git commit -m "feat: pistas medidas -> EventLog, sin tocar las herramientas existentes"
```

---

## Task 7: `vision.py` — la capa pesada, y sólo ella

**Files:**
- Create: `src/fdekit/field/vision.py`
- Create: `tests/test_field_vision.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `Detection` (tarea 5).
- Produces: `detect_markers(video_path: str | Path, dictionary: str = "DICT_4X4_50") -> tuple[list[Detection], int]` — devuelve las detecciones y el total de frames del video; `write_detections(detections: list[Detection], path: str | Path) -> None`.

**Depende de la tarea 1.** Si D1 dio "no hay rueda compatible", cambiar la
dependencia a `pupil-apriltags` y el cuerpo de `detect_markers`; el resto del
plan no se toca.

- [ ] **Step 1: Declarar el extra y el marker**

En `pyproject.toml`, junto al extra `audio` y con el mismo comentario de por qué:

```toml
[project.optional-dependencies]
dev = ["pytest>=7.4"]
# torch NO es dependencia del nucleo: el kit tiene que correr en el notebook
# prestado de un CD, sin GPU y sin permisos de instalacion.
audio = ["transformers>=4.44", "torch>=2.2", "accelerate"]
# cv2 tampoco: `vision` solo hace falta para convertir un video en un CSV de
# detecciones. Con el CSV ya hecho, todo el analisis corre sin OpenCV.
vision = ["opencv-contrib-python>=4.10"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["vision: necesita OpenCV y un video de muestra"]
addopts = "-m 'not vision'"
```

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_field_vision.py
"""Capa pesada: la unica que toca cv2.

Marcado `vision` y excluido por defecto — la suite tiene que correr en el
notebook prestado del CD, sin OpenCV. Correr con: pytest -m vision
"""

import pytest

from fdekit.field.tracks import Detection


def test_el_modulo_no_importa_cv2_al_cargarse():
    """Regla 2: importar `fdekit.field` no puede exigir OpenCV.

    Este test NO esta marcado `vision` a proposito: es justamente el que
    verifica que se puede vivir sin OpenCV, asi que tiene que correr siempre.
    """
    import sys

    sys.modules.pop("cv2", None)
    import fdekit.field.vision  # noqa: F401

    assert "cv2" not in sys.modules


def test_detect_markers_avisa_claro_si_falta_opencv():
    import fdekit.field.vision as v

    if v._tiene_cv2():
        pytest.skip("OpenCV instalado; el camino de error no aplica")
    with pytest.raises(ImportError, match="pip install"):
        v.detect_markers("cualquier.mp4")


@pytest.mark.vision
def test_detecta_un_marcador_en_un_video_de_muestra(tmp_path):
    import fdekit.field.vision as v

    dets, frames = v.detect_markers("tests/data/marcador_muestra.mp4")
    assert frames > 0
    assert dets and isinstance(dets[0], Detection)


def test_write_detections_escribe_las_columnas_que_load_detections_espera(tmp_path):
    import fdekit.field.vision as v
    from fdekit.field.tracks import load_detections

    dets = [Detection("M1", 0, 10.5, 20.5), Detection("M1", 1, 11.5, 20.5)]
    destino = tmp_path / "d.csv"
    v.write_detections(dets, destino)

    assert load_detections(destino) == dets
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_vision.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.field.vision'`

- [ ] **Step 4: Implementación mínima**

```python
# src/fdekit/field/vision.py
"""Video -> CSV de detecciones. La UNICA pieza del toolkit que toca cv2.

El import va adentro de la funcion, nunca a nivel de modulo: `import
fdekit.field` tiene que funcionar en el notebook prestado del CD, donde no hay
OpenCV ni permiso para instalarlo (regla 2). Es el mismo patron que
`gemba/transcribe.py` con torch.

Este archivo no tiene logica: detecta y escribe. Todo lo demas —homografia,
pistas, cobertura, privacidad— vive en la capa pura y se testea sin camara.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .tracks import Detection

_MENSAJE_SIN_CV2 = (
    "esta funcion necesita OpenCV, que no es dependencia del nucleo. "
    "pip install 'fde-field-kit[vision]'. Si ya tenes el CSV de detecciones, "
    "no hace falta: usa fdekit.field.load_detections."
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
    tramo que el marcador no mostro desapareceria en silencio.
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


def write_detections(detections: list[Detection], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["marker_id", "frame", "x_px", "y_px"])
        for d in detections:
            w.writerow([d.marker_id, d.frame, d.x_px, d.y_px])
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_vision.py -q && python -m pytest -q`
Expected: PASS (el test marcado `vision` queda deseleccionado por `addopts`).

- [ ] **Step 6: Commit**

```bash
git add src/fdekit/field/vision.py tests/test_field_vision.py pyproject.toml
git commit -m "feat: capa de vision aislada en el extra vision, cv2 fuera del nucleo"
```

---

## Task 8: `groundtruth.py` — el residual

> **Extensión consciente del spec** (que la ubica en la etapa 3). Ver la nota de
> la sección "Estructura de archivos". Se puede cortar sin tocar las tareas 1-7.

**Files:**
- Create: `src/fdekit/groundtruth.py`
- Test: `tests/test_groundtruth.py`

**Interfaces:**
- Consumes: `EventLog`, `Layout`, `MeasurementCoverage`.
- Produces: `compare_travel(modeled: EventLog, measured_tracks: dict[str, list[TrackPoint]], layout: Layout, coverage: MeasurementCoverage, today: date) -> dict` con claves `modeled_m_in_window`, `measured_m_in_window`, `residual_pct`, `orders_modeled`, `orders_measured`, `coverage_note`, `today`.

**Desvío de firma respecto del spec.** La sección 7 del spec escribe
`compare_travel(modeled, measured: EventLog, layout, today)`. Acá recibe las
pistas crudas y la cobertura, por dos razones: la distancia **medida** no se
puede recuperar de un `EventLog` (el `EventLog` sólo guarda las paradas, no el
camino entre ellas — y el camino es justamente lo que el modelo no sabe), y la
cobertura tiene que entrar para poder salir (regla 3). Al cerrar la tarea,
actualizar la firma en la sección 7 del spec para que no queden desalineados.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_groundtruth.py
"""El residual entre el recorrido calculado y el medido.

Es la razon de ser del toolkit: el kit ya dibuja un espagueti a partir de
aritmetica sobre el layout. Este modulo lo falsifica. Cierra H1 — el proyecto
pasa de tener un modelo a tener un modelo con residual medido.
"""

from datetime import date

import pandas as pd
import pytest

from fdekit.field.coverage import MeasurementCoverage
from fdekit.field.tracks import TrackPoint
from fdekit.groundtruth import compare_travel
from fdekit.layout import DOCK, Layout
from fdekit.processmining.log import EventLog

LAY = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)
T0 = pd.Timestamp("2026-09-14 10:00:00")
HOY = date(2026, 9, 14)
COV = MeasurementCoverage(frames_total=100, frames_with_marker=100, tracks_seen=1)


def _log_modelado() -> EventLog:
    # Un pedido: DOCK -> 01-002-1 -> 01-004-1 -> DOCK = 5 + 2 + 7 = 14 m
    return EventLog(
        pd.DataFrame(
            [
                {"case_id": "A", "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
                {"case_id": "A", "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
            ]
        )
    )


def test_residual_cero_cuando_la_medicion_coincide_con_el_modelo():
    # Pista que recorre exactamente 14 m.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)

    assert r["modeled_m_in_window"] == pytest.approx(14.0)
    assert r["measured_m_in_window"] == pytest.approx(14.0)
    assert r["residual_pct"] == pytest.approx(0.0)


def test_recupera_un_desvio_inyectado():
    # 21 m medidos contra 14 modelados = +50%.
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["residual_pct"] == pytest.approx(50.0, abs=0.1)


def test_siempre_devuelve_la_nota_de_cobertura():
    """Regla 3. Un residual sin cobertura no se publica."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert "no tratar" in r["coverage_note"].lower()


def test_no_devuelve_ningun_campo_anual():
    """Regla 8: la anualizacion vive en value/levers, y en ningun otro lado."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert not [k for k in r if "annual" in k or "anual" in k]


def test_no_lee_el_reloj():
    """Regla 4: `today` es argumento."""
    puntos = [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 14.0)]
    r = compare_travel(_log_modelado(), {"sub-a": puntos}, LAY, COV, today=HOY)
    assert r["today"] == "2026-09-14"


def test_sin_medicion_no_inventa_un_residual():
    r = compare_travel(_log_modelado(), {}, LAY, COV, today=HOY)
    assert r["measured_m_in_window"] == 0.0
    assert r["residual_pct"] is None


def test_el_residual_no_depende_del_largo_de_la_ventana():
    """Tercer invariante prioritario del spec, seccion 8.

    Es el mismo invariante que el de anualizacion, en su version de camara:
    medir una hora o medir un turno tiene que dar el mismo residual, porque
    modelo y medicion escalan juntos. Si no, el porcentaje que se le muestra al
    cliente depende de cuanto duro la grabacion.
    """
    corta_mod = _log_modelado()
    corta_med = {"sub-a": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)]}

    # La misma ventana, tres veces: tres pedidos identicos y tres pistas.
    filas = []
    for caso in ("A", "B", "C"):
        filas += [
            {"case_id": caso, "activity": "PICK", "timestamp": T0, "resource": None, "location": "01-002-1"},
            {"case_id": caso, "activity": "PICK", "timestamp": T0 + pd.Timedelta(seconds=60), "resource": None, "location": "01-004-1"},
        ]
    larga_mod = EventLog(pd.DataFrame(filas))
    larga_med = {
        f"sub-{i}": [TrackPoint(0.0, 0.0, 0.0), TrackPoint(1.0, 0.0, 21.0)] for i in range(3)
    }

    r_corta = compare_travel(corta_mod, corta_med, LAY, COV, today=HOY)
    r_larga = compare_travel(larga_mod, larga_med, LAY, COV, today=HOY)
    assert r_corta["residual_pct"] == pytest.approx(r_larga["residual_pct"], abs=0.1)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_groundtruth.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.groundtruth'`

- [ ] **Step 3: Implementación mínima**

```python
# src/fdekit/groundtruth.py
"""Modelo vs medicion: el residual, con su cobertura al lado.

El kit dibuja el espagueti con aritmetica sobre el layout, asumiendo que el
picker va directo entre ubicaciones por la transversal optima. Este modulo mide
cuanto se equivoca ese supuesto.

El entregable no es un grafico mas lindo: es una frase del tipo "el modelo dice
8 km/dia, la medicion dice 11,3 — el 41% son viajes que el WMS no registra".
Sin este modulo el proyecto es infalsable (hueco H1).
"""

from __future__ import annotations

from datetime import date

from .field.coverage import MeasurementCoverage
from .field.tracks import TrackPoint, track_distance_m
from .layout import Layout
from .processmining.log import EventLog
from .timestudy.spaghetti import travel_report


def compare_travel(
    modeled: EventLog,
    measured_tracks: dict[str, list[TrackPoint]],
    layout: Layout,
    coverage: MeasurementCoverage,
    today: date,
) -> dict:
    """Compara el recorrido calculado contra el medido en la misma ventana.

    `today` es argumento, no `date.today()` (regla 4). Todo en la ventana
    observada, sin ningun campo anual (regla 8): si esto alimenta el caso
    economico, la anualizacion ocurre en value/levers.py::_annualize.
    """
    t = travel_report(modeled, layout)
    modelado_m = float(t["distance_m"].sum())
    medido_m = float(sum(track_distance_m(p) for p in measured_tracks.values()))

    residual = None
    if modelado_m > 0 and measured_tracks:
        residual = round((medido_m / modelado_m - 1) * 100, 1)

    return {
        "modeled_m_in_window": round(modelado_m, 1),
        "measured_m_in_window": round(medido_m, 1),
        "residual_pct": residual,
        "orders_modeled": int(len(t)),
        "orders_measured": int(len(measured_tracks)),
        # Regla 3: la cobertura viaja pegada al numero, no en otro archivo.
        "coverage_note": coverage.note(),
        "today": today.isoformat(),
    }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_groundtruth.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/groundtruth.py tests/test_groundtruth.py
git commit -m "feat: groundtruth — el residual entre el espagueti calculado y el medido"
```

---

## Task 9: El comando de la demo de mesa

**Files:**
- Modify: `src/fdekit/cli.py`
- Modify: `README.md`
- Test: `tests/test_field_cli.py` (crear)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: subcomando `fdekit field --detections <csv> --refs <csv> --out <dir>`; función `run_field(detections, refs, out, fps, t0, today, layout: Layout | None = None) -> dict`.

**La geometría entra por argumento.** Un escritorio de 1 m no es un CD de 12
pasillos: si `run_field` fijara `Layout()`, la taza caería en "pasillo 2 módulo
2" y el número perdería significado físico. `layout=None` usa el CD por defecto;
la maqueta pasa el suyo.

**Criterio de éxito de la etapa 1:** este comando produce el espagueti en
pantalla en menos de dos minutos, sobre un escritorio, sin red.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_field_cli.py
"""La demo de mesa entera, de CSV a grafico.

Es el criterio de exito de la etapa 1 del spec, y las dos capas de CLI del kit
no tienen tests (punto 3 de la cola de pendientes del handoff). Esta arranca
con uno.
"""

from datetime import date

import pandas as pd
import pytest

from fdekit.cli import run_field
from fdekit.layout import Layout

REFS = "x_px,y_px,x_m,y_m\n0,0,0,0\n100,0,10,0\n100,100,10,10\n0,100,0,10\n"
# La geometria de la maqueta, no la del CD: 10x10 m de escritorio.
MESA = Layout(aisles=4, bays=10, levels=2, aisle_pitch=3.0, bay_pitch=1.0)


def _detecciones() -> str:
    filas = ["marker_id,frame,x_px,y_px"]
    # Se queda 6 s en un punto, se mueve, se queda 6 s en otro. 10 fps.
    filas += [f"M1,{f},30.0,20.0" for f in range(0, 60, 5)]
    filas += [f"M1,{f},60.0,30.0" for f in range(100, 160, 5)]
    return "\n".join(filas) + "\n"


def test_la_demo_de_mesa_produce_espagueti_y_residual(tmp_path):
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones(), encoding="utf-8")

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )

    assert (tmp_path / "out" / "espagueti_medido.png").exists()
    assert r["tracks"] == 1
    assert r["measured_m_in_window"] > 0
    assert "no tratar" in r["coverage_note"].lower()


def test_la_salida_no_lleva_identidad(tmp_path):
    from fdekit.field.privacy import assert_no_identity

    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones(), encoding="utf-8")

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )
    assert_no_identity(r)


def test_la_geometria_se_respeta_y_no_se_fuerza_la_del_cd(tmp_path):
    """La maqueta no es un CD de doce pasillos.

    Con dos geometrias distintas el mismo recorrido cae en ubicaciones
    distintas. Si `run_field` fijara `Layout()`, este test no notaria la
    diferencia — y la taza sobre el escritorio quedaria reportada en el pasillo
    2 modulo 2, que es un numero sin significado fisico.
    """
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones(), encoding="utf-8")

    comun = dict(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
    )
    a = run_field(out=tmp_path / "a", layout=MESA, **comun)
    b = run_field(out=tmp_path / "b", layout=Layout(), **comun)

    # Las paradas son las mismas dos; lo que cambia es a que ubicacion caen.
    assert a["stops"] == b["stops"] == 2
    assert a["locations"] != b["locations"]


def test_avisa_si_el_csv_de_referencias_no_tiene_cuatro_filas(tmp_path):
    (tmp_path / "refs.csv").write_text("x_px,y_px,x_m,y_m\n0,0,0,0\n", encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones(), encoding="utf-8")

    with pytest.raises(ValueError, match="cuatro"):
        run_field(
            detections=tmp_path / "det.csv",
            refs=tmp_path / "refs.csv",
            out=tmp_path / "out",
            fps=10.0,
            t0=pd.Timestamp("2026-09-14 10:00:00"),
            today=date(2026, 9, 14),
            layout=MESA,
        )
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_field_cli.py -q`
Expected: FAIL con `ImportError: cannot import name 'run_field'`

- [ ] **Step 3: Implementación mínima**

```python
# agregar a src/fdekit/cli.py

def run_field(detections, refs, out, fps, t0, today, layout=None) -> dict:
    """Demo de mesa: CSV de detecciones -> espagueti medido + residual.

    `t0` y `today` son argumentos (regla 4). `out` se crea si no existe.

    `layout` tambien es argumento: un escritorio de un metro no es un CD de doce
    pasillos, y fijar el layout por defecto haria que la taza cayera en "pasillo
    2 modulo 2". El numero seguiria saliendo, y no querria decir nada.
    """
    import csv as _csv
    from pathlib import Path

    from .field.homography import FloorHomography
    from .field.privacy import new_session_salt
    from .field.tracks import build_tracks, load_detections, track_distance_m, tracks_to_eventlog
    from .layout import Layout
    from .timestudy.spaghetti import plot_spaghetti

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    with open(refs, encoding="utf-8", newline="") as fh:
        filas = list(_csv.DictReader(fh))
    if len(filas) != 4:
        raise ValueError(
            f"el CSV de referencias necesita exactamente cuatro filas (esquinas "
            f"del piso con coordenadas conocidas), llegaron {len(filas)}"
        )

    homografia = FloorHomography.from_points(
        [(float(f["x_px"]), float(f["y_px"])) for f in filas],
        [(float(f["x_m"]), float(f["y_m"])) for f in filas],
    )

    lay = layout or Layout()
    tracks, cobertura = build_tracks(
        load_detections(detections), homografia, fps=fps, salt=new_session_salt()
    )
    log = tracks_to_eventlog(tracks, lay, t0=t0)
    plot_spaghetti(log, lay, path=str(out / "espagueti_medido.png"))

    return {
        "tracks": len(tracks),
        "measured_m_in_window": round(
            sum(track_distance_m(p) for p in tracks.values()), 1
        ),
        "stops": int(len(log)),
        # Las ubicaciones dependen de la geometria que se paso, y por eso van en
        # la salida: son lo que deja ver si el layout declarado es el correcto.
        "locations": sorted(log.df["location"].dropna().unique().tolist()),
        "coverage_note": cobertura.note(),
        "today": today.isoformat(),
    }
```

El CLI **no** despacha con `args.cmd`: cada subparser hace
`set_defaults(func=...)` y `main()` llama `args.func(args)`. Seguir ese patrón,
junto a `cmd_travel` (línea 89) y su parser (línea 297):

```python
# junto a los otros cmd_*, cerca de cmd_travel
def cmd_field(a):
    """El reloj se lee UNA sola vez, aca en el borde, y nunca en el analisis.

    `run_field` recibe t0 y today como argumentos (regla 4). Esta funcion es el
    unico lugar del camino que tiene permitido mirar el reloj.
    """
    import datetime as _dt

    from .layout import Layout

    out = run_field(
        detections=a.detections,
        refs=a.refs,
        out=a.out,
        fps=a.fps,
        t0=pd.Timestamp.now(),
        today=_dt.date.today(),
        layout=Layout(
            aisles=a.aisles, bays=a.bays, aisle_pitch=a.aisle_pitch, bay_pitch=a.bay_pitch
        ),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0
```

```python
# en build_parser, despues del bloque de `travel`
    f = sub.add_parser("field", help="demo de mesa: detecciones -> espagueti medido")
    f.add_argument("--detections", required=True)
    f.add_argument("--refs", required=True, help="CSV con 4 esquinas: x_px,y_px,x_m,y_m")
    f.add_argument("--out", default="out")
    f.add_argument("--fps", type=float, default=30.0)
    # Geometria: los defaults son los del CD. La maqueta de escritorio pasa la
    # suya (p.ej. --aisles 4 --bays 10 --aisle-pitch 3 --bay-pitch 1).
    f.add_argument("--aisles", type=int, default=12)
    f.add_argument("--bays", type=int, default=50)
    f.add_argument("--aisle-pitch", type=float, default=3.0)
    f.add_argument("--bay-pitch", type=float, default=1.2)
    f.set_defaults(func=cmd_field)
```

`json` y `pandas as pd` ya están importados a nivel de módulo en `cli.py`
(líneas 17 y 21); no agregar imports duplicados.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_field_cli.py -q && python -m pytest -q`
Expected: PASS

- [ ] **Step 5: Documentar la maqueta en el README**

Agregar esta sección a `README.md`, después del bloque de CLI:

````markdown
## La maqueta de mesa — medir en vez de inferir

El espagueti de la herramienta 2 se **calcula** con aritmética sobre el layout.
`fdekit field` lo **mide**, y la diferencia entre los dos es el hallazgo.

Procedimiento completo, sobre un escritorio, en menos de dos minutos:

1. Imprimir un marcador ArUco del diccionario `DICT_4X4_50` (cualquier
   generador en línea; sirve papel común) y pegarlo a una taza, que hace de
   carro de picking.
2. Marcar cuatro esquinas del escritorio con cinta y medirlas con huincha.
   Escribir `refs.csv`:

   ```
   x_px,y_px,x_m,y_m
   0,0,0,0
   100,0,10,0
   100,100,10,10
   0,100,0,10
   ```

   Los `x_px,y_px` salen de mirar el primer cuadro del video; los `x_m,y_m` de
   la huincha. **Cuatro filas exactas, y que no queden alineadas** — cuatro
   puntos sobre una recta no definen un plano.
3. Grabar 30 segundos moviendo la taza y deteniéndola unos segundos en dos o
   tres "ubicaciones".
4. Convertir el video en detecciones (única parte que necesita OpenCV):

   ```bash
   pip install 'fde-field-kit[vision]'
   python -c "from fdekit.field.vision import detect_markers, write_detections; d,n=detect_markers('mesa.mp4'); write_detections(d,'det.csv'); print(n,'frames')"
   ```

5. Y el análisis, que **no** necesita OpenCV:

   ```bash
   fdekit field --detections det.csv --refs refs.csv --out out --fps 30 \
                --aisles 4 --bays 10 --aisle-pitch 3 --bay-pitch 1
   ```

   Los cuatro flags de geometría describen la maqueta. Sin ellos se usa la del
   CD (12 pasillos × 50 módulos), y la taza sobre el escritorio quedaría
   reportada en el pasillo 2 módulo 2 — un número que sale, y que no quiere
   decir nada.

En `out/espagueti_medido.png` queda el recorrido real. La salida en consola trae
los metros medidos y la nota de cobertura — qué fracción de los cuadros vio
efectivamente el marcador. **Un recorrido sin cobertura no se muestra a un
cliente:** lo que la cámara no vio no está en el número, y callarlo sería el
error más caro que puede cometer este kit.

Ninguna identidad sale del proceso: el `marker_id` se hashea con una sal de
sesión que nunca se escribe a disco, y `tests/test_field_privacy.py` lo
verifica. El sensor ve al operador; el archivo que sale, no.
````

- [ ] **Step 6: Commit**

```bash
git add src/fdekit/cli.py tests/test_field_cli.py README.md
git commit -m "feat: fdekit field — la demo de mesa completa, de CSV a espagueti"
```

---

## Cierre de la etapa

Al terminar la tarea 9:

- [ ] `python -m pytest -q` verde. Base al arrancar la etapa: **493** (correr
      `python -m pytest -q` antes de la tarea 2 y anotar el número real; la base
      se movió durante la escritura del plan). Esperado al cerrar: base + ~48.
- [ ] `python -m pytest -m vision -q` corre (con OpenCV instalado) o se salta limpio.
- [ ] Actualizar `HANDOFF.md`: nueva sección del toolkit de terreno, reglas 9 y 10
      en la lista de decisiones de diseño, y el conteo de tests.
- [ ] Marcar la etapa 1 como cerrada en la tabla de la sección 9 del spec.
- [ ] Revisar la cola de la sección 11 del spec: D1 cerrada, D3 y D4 siguen
      abiertas y bloquean la etapa 3.
