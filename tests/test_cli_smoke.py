"""Smoke test de las dos capas de CLI. 1.077 LOC que no tenian ningun test.

No pretende cubrir la logica —esa vive en los tests de cada modulo— sino la
clase de defecto que solo se ve al invocar: un subcomando que no parsea, un
`dest` mal escrito, un flag documentado que no existe, o un ejemplo del README
que falla al copiarlo. Ese ultimo caso ya se dio: el ejemplo de `decide confirm`
omitia `--meeting`, que es obligatorio.
"""

import re
from pathlib import Path

import pytest

from fdekit.cli import build_parser

README = Path(__file__).resolve().parent.parent / "README.md"

# Todos los subcomandos, en las dos capas.
COMANDOS = [
    ["demo"], ["synth"], ["mine"], ["travel"], ["dq"], ["sim"], ["spc"], ["probe"],
    ["templates"], ["value"],
    ["decide", "meeting"], ["decide", "add", "decision"], ["decide", "add", "commitment"],
    ["decide", "add", "assumption"], ["decide", "add", "question"],
    ["decide", "draft"], ["decide", "review"], ["decide", "agenda"], ["decide", "why"],
    ["decide", "refs"], ["decide", "close"], ["decide", "tick"],
    ["decide", "supersede"], ["decide", "head"],
    ["decide", "transcribe"], ["decide", "resolve"], ["decide", "confirm"],
    ["decide", "unalias"], ["decide", "aliases"], ["decide", "metrics"],
    ["decide", "mine"], ["decide", "export"], ["decide", "seed"],
    ["decide", "pilot", "init"], ["decide", "pilot", "baseline"],
    ["decide", "pilot", "score"], ["decide", "pilot", "survey"],
    ["decide", "pilot", "verdict"],
]


@pytest.mark.parametrize("argv", COMANDOS, ids=lambda a: " ".join(a))
def test_todo_subcomando_expone_su_help(argv):
    """`--help` recorre el parser entero: si un `dest`, un `choices` o un
    `set_defaults` esta mal, revienta aca y no en la sala del cliente."""
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args([*argv, "--help"])
    assert e.value.code == 0


def test_el_parser_se_construye_entero():
    p = build_parser()
    assert p.prog == "fdekit"


def _bloques_bash(texto: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", texto, re.S)


def _lineas_fdekit(md: str) -> list[list[str]]:
    """Comandos `fdekit ...` de los bloques bash del README, reensamblando las
    continuaciones con backslash."""
    import shlex

    out = []
    for bloque in _bloques_bash(md):
        crudo = bloque.replace("\\\n", " ")
        for linea in crudo.splitlines():
            linea = linea.split("#")[0].strip()
            if linea.startswith("fdekit "):
                out.append(shlex.split(linea)[1:])
    return out


def test_los_ejemplos_del_readme_parsean():
    """El ejemplo de `decide confirm` del README omitia `--meeting`, que es
    obligatorio: fallaba al copiarlo y pegarlo. Un README que no se puede
    copiar es peor que uno corto."""
    fallan = []
    for argv in _lineas_fdekit(README.read_text(encoding="utf-8")):
        try:
            build_parser().parse_args(argv)
        except SystemExit:
            fallan.append(" ".join(argv))
    assert not fallan, "ejemplos del README que no parsean:\n  " + "\n  ".join(fallan)


def test_el_readme_trae_ejemplos_de_las_dos_mitades():
    """Guardia contra que este test pase por no encontrar nada que revisar."""
    cmds = _lineas_fdekit(README.read_text(encoding="utf-8"))
    assert len(cmds) >= 10
    assert any(c[0] == "decide" for c in cmds)
    assert any(c[0] not in ("decide",) for c in cmds)
