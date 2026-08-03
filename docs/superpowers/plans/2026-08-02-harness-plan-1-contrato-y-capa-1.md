# Harness de self-healing — Plan 1: contrato y capa 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el contrato `fdekit.guard` y la capa 1 del harness (captura pasiva + cosecha aislada con oráculo mecánico), y cerrar con el test que falsifica el harness entero contra los 17 bugs históricos del repo.

**Architecture:** `fdekit.guard` es stdlib pura y viaja en el paquete: `Hallazgo` con procedencia obligatoria, `Guardia` con su motivo al lado, `CoberturaGuardia` que nunca dice estar completa. `tools/harness/` queda fuera del paquete y contiene la capa 1: un hook que sólo observa, y una cosecha a pedido que corre en worktree aislado con dos roles cuyas fronteras se verifican por `git diff`. El oráculo es código, no un agente: corre la suite en el árbol anterior y en el posterior, y rechaza el episodio si el test nuevo no falla en el anterior.

**Tech Stack:** Python 3.11, stdlib, pytest. Sin dependencias nuevas — ni en el paquete ni en las herramientas.

## Global Constraints

- **Sin caracteres acentuados en ningún `.py`** bajo `src/fdekit/` ni `tests/`. Ni tildes ni eñes, ni en comentarios ni en docstrings ni en strings. El guardia `tests/test_convenciones.py` lo verifica y falla la suite. Los `.md` sí llevan acentos normalmente.
- **`src/fdekit/guard/` usa sólo la biblioteca estándar.** Nada de numpy, pandas, scipy, red ni modelos. Viaja al notebook prestado de un centro de distribución.
- **`tools/` no se instala y no está en `[tool.setuptools.packages.find]`.** No se agrega al `pyproject.toml` como paquete.
- **`today` es argumento, nunca `date.today()` adentro de una función.** Regla 4 del repo.
- **Los tests del harness corren sin el harness.** `pytest` verde no puede depender de que la cosecha haya corrido.
- **Formato de commit:** `<tipo>: <descripcion en minuscula, sin acentos>`. Tipos: feat, fix, refactor, docs, test, chore. Sin líneas de atribución.
- **Verificación de suite completa:** `python -m pytest -q` desde `C:\fde\fde-field-kit`.
  **No hay un número absoluto de tests confiable en este plan.** Hay otras sesiones
  commiteando al mismo repo: durante la escritura de este documento la base pasó de 792
  a 797 en veinte minutos. La Tarea 0 mide la base y la llama **B**; cada tarea declara
  su delta contra B. Si un `pytest -q` da menos de lo esperado, alguien más commiteó —
  verificar con `git log` antes de tocar nada.
- **Rama de trabajo:** crear `harness/plan-1` desde `master` antes de la Tarea 1. No commitear a `master`.

---

## Estructura de archivos

**Se crean:**

| archivo | responsabilidad |
|---|---|
| `src/fdekit/guard/__init__.py` | API pública y `__all__` |
| `src/fdekit/guard/hallazgo.py` | `Procedencia`, `Hallazgo` — el dato compartido entre capas |
| `src/fdekit/guard/cobertura.py` | `CoberturaGuardia` — la honestidad del harness |
| `src/fdekit/guard/guardia.py` | `Guardia` y su registro |
| `tools/harness/episodio.py` | `Episodio` y el log append-only |
| `tools/harness/captura.py` | detección rojo→verde, pura |
| `tools/harness/oraculo.py` | veredicto sobre dos árboles |
| `tools/harness/roles.py` | fronteras de testigo y reparador |
| `tools/harness/cosecha.py` | orquestador |
| `tools/harness/indice.py` | genera el índice legible |
| `tools/harness/historia.py` | reconstruye episodios de la historia de git |
| `tests/test_guard.py` | contrato |
| `tests/test_harness_captura.py` | captura y episodios |
| `tests/test_harness_oraculo.py` | oráculo y roles |
| `tests/test_harness_cosecha.py` | orquestación e índice |
| `tests/test_harness_falsificacion.py` | §7.1, marcado `historia` |

**Se modifican:**

| archivo | cambio |
|---|---|
| `tests/test_convenciones.py` | que el guardia cubra `tests/guards/` |
| `pyproject.toml:39-40` | agregar el marcador `historia` |

**Nota de diseño sobre testabilidad:** `oraculo.py`, `captura.py` e `historia.py` reciben la lectura del mundo (correr tests, leer git) como **argumento**, no la hacen adentro. Eso los vuelve funciones puras testeables sin git ni subprocess, que es lo que permite que las Tareas 5-7 tengan tests rápidos y herméticos. Sólo `cosecha.py` y el test de falsificación tocan el mundo real.

---

## Tarea 0: Rama de trabajo

- [ ] **Step 1: Crear la rama desde master**

```bash
cd /c/fde/fde-field-kit
git checkout -b harness/plan-1 master
git rev-parse --abbrev-ref HEAD
```

Expected: `harness/plan-1`

- [ ] **Step 2: Verificar el punto de partida**

Run: `python -m pytest -q`
Expected: pasa sin fallas. **Anotar el número: ese es B.**
Al 2-ago-2026 20:55 era `797 passed, 1 deselected`, y sube solo.

Todas las tareas siguientes expresan lo esperado como `B + n`. Si el total no coincide
con `B + n` pero tampoco hay fallas, otra sesión agregó tests: correr `git log --oneline`
y actualizar B.

---

## Tarea 1: `Hallazgo` con procedencia obligatoria

**Files:**
- Create: `src/fdekit/guard/hallazgo.py`
- Create: `src/fdekit/guard/__init__.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: nada
- Produces: `Procedencia(commit: str, fecha: date, dueno: str)` y `Hallazgo(regla: str, evidencia: str, procedencia: Procedencia, familia: str = "")`, ambos `@dataclass(frozen=True)`. Las tareas 2, 3, 4 y 10 los usan.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_guard.py`:

```python
"""Contrato compartido entre las dos capas del harness.

Estos tests fijan lo unico que ambas capas tienen que respetar. Si alguno se
pone rojo, el contrato cambio y las dos capas hay que mirarlas.
"""

from datetime import date

import pytest

from fdekit.guard import Hallazgo, Procedencia


def _proc(commit="abc1234", dueno="stipi"):
    return Procedencia(commit=commit, fecha=date(2026, 8, 2), dueno=dueno)


def test_un_hallazgo_sin_commit_no_se_construye():
    """La leccion de los hashes del HANDOFF, aplicada al tipo: una afirmacion
    sobre el repo sin commit que la ancle es la que despues engana."""
    with pytest.raises(ValueError, match="commit"):
        Procedencia(commit="", fecha=date(2026, 8, 2), dueno="stipi")


def test_un_hallazgo_sin_dueno_no_se_construye():
    """Regla 1 del repo: lo que va a una cola de revision va con dueno."""
    with pytest.raises(ValueError, match="dueno"):
        Procedencia(commit="abc1234", fecha=date(2026, 8, 2), dueno="")


def test_un_hallazgo_sin_regla_no_se_construye():
    with pytest.raises(ValueError, match="regla"):
        Hallazgo(regla="", evidencia="algo", procedencia=_proc())


def test_un_hallazgo_completo_es_inmutable():
    h = Hallazgo(regla="no anualizar dos veces", evidencia="L1 20% baja", procedencia=_proc())
    with pytest.raises(Exception):
        h.regla = "otra"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_guard.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fdekit.guard'`

- [ ] **Step 3: Write minimal implementation**

Crear `src/fdekit/guard/hallazgo.py`:

```python
"""El dato que cruza las dos capas del harness.

Un Hallazgo es una afirmacion sobre el repo o sobre los datos. La procedencia
es obligatoria en el constructor y no por prolijidad: la memoria en prosa de
este proyecto ya mintio una vez -- el HANDOFF confiesa que sus hashes
posteriores a 17b6901 no sirven, y que los viejos siguen existiendo como
objetos huerfanos, asi que `git show` sobre ellos funciona y engana. Un tipo
que se puede construir sin commit reproduce esa falla en cada instancia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Procedencia:
    """De donde salio la afirmacion. Los tres campos son obligatorios."""

    commit: str
    fecha: date
    dueno: str

    def __post_init__(self) -> None:
        if not self.commit:
            raise ValueError("procedencia sin commit: una afirmacion sobre el repo sin hash que la ancle no es verificable")
        if not self.dueno:
            raise ValueError("procedencia sin dueno: la regla 1 del repo pide dueno para todo lo que va a una cola")


@dataclass(frozen=True)
class Hallazgo:
    """Una afirmacion con su evidencia y su procedencia.

    `familia` agrupa hallazgos del mismo tipo de error. Vacia significa sin
    clasificar, nunca "ninguna" -- es ausencia de dato, no evidencia.
    """

    regla: str
    evidencia: str
    procedencia: Procedencia
    familia: str = ""

    def __post_init__(self) -> None:
        if not self.regla:
            raise ValueError("hallazgo sin regla: no dice que es lo que no se puede volver a hacer")
```

Crear `src/fdekit/guard/__init__.py`:

```python
"""Contrato compartido entre la capa agentica y la capa de terreno.

Stdlib pura a proposito: este subpaquete viaja al notebook prestado de un
centro de distribucion, donde no hay GPU, no hay red y no hay permisos de
instalacion. Cualquier import pesado que entre aca rompe la regla 2 del repo.
"""

from .hallazgo import Hallazgo, Procedencia

__all__ = [
    "Hallazgo",
    "Procedencia",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_guard.py -q`
Expected: `4 passed`

Run: `python -m pytest -q`
Expected: `B + 4` passed

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/guard/ tests/test_guard.py
git commit -m "feat: el contrato del harness -- Hallazgo con procedencia obligatoria

Un tipo que se construye sin commit reproduce la falla que el HANDOFF ya
confiesa: hashes que git show muestra y que no estan en la rama."
```

---

## Tarea 2: `CoberturaGuardia` — la honestidad del harness

**Files:**
- Create: `src/fdekit/guard/cobertura.py`
- Modify: `src/fdekit/guard/__init__.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: nada de la Tarea 1.
- Produces: `CoberturaGuardia(familias_vigiladas: tuple[str, ...] = (), bugs_historicos: int = 17, bugs_atrapados: int = 0)` con `.is_complete` (siempre `False`) y `.nota() -> str`.

- [ ] **Step 1: Write the failing test**

Primero, extender el import del encabezado del archivo, que queda:

```python
from fdekit.guard import CoberturaGuardia, Hallazgo, Procedencia
```

Despues, agregar al final de `tests/test_guard.py`:

```python
# ------------------------------------------------------------- cobertura


def test_la_cobertura_nunca_dice_estar_completa():
    """Mismo motivo que Coverage en decide/query.py: heredar la interfaz de la
    promesa 'detecta los bugs' sin heredar la garantia, y callarlo, es el error
    mas grave que puede cometer este diseno."""
    c = CoberturaGuardia(familias_vigiladas=("anualizacion", "unidades"), bugs_atrapados=17)
    assert c.is_complete is False


def test_la_nota_nombra_primero_lo_que_NO_vigila():
    """El limite que hereda el oraculo elegido: sin invariantes externas, el
    harness solo aprende de fracasos que ya se manifestaron como test rojo. El
    bug que nunca falla no lo atrapa nadie, y eso va en la primera linea."""
    nota = CoberturaGuardia(familias_vigiladas=("anualizacion",)).nota()
    primera = nota.splitlines()[0]
    assert "no vigila" in primera
    assert "nunca fallo" in primera


def test_la_nota_publica_el_puntaje_crudo_contra_los_bugs_historicos():
    """El numero honesto no es 17/17: es cuantos de los 17 atrapa."""
    nota = CoberturaGuardia(familias_vigiladas=("a", "b"), bugs_atrapados=2).nota()
    assert "2 de 17" in nota


def test_sin_familias_la_nota_lo_dice_en_vez_de_quedar_muda():
    nota = CoberturaGuardia().nota()
    assert "ninguna familia" in nota
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_guard.py -q`
Expected: FAIL con `ImportError: cannot import name 'CoberturaGuardia'`

- [ ] **Step 3: Write minimal implementation**

Crear `src/fdekit/guard/cobertura.py`:

```python
"""La honestidad del harness, con el mismo contrato que Coverage.

`Coverage` (decide/query.py) existe porque Serena puede prometer que
find_referencing_symbols devuelve todo -- tiene un compilador abajo -- y
nosotros no. Un harness de self-healing hereda exactamente la misma clase de
promesa: "detecta los bugs". No los detecta todos y nunca va a poder.

El limite concreto de este harness no es un detalle de implementacion, es una
consecuencia del oraculo que se eligio: sin invariantes externas al test, solo
aprende de fracasos que YA se manifestaron como test rojo. El bug que no falla
-- que es el patron dominante de este repo, 17 casos documentados -- no genera
episodio. Por eso `nota()` lo dice en la PRIMERA linea y no en una nota al pie.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BUGS_HISTORICOS = 17
"""Los bugs de clase 'no falla, miente' documentados en HANDOFF.md. Es el
denominador del unico puntaje que hace falsable al harness."""


@dataclass(frozen=True)
class CoberturaGuardia:
    familias_vigiladas: tuple[str, ...] = ()
    bugs_historicos: int = BUGS_HISTORICOS
    bugs_atrapados: int = 0

    @property
    def is_complete(self) -> bool:
        return False  # nunca, y por eso se muestra

    def nota(self) -> str:
        cuales = ", ".join(self.familias_vigiladas) if self.familias_vigiladas else "ninguna familia todavia"
        return (
            "Este harness NO vigila el bug que nunca fallo: sin un test en rojo no hay "
            "episodio que capturar, y ese es el patron dominante del repo.\n"
            f"Vigila {cuales}.\n"
            f"Contra los bugs historicos atrapa {self.bugs_atrapados} de {self.bugs_historicos}."
        )
```

Modificar `src/fdekit/guard/__init__.py`:

```python
from .cobertura import BUGS_HISTORICOS, CoberturaGuardia
from .hallazgo import Hallazgo, Procedencia

__all__ = [
    "Hallazgo",
    "Procedencia",
    "CoberturaGuardia",
    "BUGS_HISTORICOS",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_guard.py -q`
Expected: `8 passed`

Run: `python -m pytest -q`
Expected: `B + 8` passed

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/guard/cobertura.py src/fdekit/guard/__init__.py tests/test_guard.py
git commit -m "feat: la cobertura del harness nombra primero lo que no vigila

is_complete es False siempre, igual que Coverage. Y la primera linea de
nota() dice el limite que hereda el oraculo: sin test rojo no hay episodio,
o sea que el bug que nunca falla no lo atrapa nadie."
```

---

## Tarea 3: `Guardia` y su registro

**Files:**
- Create: `src/fdekit/guard/guardia.py`
- Modify: `src/fdekit/guard/__init__.py`
- Test: `tests/test_guard.py`

**Interfaces:**
- Consumes: `Hallazgo` de la Tarea 1.
- Produces: `Guardia(nombre: str, motivo: str, hallazgo: Hallazgo, predicado: Callable[[object], bool])` y `evaluar(guardias, obj) -> list[Hallazgo]`. La capa 2 (Plan 2) consume ambos.

- [ ] **Step 1: Write the failing test**

Primero, extender el import del encabezado del archivo, que queda:

```python
from fdekit.guard import CoberturaGuardia, Guardia, Hallazgo, Procedencia, evaluar
```

Despues, agregar al final de `tests/test_guard.py`:

```python
# --------------------------------------------------------------- guardia


def _guardia(nombre="sin_anualizar_dos_veces", sano=True):
    return Guardia(
        nombre=nombre,
        motivo="anualizar en dos capas dejo L1 y L2 20% bajas, en silencio",
        hallazgo=Hallazgo(regla="una sola anualizacion", evidencia="residuo 250/300", procedencia=_proc()),
        predicado=lambda _obj: sano,
    )


def test_un_guardia_sin_motivo_no_se_construye():
    """Cada excepcion del guardia de convenciones lleva su motivo escrito al
    lado. Un guardia sin motivo es el que nadie sabe si puede borrar."""
    with pytest.raises(ValueError, match="motivo"):
        Guardia(
            nombre="x",
            motivo="",
            hallazgo=Hallazgo(regla="r", evidencia="e", procedencia=_proc()),
            predicado=lambda _obj: True,
        )


def test_evaluar_devuelve_hallazgos_no_booleanos():
    """Un booleano pierde la procedencia. Lo que sale de un guardia violado
    tiene que poder rastrearse hasta el commit que lo origino."""
    hallazgos = evaluar([_guardia(sano=False)], obj={"cualquiera": 1})
    assert len(hallazgos) == 1
    assert hallazgos[0].procedencia.commit == "abc1234"


def test_evaluar_no_devuelve_nada_cuando_todo_esta_sano():
    assert evaluar([_guardia(sano=True)], obj={}) == []


def test_un_guardia_que_revienta_no_tumba_la_evaluacion_entera():
    """Un guardia roto tiene que degradar como el store degrada por archivo:
    el que revienta se reporta como violado con el motivo, y los demas corren.
    Que un guardia nuevo apague a los otros es como se pierde el corpus."""

    def bomba(_obj):
        raise KeyError("campo que ya no existe")

    roto = Guardia(
        nombre="roto",
        motivo="quedo viejo",
        hallazgo=Hallazgo(regla="r", evidencia="e", procedencia=_proc()),
        predicado=bomba,
    )
    hallazgos = evaluar([roto, _guardia(sano=True)], obj={})
    assert len(hallazgos) == 1
    assert "reviento" in hallazgos[0].evidencia
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_guard.py -q`
Expected: FAIL con `ImportError: cannot import name 'Guardia'`

- [ ] **Step 3: Write minimal implementation**

Crear `src/fdekit/guard/guardia.py`:

```python
"""Un guardia es un predicado con su motivo escrito al lado.

El modelo es ARCHIVOS_CON_ACENTOS_A_PROPOSITO en tests/test_convenciones.py:
cada excepcion trae el porque, y por eso seis meses despues se puede decidir
si sigue valiendo. Un guardia sin motivo es el que nadie sabe si puede borrar,
y el que termina borrado el dia que molesta.

`evaluar` devuelve Hallazgos y no booleanos porque un booleano pierde la
procedencia: lo que sale de un guardia violado tiene que rastrearse hasta el
commit que lo origino.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .hallazgo import Hallazgo


@dataclass(frozen=True)
class Guardia:
    """`predicado` devuelve True cuando el objeto esta SANO."""

    nombre: str
    motivo: str
    hallazgo: Hallazgo
    predicado: Callable[[object], bool]

    def __post_init__(self) -> None:
        if not self.nombre:
            raise ValueError("guardia sin nombre")
        if not self.motivo:
            raise ValueError("guardia sin motivo: es el que nadie sabe si puede borrar")


def evaluar(guardias: Iterable[Guardia], obj: object) -> list[Hallazgo]:
    """Corre todos los guardias y devuelve los Hallazgos de los violados.

    Un guardia que revienta se reporta como violado en vez de tumbar la
    evaluacion. Es la misma degradacion por unidad que hace el store al leer:
    un archivo ilegible no puede apagar toda la fase 4.
    """
    fallas: list[Hallazgo] = []
    for g in guardias:
        try:
            sano = g.predicado(obj)
        except Exception as exc:  # noqa: BLE001 -- un guardia roto no apaga a los demas
            fallas.append(
                Hallazgo(
                    regla=g.hallazgo.regla,
                    evidencia=f"el guardia {g.nombre} reviento al evaluar: {exc!r}",
                    procedencia=g.hallazgo.procedencia,
                    familia=g.hallazgo.familia,
                )
            )
            continue
        if not sano:
            fallas.append(g.hallazgo)
    return fallas
```

Modificar `src/fdekit/guard/__init__.py` — agregar el import y las dos entradas de `__all__`:

```python
from .cobertura import BUGS_HISTORICOS, CoberturaGuardia
from .guardia import Guardia, evaluar
from .hallazgo import Hallazgo, Procedencia

__all__ = [
    "Hallazgo",
    "Procedencia",
    "CoberturaGuardia",
    "BUGS_HISTORICOS",
    "Guardia",
    "evaluar",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_guard.py -q`
Expected: `12 passed`

Run: `python -m pytest -q`
Expected: `B + 12` passed

- [ ] **Step 5: Commit**

```bash
git add src/fdekit/guard/guardia.py src/fdekit/guard/__init__.py tests/test_guard.py
git commit -m "feat: Guardia con su motivo al lado, y evaluar que degrada por guardia

evaluar devuelve Hallazgos y no booleanos: un booleano pierde la procedencia.
Un guardia que revienta se reporta violado en vez de apagar a los demas."
```

---

## Tarea 4: `Episodio` y el log append-only

**Files:**
- Create: `tools/harness/__init__.py`
- Create: `tools/harness/episodio.py`
- Test: `tests/test_harness_captura.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Episodio` frozen con campos `fecha, commit_antes, commit_despues, tests_que_fallaban: tuple[str, ...], archivos_tocados: tuple[str, ...], mensaje, estado`; `ESTADOS`; `leer(path) -> list[Episodio]`; `agregar(path, ep) -> None`; `marcar(path, indice, estado) -> None`.

**Nota:** `tools/` no está en el paquete, así que los tests lo importan agregando la raíz del repo al `sys.path` vía `conftest.py`. Eso se resuelve en el Step 3.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_harness_captura.py`:

```python
"""El log de evidencia del harness: append-only, como el event log del kit.

D3 de fundacion-huecos.md dice que el event log no pierde filas: gana una
columna. Lo mismo aca. Un episodio que no dio leccion se MARCA, no se borra --
un log de eventos al que se le sacan eventos es exactamente la mentira
silenciosa que la regla 3 prohibe.
"""

import json

import pytest

from tools.harness.episodio import Episodio, agregar, leer, marcar


def _ep(commit_antes="aaa", commit_despues="bbb", estado="abierto"):
    return Episodio(
        fecha="2026-08-02",
        commit_antes=commit_antes,
        commit_despues=commit_despues,
        tests_que_fallaban=("tests/test_value.py::test_anualizacion",),
        archivos_tocados=("src/fdekit/value/levers.py",),
        mensaje="fix: anualizar una sola vez",
        estado=estado,
    )


def test_agregar_y_leer_da_la_vuelta_completa(tmp_path):
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep())
    assert leer(p) == [_ep()]


def test_agregar_no_pisa_lo_anterior(tmp_path):
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep(commit_antes="uno"))
    agregar(p, _ep(commit_antes="dos"))
    assert [e.commit_antes for e in leer(p)] == ["uno", "dos"]


def test_marcar_cambia_el_estado_sin_borrar_la_fila(tmp_path):
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep())
    agregar(p, _ep(commit_antes="otro"))
    marcar(p, 0, "descartado")

    eps = leer(p)
    assert len(eps) == 2
    assert eps[0].estado == "descartado"
    assert eps[1].estado == "abierto"


def test_un_estado_desconocido_se_rechaza(tmp_path):
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep())
    with pytest.raises(ValueError, match="estado"):
        marcar(p, 0, "masomenos")


def test_una_linea_ilegible_no_tumba_la_lectura_entera(tmp_path):
    """Misma degradacion que el store: un archivo ilegible dice cual es y los
    demas se leen igual."""
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep())
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{esto no es json\n")
    agregar(p, _ep(commit_antes="tercero"))

    eps = leer(p)
    assert len(eps) == 2
    assert eps[1].commit_antes == "tercero"


def test_leer_un_archivo_que_no_existe_da_lista_vacia(tmp_path):
    assert leer(tmp_path / "no-existe.jsonl") == []


def test_lo_escrito_es_json_por_linea(tmp_path):
    """El formato tiene que poder leerse con herramientas de linea de comando
    sin el harness: si el harness se cae, la evidencia sigue siendo legible."""
    p = tmp_path / "evidencia.jsonl"
    agregar(p, _ep())
    fila = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert fila["commit_antes"] == "aaa"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_captura.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Write minimal implementation**

Agregar al principio de `tests/conftest.py` (antes de cualquier otra cosa):

```python
import sys
from pathlib import Path

# `tools/` no es un paquete instalado a proposito: no viaja al notebook del CD.
# Los tests lo importan desde la raiz del repo.
_RAIZ = Path(__file__).resolve().parents[1]
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))
```

Crear `tools/__init__.py` vacío y `tools/harness/__init__.py` vacío.

Crear `tools/harness/episodio.py`:

```python
"""El episodio: el par de arboles que el oraculo necesita para dar veredicto.

Un episodio se cierra cuando una corrida deja en verde tests que la corrida
anterior tenia en rojo. El par (commit_antes, commit_despues) es lo unico que
hace falta para reconstruir los dos arboles.

El log es append-only. Un episodio que no dio leccion se MARCA, no se borra.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

ESTADOS = ("abierto", "irreproducible", "descartado", "destilado")
"""abierto: sin procesar. irreproducible: el arbol estaba sucio y no hay HEAD
que lo reproduzca. descartado: la cosecha lo miro y no dio leccion.
destilado: produjo un guardia."""


@dataclass(frozen=True)
class Episodio:
    fecha: str
    commit_antes: str
    commit_despues: str
    tests_que_fallaban: tuple[str, ...]
    archivos_tocados: tuple[str, ...]
    mensaje: str
    estado: str = "abierto"


def _a_episodio(fila: dict) -> Episodio:
    return Episodio(
        fecha=fila["fecha"],
        commit_antes=fila["commit_antes"],
        commit_despues=fila["commit_despues"],
        tests_que_fallaban=tuple(fila.get("tests_que_fallaban", ())),
        archivos_tocados=tuple(fila.get("archivos_tocados", ())),
        mensaje=fila.get("mensaje", ""),
        estado=fila.get("estado", "abierto"),
    )


def leer(path: Path) -> list[Episodio]:
    """Lee el log. Una linea ilegible se saltea sin tumbar las demas."""
    p = Path(path)
    if not p.exists():
        return []
    eps: list[Episodio] = []
    for linea in p.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            eps.append(_a_episodio(json.loads(linea)))
        except (ValueError, KeyError):
            continue
    return eps


def agregar(path: Path, ep: Episodio) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(ep), ensure_ascii=False) + "\n")


def marcar(path: Path, indice: int, estado: str) -> None:
    """Cambia el estado de un episodio reescribiendo el archivo entero.

    Reescribe en vez de agregar porque el estado es del episodio, no un evento
    nuevo. Las filas ilegibles se pierden en la reescritura y eso es aceptable:
    ya eran ilegibles.
    """
    if estado not in ESTADOS:
        raise ValueError(f"estado desconocido: {estado}. Opciones: {', '.join(ESTADOS)}")
    eps = leer(path)
    eps[indice] = replace(eps[indice], estado=estado)
    p = Path(path)
    p.write_text(
        "".join(json.dumps(asdict(e), ensure_ascii=False) + "\n" for e in eps),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_captura.py -q`
Expected: `7 passed`

Run: `python -m pytest -q`
Expected: `B + 19` passed

- [ ] **Step 5: Commit**

```bash
git add tools/ tests/conftest.py tests/test_harness_captura.py
git commit -m "feat: el log de evidencia del harness, append-only

Un episodio que no dio leccion se marca, no se borra: un log de eventos al
que se le sacan eventos es la mentira silenciosa que la regla 3 prohibe."
```

---

## Tarea 5: La captura — detección rojo→verde, pura

**Files:**
- Create: `tools/harness/captura.py`
- Test: `tests/test_harness_captura.py` (agregar)

**Interfaces:**
- Consumes: `Episodio` de la Tarea 4.
- Produces: `registrar_corrida(estado_path: Path, head: str, fallidos: Iterable[str], archivos_tocados: Iterable[str], mensaje: str, today: str, arbol_limpio: bool = True) -> Episodio | None`. Devuelve el `Episodio` cuando detecta la transición, `None` cuando no.

- [ ] **Step 1: Write the failing test**

Primero, agregar al encabezado del archivo, junto al import que ya esta:

```python
from tools.harness.captura import registrar_corrida
```

Despues, agregar al final de `tests/test_harness_captura.py`:

```python
# ---------------------------------------------------------------- captura


def test_una_corrida_verde_sola_no_es_episodio(tmp_path):
    """Sin una corrida roja previa no hay par de arboles que comparar."""
    est = tmp_path / "ultima.json"
    assert registrar_corrida(est, head="aaa", fallidos=[], archivos_tocados=[], mensaje="", today="2026-08-02") is None


def test_rojo_y_despues_verde_cierra_el_episodio(tmp_path):
    est = tmp_path / "ultima.json"
    registrar_corrida(est, head="aaa", fallidos=["t::uno"], archivos_tocados=[], mensaje="", today="2026-08-02")
    ep = registrar_corrida(
        est, head="bbb", fallidos=[], archivos_tocados=["src/x.py"], mensaje="fix: x", today="2026-08-02"
    )

    assert ep is not None
    assert ep.commit_antes == "aaa"
    assert ep.commit_despues == "bbb"
    assert ep.tests_que_fallaban == ("t::uno",)


def test_dos_rojas_seguidas_no_cierran_nada(tmp_path):
    est = tmp_path / "ultima.json"
    registrar_corrida(est, head="aaa", fallidos=["t::uno"], archivos_tocados=[], mensaje="", today="2026-08-02")
    ep = registrar_corrida(est, head="bbb", fallidos=["t::uno"], archivos_tocados=[], mensaje="", today="2026-08-02")
    assert ep is None


def test_un_test_que_sigue_rojo_no_cuenta_como_curado(tmp_path):
    """Solo cuentan los que pasaron de rojo a verde. Si quedan rojos otros, el
    episodio se cierra igual sobre los que si se curaron."""
    est = tmp_path / "ultima.json"
    registrar_corrida(est, head="aaa", fallidos=["t::uno", "t::dos"], archivos_tocados=[], mensaje="", today="2026-08-02")
    ep = registrar_corrida(est, head="bbb", fallidos=["t::dos"], archivos_tocados=[], mensaje="", today="2026-08-02")

    assert ep is not None
    assert ep.tests_que_fallaban == ("t::uno",)


def test_un_arbol_sucio_marca_el_episodio_irreproducible(tmp_path):
    """Sin HEAD que reproduzca el arbol rojo no hay dos arboles que comparar.
    No se intenta reconstruir desde un stash."""
    est = tmp_path / "ultima.json"
    registrar_corrida(
        est, head="aaa", fallidos=["t::uno"], archivos_tocados=[], mensaje="", today="2026-08-02", arbol_limpio=False
    )
    ep = registrar_corrida(est, head="bbb", fallidos=[], archivos_tocados=[], mensaje="", today="2026-08-02")

    assert ep is not None
    assert ep.estado == "irreproducible"


def test_un_estado_ilegible_no_revienta_la_captura(tmp_path):
    """La captura corre en un hook: si revienta, molesta en cada corrida. Falla
    hacia el lado seguro, que es no registrar nada."""
    est = tmp_path / "ultima.json"
    est.write_text("{roto", encoding="utf-8")
    assert registrar_corrida(est, head="bbb", fallidos=[], archivos_tocados=[], mensaje="", today="2026-08-02") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_captura.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.captura'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/captura.py`:

```python
"""La mitad del harness que corre sola, y por eso solo observa.

La frontera del diseno: capturar nunca miente, actuar si puede. Este modulo no
escribe codigo, no interpreta y no clasifica. Escribe un renglon cuando una
corrida deja en verde tests que la anterior tenia en rojo.

Es una funcion pura sobre el estado en disco: recibe el resultado de la corrida
como argumento en vez de correr pytest adentro. Eso la vuelve testeable sin
subprocess y sin git, que es la unica forma de que el hook sea confiable.

Si algo sale mal, devuelve None. Un hook que revienta molesta en cada corrida y
termina desactivado; perder un episodio no cuesta nada.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .episodio import Episodio


def _ultima(path: Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def registrar_corrida(
    estado_path: Path,
    head: str,
    fallidos: Iterable[str],
    archivos_tocados: Iterable[str],
    mensaje: str,
    today: str,
    arbol_limpio: bool = True,
) -> Episodio | None:
    """Guarda esta corrida y devuelve un Episodio si cerro uno.

    `today` es argumento y no `date.today()`: regla 4 del repo.
    """
    fallidos = tuple(fallidos)
    previa = _ultima(estado_path)

    ep: Episodio | None = None
    if previa is not None:
        curados = tuple(t for t in previa.get("fallidos", ()) if t not in fallidos)
        if curados:
            ep = Episodio(
                fecha=today,
                commit_antes=previa.get("head", ""),
                commit_despues=head,
                tests_que_fallaban=curados,
                archivos_tocados=tuple(archivos_tocados),
                mensaje=mensaje,
                estado="abierto" if previa.get("arbol_limpio", True) else "irreproducible",
            )

    p = Path(estado_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"head": head, "fallidos": list(fallidos), "arbol_limpio": arbol_limpio}, ensure_ascii=False),
        encoding="utf-8",
    )
    return ep
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_captura.py -q`
Expected: `13 passed`

Run: `python -m pytest -q`
Expected: `B + 25` passed

- [ ] **Step 5: Commit**

```bash
git add tools/harness/captura.py tests/test_harness_captura.py
git commit -m "feat: la captura del harness, pura y que falla hacia el lado seguro

Recibe el resultado de la corrida como argumento en vez de correr pytest
adentro: testeable sin subprocess. Si algo sale mal devuelve None -- un hook
que revienta termina desactivado, y perder un episodio no cuesta nada."
```

---

## Tarea 6: Las fronteras de los roles

**Files:**
- Create: `tools/harness/roles.py`
- Test: `tests/test_harness_oraculo.py`

**Interfaces:**
- Consumes: nada.
- Produces: `FRONTERAS: dict[str, tuple[str, ...]]`, `viola_frontera(rol: str, archivos: Iterable[str]) -> list[str]`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_harness_oraculo.py`:

```python
"""El oraculo y las fronteras: la contencion mecanica del harness.

La autoridad del harness es amplia -- escribe tests y arregla src -- asi que la
contencion no puede estar en el permiso. Esta en dos lugares y los dos son
codigo: las fronteras se verifican sobre el diff, y el veredicto se decide
corriendo la suite en dos arboles.
"""

import pytest

from tools.harness.roles import viola_frontera


def test_el_testigo_no_puede_tocar_src():
    """El que escribe el test no puede escribir el arreglo. Si pudiera, verde
    solo probaria que los dos comparten el mismo error."""
    assert viola_frontera("testigo", ["tests/test_x.py", "src/fdekit/value/levers.py"]) == [
        "src/fdekit/value/levers.py"
    ]


def test_el_reparador_no_puede_tocar_tests():
    assert viola_frontera("reparador", ["src/fdekit/x.py", "tests/test_x.py"]) == ["tests/test_x.py"]


def test_un_diff_que_respeta_la_frontera_no_da_violaciones():
    assert viola_frontera("testigo", ["tests/test_x.py", "tests/guards/test_anualizacion.py"]) == []


def test_un_rol_desconocido_se_rechaza():
    """Un rol sin frontera declarada seria un rol sin frontera."""
    with pytest.raises(ValueError, match="rol"):
        viola_frontera("cualquiera", ["src/x.py"])


def test_un_archivo_fuera_de_src_y_tests_tambien_viola():
    """El harness no toca pyproject, ni docs, ni tools. Una regla que solo
    prohibe la carpeta del otro rol deja abierto todo lo demas."""
    assert viola_frontera("reparador", ["pyproject.toml"]) == ["pyproject.toml"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_oraculo.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.roles'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/roles.py`:

```python
"""Las fronteras de los dos roles de la cosecha, verificadas sobre el diff.

Un rol que puede violar su prohibicion no tiene prohibicion, tiene una
sugerencia. Por eso esto no se le pide al agente: se calcula sobre los archivos
que efectivamente toco.

La frontera es una lista de prefijos PERMITIDOS, no de prohibidos. Prohibir la
carpeta del otro rol dejaria abierto todo lo demas -- pyproject, docs, tools --
y el harness no tiene nada que hacer ahi.
"""

from __future__ import annotations

from typing import Iterable

FRONTERAS: dict[str, tuple[str, ...]] = {
    "testigo": ("tests/",),
    "reparador": ("src/",),
}


def viola_frontera(rol: str, archivos: Iterable[str]) -> list[str]:
    """Devuelve los archivos que el rol no tenia permitido tocar."""
    if rol not in FRONTERAS:
        raise ValueError(f"rol desconocido: {rol}. Opciones: {', '.join(FRONTERAS)}")
    permitidos = FRONTERAS[rol]
    return [a for a in archivos if not a.startswith(permitidos)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_oraculo.py -q`
Expected: `5 passed`

Run: `python -m pytest -q`
Expected: `B + 30` passed

- [ ] **Step 5: Commit**

```bash
git add tools/harness/roles.py tests/test_harness_oraculo.py
git commit -m "feat: las fronteras de los roles se calculan sobre el diff

Lista de prefijos permitidos, no de prohibidos: prohibir solo la carpeta del
otro rol dejaria abierto pyproject, docs y tools."
```

---

## Tarea 7: El oráculo — veredicto sobre dos árboles

**Files:**
- Create: `tools/harness/oraculo.py`
- Test: `tests/test_harness_oraculo.py` (agregar)

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces: `Veredicto(acepta: bool, motivo: str, fallo_en_antes: bool, paso_en_despues: bool, regresiones: tuple[str, ...])` y `veredicto(test_nuevo: str, correr: Callable[[str], set[str]], commit_antes: str, commit_despues: str) -> Veredicto`.

`correr(commit)` devuelve el conjunto de ids de tests que **fallan** en ese árbol. Inyectarlo es lo que permite testear el oráculo sin git.

- [ ] **Step 1: Write the failing test**

Primero, agregar al encabezado del archivo, junto al import que ya esta:

```python
from tools.harness.oraculo import veredicto
```

Despues, agregar al final de `tests/test_harness_oraculo.py`:

```python
# ---------------------------------------------------------------- oraculo


def _correr(mapa):
    """Simula la suite: devuelve los tests que fallan en cada arbol."""
    return lambda commit: set(mapa[commit])


def test_un_test_que_falla_antes_y_pasa_despues_se_acepta():
    v = veredicto(
        test_nuevo="tests/guards/test_anual.py::test_una_sola_vez",
        correr=_correr({"antes": ["tests/guards/test_anual.py::test_una_sola_vez"], "despues": []}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is True


def test_un_test_vacuo_se_rechaza():
    """El chequeo que hace que esto no sea un teatro: un test que pasa en el
    arbol donde el bug TODAVIA EXISTE no prueba nada. Verde no lo distingue de
    un test que prueba algo; correrlo contra el arbol viejo si."""
    v = veredicto(
        test_nuevo="tests/guards/test_vacuo.py::test_nada",
        correr=_correr({"antes": [], "despues": []}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.fallo_en_antes is False
    assert "vacuo" in v.motivo


def test_un_test_que_sigue_fallando_despues_se_rechaza():
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr({"antes": ["tests/guards/test_x.py::test_x"], "despues": ["tests/guards/test_x.py::test_x"]}),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.paso_en_despues is False


def test_una_regresion_voltea_el_episodio_aunque_el_test_nuevo_este_verde():
    """No basta con que el numero nuevo este bien: ninguno de los viejos puede
    haber empeorado. La suite completa corre en los dos arboles."""
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr(
            {
                "antes": ["tests/guards/test_x.py::test_x"],
                "despues": ["tests/test_value.py::test_que_pasaba_antes"],
            }
        ),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is False
    assert v.regresiones == ("tests/test_value.py::test_que_pasaba_antes",)
    assert "regres" in v.motivo


def test_un_test_que_ya_fallaba_por_otro_motivo_no_cuenta_como_regresion():
    """Un test roto de antes sigue roto y no es culpa de este episodio. La
    semantica es 'no empeorar', igual que save() en el store."""
    v = veredicto(
        test_nuevo="tests/guards/test_x.py::test_x",
        correr=_correr(
            {
                "antes": ["tests/guards/test_x.py::test_x", "tests/test_viejo.py::test_roto"],
                "despues": ["tests/test_viejo.py::test_roto"],
            }
        ),
        commit_antes="antes",
        commit_despues="despues",
    )
    assert v.acepta is True
    assert v.regresiones == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_oraculo.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.oraculo'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/oraculo.py`:

```python
"""El veredicto: dos arboles, la suite completa, ninguna afirmacion.

Un test verde no prueba nada cuando el mismo proceso escribio el test y el
arreglo: prueba que los dos comparten el error. Lo que si prueba algo es correr
el test contra el arbol donde el bug TODAVIA EXISTE. Si ahi pasa, el test es
vacuo y el episodio se voltea entero.

Y no alcanza con el test nuevo: la suite completa corre en los dos arboles,
porque el modo de falla de este repo es el numero plausible, y un arreglo que
cura un numero y rompe otro se ve solo mirando los demas.

La semantica de regresion es 'no empeorar', la misma que save() en el store: un
test que ya fallaba antes sigue fallando y no es culpa de este episodio.

`correr` se recibe como argumento a proposito: el oraculo es una decision, no
un ejecutor. Quien lo llama decide si corre pytest de verdad o simula.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Veredicto:
    acepta: bool
    motivo: str
    fallo_en_antes: bool
    paso_en_despues: bool
    regresiones: tuple[str, ...]


def veredicto(
    test_nuevo: str,
    correr: Callable[[str], set[str]],
    commit_antes: str,
    commit_despues: str,
) -> Veredicto:
    """Acepta el episodio solo si el test nuevo fallaba antes, pasa ahora, y
    ningun test que pasaba antes empeoro."""
    fallan_antes = set(correr(commit_antes))
    fallan_despues = set(correr(commit_despues))

    fallo_en_antes = test_nuevo in fallan_antes
    paso_en_despues = test_nuevo not in fallan_despues
    regresiones = tuple(sorted(fallan_despues - fallan_antes))

    if not fallo_en_antes:
        motivo = (
            f"test vacuo: {test_nuevo} pasa en {commit_antes}, donde el bug todavia existe. "
            "Un test que no distingue el arbol roto del arreglado no prueba nada."
        )
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    if not paso_en_despues:
        motivo = f"el test {test_nuevo} sigue fallando en {commit_despues}: el arreglo no lo cura"
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    if regresiones:
        motivo = (
            f"regresiones en {commit_despues}: {', '.join(regresiones)}. "
            "El test nuevo esta verde pero la suite empeoro."
        )
        return Veredicto(False, motivo, fallo_en_antes, paso_en_despues, regresiones)

    return Veredicto(True, "", fallo_en_antes, paso_en_despues, ())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_oraculo.py -q`
Expected: `10 passed`

Run: `python -m pytest -q`
Expected: `B + 35` passed

- [ ] **Step 5: Commit**

```bash
git add tools/harness/oraculo.py tests/test_harness_oraculo.py
git commit -m "feat: el oraculo corre la suite en dos arboles y rechaza el test vacuo

Un test que pasa en el arbol donde el bug todavia existe no prueba nada.
Y la regresion se mide con semantica de no empeorar, igual que save()."
```

---

## Tarea 8: El índice derivado

**Files:**
- Create: `tools/harness/indice.py`
- Test: `tests/test_harness_cosecha.py`

**Interfaces:**
- Consumes: nada.
- Produces: `indice(guards_dir: Path) -> str`.

Cada archivo de `tests/guards/` declara su lección en un dict de módulo `LECCION` con claves `regla`, `familia`, `commit`, `fecha`, `dueno`. El índice se arma leyendo esos dicts sin importar los módulos (parse de texto), porque importar un guardia roto tumbaría la generación del índice.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_harness_cosecha.py`:

```python
"""El indice legible se DERIVA del corpus ejecutable, nunca al reves.

Misma decision que estado_captura (D5 de fundacion-huecos.md): un estado que
alguien tiene que acordarse de escribir es un estado que va a estar mal. La
memoria del proyecto ya mintio una vez por escribirse a mano.
"""

from pathlib import Path

from tools.harness.indice import indice

_GUARDIA = '''"""Guardia de ejemplo."""

LECCION = {
    "regla": "una sola anualizacion, y va donde esta operating_days",
    "familia": "anualizacion",
    "commit": "b2267bd",
    "fecha": "2026-08-02",
    "dueno": "stipi",
}


def test_no_se_anualiza_dos_veces():
    assert True
'''


def _guards(tmp_path: Path, **archivos) -> Path:
    d = tmp_path / "guards"
    d.mkdir()
    for nombre, texto in archivos.items():
        (d / nombre).write_text(texto, encoding="utf-8")
    return d


def test_el_indice_lista_la_leccion_con_su_procedencia(tmp_path):
    md = indice(_guards(tmp_path, test_anualizacion=_GUARDIA))
    assert "una sola anualizacion" in md
    assert "b2267bd" in md
    assert "anualizacion" in md


def test_el_indice_avisa_que_es_generado(tmp_path):
    """Si no lo dice, alguien lo edita a mano y la proxima regeneracion se lo
    come sin avisar."""
    md = indice(_guards(tmp_path, test_anualizacion=_GUARDIA))
    assert "generado" in md.lower()


def test_un_guardia_sin_LECCION_se_lista_como_sin_procedencia(tmp_path):
    """No se saltea en silencio: un guardia que no declara su leccion es
    exactamente lo que hay que ver para arreglarlo."""
    md = indice(_guards(tmp_path, test_mudo='def test_x():\n    assert True\n'))
    assert "test_mudo" in md
    assert "sin procedencia" in md


def test_un_guardia_roto_no_impide_generar_el_indice(tmp_path):
    """El indice se arma parseando texto, no importando modulos: un guardia con
    un SyntaxError no puede apagar la generacion entera."""
    md = indice(_guards(tmp_path, test_ok=_GUARDIA, test_roto="def test_x(:\n"))
    assert "una sola anualizacion" in md
    assert "test_roto" in md


def test_sin_guardias_el_indice_lo_dice_en_vez_de_quedar_vacio(tmp_path):
    md = indice(_guards(tmp_path))
    assert "todavia no hay guardias" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_cosecha.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.indice'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/indice.py`:

```python
"""Genera el indice legible del corpus de guardias.

El corpus ejecutable es la memoria; esto es solo una vista. Se arma parseando
el texto de cada guardia con ast en vez de importarlo: un guardia con un
SyntaxError, o uno que hace algo al importarse, no puede apagar la generacion
del indice de todos los demas.
"""

from __future__ import annotations

import ast
from pathlib import Path

ENCABEZADO = (
    "# Lecciones del harness\n\n"
    "> Archivo GENERADO por `tools/harness/indice.py` desde `tests/guards/`.\n"
    "> No editar a mano: la proxima regeneracion se come los cambios.\n"
    "> La memoria real son los tests; esto es una vista.\n\n"
)


def _leccion(texto: str) -> dict | None:
    """Extrae el dict LECCION de nivel de modulo, sin importar el modulo."""
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return None
    for nodo in arbol.body:
        if not isinstance(nodo, ast.Assign):
            continue
        for destino in nodo.targets:
            if isinstance(destino, ast.Name) and destino.id == "LECCION":
                try:
                    valor = ast.literal_eval(nodo.value)
                except ValueError:
                    return None
                return valor if isinstance(valor, dict) else None
    return None


def indice(guards_dir: Path) -> str:
    d = Path(guards_dir)
    archivos = sorted(p for p in d.glob("*.py") if p.name != "__init__.py")
    if not archivos:
        return ENCABEZADO + "Todavia no hay guardias en el corpus.\n"

    filas = ["| guardia | familia | regla | commit | fecha | dueno |", "|---|---|---|---|---|---|"]
    for p in archivos:
        lec = _leccion(p.read_text(encoding="utf-8"))
        if lec is None:
            filas.append(f"| `{p.stem}` | - | **sin procedencia** - no declara `LECCION` | - | - | - |")
            continue
        filas.append(
            f"| `{p.stem}` | {lec.get('familia', '-')} | {lec.get('regla', '-')} | "
            f"`{lec.get('commit', '-')}` | {lec.get('fecha', '-')} | {lec.get('dueno', '-')} |"
        )
    return ENCABEZADO + "\n".join(filas) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_cosecha.py -q`
Expected: `5 passed`

Run: `python -m pytest -q`
Expected: `B + 40` passed

- [ ] **Step 5: Commit**

```bash
git add tools/harness/indice.py tests/test_harness_cosecha.py
git commit -m "feat: el indice de lecciones se deriva del corpus ejecutable

Se arma parseando con ast, no importando: un guardia con SyntaxError no
puede apagar la generacion del indice de todos los demas."
```

---

## Tarea 9: El guardia de convenciones cubre `tests/guards/`

**Files:**
- Create: `tests/guards/__init__.py`
- Modify: `tests/test_convenciones.py`
- Test: `tests/test_convenciones.py`

**Interfaces:**
- Consumes: nada.
- Produces: nada que otras tareas usen.

**Contexto:** el guardia hoy recorre los `.py` versionados bajo `src/fdekit/` y `tests/`. `tests/guards/` cae bajo `tests/`, así que ya estaría cubierto — **pero hay que verificarlo con un test en vez de asumirlo**, porque ahí va a escribir un agente y es exactamente donde una tilde se cuela sin que nadie mire.

**La función que arma la lista es `_get_py_files_to_check()`** (`tests/test_convenciones.py:55`). Filtra `git ls-files *.py` por los prefijos `src/fdekit/` y `tests/`, con un fallback a glob si git no está. Como la ruta principal usa `git ls-files`, **el archivo tiene que estar versionado** para quedar cubierto — por eso el Step 4 hace `git add` antes de correr.

- [ ] **Step 1: Verificar el punto de partida**

Run: `python -m pytest tests/test_convenciones.py -q`
Expected: pasa

- [ ] **Step 2: Write the failing test**

Agregar al final de `tests/test_convenciones.py`:

```python
def test_el_guardia_cubre_el_corpus_de_guardias_del_harness():
    """tests/guards/ es donde escribe un agente. Si el guardia no lo cubre, una
    tilde entra ahi y nadie la mira hasta que el archivo se abre en un notebook
    prestado con otra codificacion.

    El guardia filtra `git ls-files` por prefijo, asi que esto tambien verifica
    que el corpus este VERSIONADO: un tests/guards/ sin git add no lo cubre
    nadie.
    """
    cubiertos = [str(p).replace("\\", "/") for p in _get_py_files_to_check()]
    assert any("tests/guards/" in c for c in cubiertos), (
        "tests/guards/ no esta cubierto por el guardia de convenciones"
    )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_convenciones.py -q`
Expected: FAIL — `tests/guards/` no existe todavía, así que ningún archivo matchea.

- [ ] **Step 4: Crear el corpus vacío y verificar**

Crear `tests/guards/__init__.py`:

```python
"""Corpus de guardias del harness: la memoria ejecutable.

Un archivo por leccion, nombrado por la familia de error. Cada uno declara un
dict LECCION de nivel de modulo con regla, familia, commit, fecha y dueno, que
es lo que tools/harness/indice.py lee para generar el indice legible.

Un guardia solo se borra CON MOTIVO ESCRITO, y el borrado es en si mismo un
episodio de evidencia. Agregar y quitar cuestan lo mismo en trazabilidad: si
no, el corpus se erosiona en silencio.
"""
```

```bash
git add tests/guards/__init__.py
```

Run: `python -m pytest tests/test_convenciones.py -q`
Expected: pasa

Run: `python -m pytest -q`
Expected: `B + 41` passed

- [ ] **Step 5: Commit**

```bash
git add tests/guards/ tests/test_convenciones.py
git commit -m "feat: el corpus de guardias existe y el guardia de convenciones lo cubre

tests/guards/ es donde escribe un agente: es justo donde una tilde se cuela
sin que nadie mire."
```

---

## Tarea 10: La cosecha — orquestador sobre worktree aislado

**Files:**
- Create: `tools/harness/cosecha.py`
- Test: `tests/test_harness_cosecha.py` (agregar)

**Interfaces:**
- Consumes: `Episodio`/`leer`/`marcar` (Tarea 4), `veredicto` (Tarea 7), `viola_frontera` (Tarea 6), `CoberturaGuardia` (Tarea 2).
- Produces: `Resultado(guardias: tuple[str, ...], descartados: tuple[tuple[str, str], ...], cobertura: CoberturaGuardia)` y `cosechar(episodios, destilar, correr, today) -> Resultado`.

`destilar(ep) -> tuple[str, str, str, list[str]] | None` devuelve `(nombre_del_guardia, familia, test_id, archivos_tocados)` o `None` si el episodio no da lección.

**El `familia` va separado del `nombre` a proposito.** El nombre identifica un guardia (`test_no_anualiza_dos_veces`); la familia agrupa la clase de error (`anualizacion`). `CoberturaGuardia.familias_vigiladas` publica familias, asi que llenarla con nombres seria un campo que dice una cosa y contiene otra — la clase de bug que este repo tiene documentada 17 veces. Se inyecta: es el único punto agéntico, y aislarlo detrás de un callable es lo que permite testear la orquestación entera sin gastar un token.

- [ ] **Step 1: Write the failing test**

Primero, agregar al encabezado del archivo, junto al import que ya esta:

```python
from tools.harness.cosecha import cosechar
from tools.harness.episodio import Episodio
```

Despues, agregar al final de `tests/test_harness_cosecha.py`:

```python
# ---------------------------------------------------------------- cosecha


def _ep(commit_antes="antes", commit_despues="despues", estado="abierto"):
    return Episodio(
        fecha="2026-08-02",
        commit_antes=commit_antes,
        commit_despues=commit_despues,
        tests_que_fallaban=("t::uno",),
        archivos_tocados=("src/fdekit/x.py",),
        mensaje="fix: x",
        estado=estado,
    )


def _correr_ok(commit):
    return {"tests/guards/test_g.py::test_g"} if commit == "antes" else set()


def _destilar_ok(_ep):
    return ("test_g", "anualizacion", "tests/guards/test_g.py::test_g", ["tests/guards/test_g.py"])


def test_una_cosecha_sin_leccion_devuelve_cero_guardias():
    """Tiene que poder devolver vacio, y es un resultado BUENO. Es agenda()
    otra vez: la operacion de mayor retorno es la que puede decir 'proponer
    cancelar'. Una cosecha que siempre produce algo produce ruido."""
    r = cosechar([_ep()], destilar=lambda _e: None, correr=_correr_ok, today="2026-08-02")
    assert r.guardias == ()
    assert r.descartados[0][1] != ""


def test_un_episodio_que_pasa_el_oraculo_produce_un_guardia():
    r = cosechar([_ep()], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.guardias == ("test_g",)


def test_un_test_vacuo_voltea_el_episodio():
    r = cosechar([_ep()], destilar=_destilar_ok, correr=lambda _c: set(), today="2026-08-02")
    assert r.guardias == ()
    assert "vacuo" in r.descartados[0][1]


def test_un_testigo_que_toca_src_voltea_el_episodio():
    """La prohibicion se verifica sobre los archivos que efectivamente toco."""

    def destilar_invasor(_ep):
        return (
            "test_g",
            "anualizacion",
            "tests/guards/test_g.py::test_g",
            ["tests/guards/test_g.py", "src/fdekit/x.py"],
        )

    r = cosechar([_ep()], destilar=destilar_invasor, correr=_correr_ok, today="2026-08-02")
    assert r.guardias == ()
    assert "frontera" in r.descartados[0][1]


def test_un_episodio_irreproducible_no_se_procesa():
    r = cosechar([_ep(estado="irreproducible")], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.guardias == ()
    assert "irreproducible" in r.descartados[0][1]


def test_la_cobertura_del_resultado_nunca_dice_estar_completa():
    r = cosechar([_ep()], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.cobertura.is_complete is False
    assert "no vigila" in r.cobertura.nota().splitlines()[0]
    # familias, no nombres: el campo tiene que contener lo que su nombre dice.
    assert r.cobertura.familias_vigiladas == ("anualizacion",)


def test_los_descartados_dicen_por_que_uno_por_uno():
    """Una exclusion silenciosa es la misma mentira que un hueco."""
    r = cosechar(
        [_ep(commit_antes="a"), _ep(commit_antes="b", estado="irreproducible")],
        destilar=lambda _e: None,
        correr=_correr_ok,
        today="2026-08-02",
    )
    assert len(r.descartados) == 2
    assert all(motivo for _id, motivo in r.descartados)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_cosecha.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.cosecha'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/cosecha.py`:

```python
"""La orquestacion de la cosecha.

Es la mitad del harness que ACTUA, y por eso corre a pedido y en worktree
aislado: el arbol de trabajo no se toca nunca, asi que las sesiones
concurrentes -- que en este repo ya revirtieron ediciones dos veces en una
tarde -- dejan de importar.

`destilar` se inyecta porque es el UNICO punto agentico de todo el modulo.
Aislarlo detras de un callable es lo que permite testear la orquestacion entera
sin gastar un token, y es tambien lo que deja la decision en codigo: el agente
propone un guardia, el oraculo y las fronteras deciden si entra.

La cosecha puede devolver CERO guardias y eso es un resultado bueno. Una
cosecha que siempre produce algo esta produciendo ruido para justificarse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from fdekit.guard import CoberturaGuardia

from .episodio import Episodio
from .oraculo import veredicto
from .roles import viola_frontera

Destilador = Callable[[Episodio], "tuple[str, str, str, list[str]] | None"]
"""Devuelve (nombre_del_guardia, familia, test_id, archivos_tocados) o None.

La familia va separada del nombre porque son cosas distintas: el nombre
identifica un guardia, la familia agrupa la clase de error. CoberturaGuardia
publica familias, y un campo que dice una cosa y contiene otra es la clase de
bug que este repo tiene documentada 17 veces."""


@dataclass(frozen=True)
class Resultado:
    guardias: tuple[str, ...]
    descartados: tuple[tuple[str, str], ...]
    cobertura: CoberturaGuardia


def _id(ep: Episodio) -> str:
    return f"{ep.commit_antes[:7]}..{ep.commit_despues[:7]}"


def cosechar(
    episodios: Iterable[Episodio],
    destilar: Destilador,
    correr: Callable[[str], set[str]],
    today: str,
) -> Resultado:
    """Procesa los episodios y devuelve los guardias que sobrevivieron.

    `today` es argumento: regla 4 del repo.
    """
    guardias: list[str] = []
    descartados: list[tuple[str, str]] = []
    familias: list[str] = []

    for ep in episodios:
        if ep.estado != "abierto":
            descartados.append((_id(ep), f"estado {ep.estado}: no se procesa"))
            continue

        propuesta = destilar(ep)
        if propuesta is None:
            descartados.append((_id(ep), "sin leccion: el episodio no generaliza a ninguna regla"))
            continue

        nombre, familia, test_id, tocados = propuesta

        invadidos = viola_frontera("testigo", tocados)
        if invadidos:
            descartados.append((_id(ep), f"frontera violada por el testigo: {', '.join(invadidos)}"))
            continue

        v = veredicto(test_id, correr, ep.commit_antes, ep.commit_despues)
        if not v.acepta:
            descartados.append((_id(ep), v.motivo))
            continue

        guardias.append(nombre)
        familias.append(familia)

    return Resultado(
        guardias=tuple(guardias),
        descartados=tuple(descartados),
        cobertura=CoberturaGuardia(familias_vigiladas=tuple(familias)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_cosecha.py -q`
Expected: `12 passed`

Run: `python -m pytest -q`
Expected: `B + 48` passed

- [ ] **Step 5: Commit**

```bash
git add tools/harness/cosecha.py tests/test_harness_cosecha.py
git commit -m "feat: la cosecha orquesta, y el punto agentico va inyectado

destilar es el unico punto agentico: aislarlo detras de un callable deja la
decision en codigo -- el agente propone, el oraculo y las fronteras deciden.
La cosecha puede devolver cero guardias y eso es un resultado bueno."
```

---

## Tarea 11: El test que falsifica el harness

**Files:**
- Create: `tools/harness/historia.py`
- Create: `tests/test_harness_falsificacion.py`
- Modify: `pyproject.toml:39-40`

**Interfaces:**
- Consumes: `Episodio` (Tarea 4).
- Produces: `episodios_de_git(salida: str) -> list[Episodio]`.

**Contexto medido:** la historia del repo tiene **61 commits que tocan `src/` y `tests/` en el mismo commit** — episodios reconstruibles. El HANDOFF documenta **17 bugs** de clase "no falla, miente". El test mide cuántos de esos episodios el harness convierte en guardia.

- [ ] **Step 1: Write the failing test para el parser (rápido, hermético)**

Crear `tests/test_harness_falsificacion.py`:

```python
"""El test que hace falsable al harness.

Un harness que genera tests es infalsable por defecto: puede producir guardias
para siempre sin que nadie sepa si sirven. Es exactamente el hallazgo que
reordeno este proyecto, asi que aplicarlo al harness no es opcional.

La parte de parseo es hermetica y corre siempre. La parte que toca git de
verdad esta marcada `historia` y sale del corrido por defecto, igual que
`vision`: necesita la historia completa del repo.
"""

import subprocess

import pytest

from tools.harness.historia import episodios_de_git

_SALIDA = """C aaa1111 2026-08-02 fix: anualizar una sola vez
src/fdekit/value/levers.py
tests/test_value.py

C bbb2222 2026-08-01 docs: nada de codigo
docs/x.md

C ccc3333 2026-08-01 feat: algo sin tests
src/fdekit/x.py
"""


def test_solo_los_commits_con_src_y_tests_son_episodios():
    """Sin un test en el commit no hay nada que correr contra el arbol viejo."""
    eps = episodios_de_git(_SALIDA)
    assert len(eps) == 1
    assert eps[0].commit_despues == "aaa1111"


def test_el_commit_anterior_es_el_arbol_de_antes():
    eps = episodios_de_git(_SALIDA)
    assert eps[0].commit_antes == "aaa1111~1"


def test_los_archivos_tocados_llegan_al_episodio():
    eps = episodios_de_git(_SALIDA)
    assert "src/fdekit/value/levers.py" in eps[0].archivos_tocados


def test_una_salida_vacia_no_revienta():
    assert episodios_de_git("") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_harness_falsificacion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tools.harness.historia'`

- [ ] **Step 3: Write minimal implementation**

Crear `tools/harness/historia.py`:

```python
"""Reconstruye episodios de la historia de git.

El conjunto de validacion del harness no se inventa: ya existe en la historia
del repo. Todo commit que toca src/ y tests/ a la vez es un episodio
reconstruible -- el arbol de antes es el commit padre, el de despues es el
commit mismo, y el test que trae es el candidato a guardia.

Al 2-ago-2026 hay 61 commits asi, y el HANDOFF documenta 17 bugs de clase "no
falla, miente". El numero que importa es cuantos de esos el harness convierte
en guardia, publicado crudo.

`episodios_de_git` es puro sobre la salida de git para poder testearlo sin la
historia real. El comando que la produce vive en el test marcado `historia`.
"""

from __future__ import annotations

from .episodio import Episodio

FORMATO = "C %H %ad %s"
"""Usar con: git log --format='C %H %ad %s' --date=short --name-only"""


def episodios_de_git(salida: str) -> list[Episodio]:
    """Parsea la salida de `git log --format=FORMATO --date=short --name-only`."""
    eps: list[Episodio] = []
    commit = fecha = mensaje = ""
    archivos: list[str] = []

    def cerrar() -> None:
        if not commit:
            return
        tiene_src = any(a.startswith("src/") for a in archivos)
        tiene_tests = any(a.startswith("tests/") for a in archivos)
        if tiene_src and tiene_tests:
            eps.append(
                Episodio(
                    fecha=fecha,
                    commit_antes=f"{commit}~1",
                    commit_despues=commit,
                    tests_que_fallaban=(),
                    archivos_tocados=tuple(archivos),
                    mensaje=mensaje,
                )
            )

    for linea in salida.splitlines():
        if linea.startswith("C "):
            cerrar()
            partes = linea[2:].split(" ", 2)
            commit = partes[0]
            fecha = partes[1] if len(partes) > 1 else ""
            mensaje = partes[2] if len(partes) > 2 else ""
            archivos = []
        elif linea.strip():
            archivos.append(linea.strip())
    cerrar()
    return eps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_harness_falsificacion.py -q`
Expected: `4 passed`

- [ ] **Step 5: Agregar el marcador y el test que toca git de verdad**

Modificar `pyproject.toml` — la línea `markers`:

```toml
markers = [
    "vision: necesita OpenCV y un video de muestra",
    "historia: recorre la historia completa del repo, lento",
]
```

**Dejar `addopts = "-m 'not vision'"` como está** — el marcador `historia` se corre a pedido con `-m historia`, pero no se excluye del corrido por defecto salvo que tarde más de 30 s; medirlo en el Step 6 y ajustar si hace falta.

Agregar al final de `tests/test_harness_falsificacion.py`:

```python
@pytest.mark.historia
def test_la_historia_del_repo_tiene_episodios_reconstruibles():
    """El conjunto de validacion existe y hay que verlo antes de creerle al
    harness. Al 2-ago-2026 eran 61; el numero puede subir y no puede ser cero:
    si es cero, el harness no tiene contra que medirse."""
    salida = subprocess.run(
        ["git", "log", "--format=C %H %ad %s", "--date=short", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    eps = episodios_de_git(salida)

    assert len(eps) >= 40, f"solo {len(eps)} episodios reconstruibles: el conjunto de validacion se encogio"
    assert all(e.commit_antes.endswith("~1") for e in eps)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_harness_falsificacion.py -q`
Expected: `5 passed`

Run: `python -m pytest tests/test_harness_falsificacion.py::test_la_historia_del_repo_tiene_episodios_reconstruibles -q --durations=1`
Expected: PASS. **Anotar el tiempo.** Si tarda más de 30 s, cambiar `addopts` a `-m 'not vision and not historia'` y anotarlo en el HANDOFF.

Run: `python -m pytest -q`
Expected: `B + 53` passed

- [ ] **Step 7: Commit**

```bash
git add tools/harness/historia.py tests/test_harness_falsificacion.py pyproject.toml
git commit -m "feat: el conjunto de validacion del harness sale de la historia del repo

Todo commit que toca src y tests a la vez es un episodio reconstruible: el
arbol de antes es el padre. Son 61 al 2-ago-2026, contra 17 bugs de clase
'no falla, miente'. El numero que importa es cuantos de esos el harness
convierte en guardia, publicado crudo."
```

---

## Tarea 12: Cierre — índice generado y HANDOFF actualizado

**Files:**
- Create: `docs/harness/lecciones.md` (generado)
- Modify: `HANDOFF.md` (en `C:\fde\`, fuera del repo del kit)

- [ ] **Step 1: Generar el índice por primera vez**

```bash
python -c "from pathlib import Path; import sys; sys.path.insert(0, '.'); from tools.harness.indice import indice; p = Path('docs/harness'); p.mkdir(parents=True, exist_ok=True); (p / 'lecciones.md').write_text(indice(Path('tests/guards')), encoding='utf-8'); print((p / 'lecciones.md').read_text(encoding='utf-8'))"
```

Expected: imprime el encabezado + "Todavia no hay guardias en el corpus."

Eso es lo correcto: el corpus arranca vacío y el índice lo dice en vez de quedar mudo.

- [ ] **Step 2: Verificar la suite completa**

Run: `python -m pytest -q`
Expected: `B + 53` passed

- [ ] **Step 3: Verificar que el paquete sigue liviano**

```bash
python -c "import fdekit.guard, sys; print([m for m in sys.modules if m.split('.')[0] in ('numpy','pandas','scipy','matplotlib','torch','cv2')])"
```

Expected: `[]`

Si aparece algo, un import pesado se coló en `fdekit.guard` y rompe la regla 2. Arreglarlo antes de commitear.

- [ ] **Step 4: Agregar la sección al HANDOFF**

Agregar a `C:\fde\HANDOFF.md`, después de la sección de los bugs de clase "no falla, miente":

```markdown
## El harness de self-healing

Diseño: `docs/superpowers/specs/2026-08-02-harness-selfhealing-design.md`.
Plan 1: `docs/superpowers/plans/2026-08-02-harness-plan-1-contrato-y-capa-1.md`.

Dos capas. `src/fdekit/guard/` es el contrato y viaja en el paquete (stdlib
pura, sin red ni modelo). `tools/harness/` es la capa 1 y no se instala.

**Lo que el harness NO puede, y hay que decirlo antes de confiar en él:** sin
invariantes externas al test, sólo aprende de fracasos que ya se manifestaron
como test rojo. El bug que nunca falla —el patrón dominante de este repo, 17
casos— no genera episodio. El ICC hardcodeado en 0,02 es el ejemplo más
reciente: lo atrapó el inventario de mediciones, no un test.

Estado: capa 1 implementada, corpus de guardias vacío. La capa 2
(`instrumento.py`, `calibracion.py`) es el Plan 2 y arranca sólo si el Plan 1
cerró atrapando al menos uno de los 17.
```

- [ ] **Step 5: Commit**

```bash
git add docs/harness/lecciones.md
git commit -m "docs: el indice de lecciones, generado y vacio a proposito

El corpus arranca sin guardias y el indice lo dice en vez de quedar mudo."
```

```bash
cd /c/fde && git status --short 2>/dev/null || echo "HANDOFF.md no esta en un repo git -- guardar el cambio igual"
```

---

## Verificación final

- [ ] `python -m pytest -q` → `B + 53` passed, sin fallas
- [ ] `python -m pytest -m historia -q` → `1 passed`
- [ ] `python -c "import fdekit.guard, sys; print([m for m in sys.modules if m.split('.')[0] in ('numpy','pandas','scipy','matplotlib','torch','cv2')])"` → `[]`
- [ ] `git log --oneline harness/plan-1 ^master` → 12 commits
- [ ] `docs/harness/lecciones.md` existe y dice que el corpus está vacío
- [ ] `tools/` **no** aparece en `pip show -f fde-field-kit`

**Lo que queda deliberadamente sin hacer en el Plan 1:**

- El hook que llama a `captura.py` desde `settings.json`. La función está testeada; cablearla al harness de Claude Code es configuración local, no código del repo, y depende de la máquina.
- El `destilar` real (el agente). El Plan 1 entrega la orquestación con el punto agéntico inyectado y testeado con un doble. Escribir el prompt del testigo y del reparador es lo primero del Plan 2 — o de una tarea aparte, si la capa 2 se prioriza antes.
- **`.harness/cosecha/`, el reporte por corrida (spec §4.4).** `cosechar()` devuelve el `Resultado` completo —guardias, descartados con motivo, cobertura— pero el Plan 1 no lo persiste. El motivo es que el formato del reporte se decide mirando una cosecha real, y sin `destilar` no hay ninguna: un formato inventado antes del primer uso es la abstracción prematura que el repo ya evitó dos veces. Se agrega en la misma tanda que el `destilar` real. **Mientras tanto el `Resultado` no se pierde: lo devuelve la función y lo imprime quien la llame.**
- **El merge manual (spec §6).** No es código y no puede serlo: es la línea que la autoridad del harness no cruza. Queda como regla escrita en el HANDOFF (Tarea 12, Step 4), no como guardia.
- Todo `src/fdekit/guard/instrumento.py` y `calibracion.py`: son el Plan 2.
