"""La demo del Decision Cockpit viaja en mellon y se abre sin servidor.

`linchpin.fly.dev/cockpit` responde 404: el cockpit esta en `main` de Kern por
un merge local y nunca se desplego. `docs/cockpit.html` es la pagina que arma
Kern con `scripts/build_cockpit_page.py --copy-to`, y lleva adentro una corrida
real congelada, en `<script id="narvi-snapshot">`.

Estos tests no comparan la copia con Kern: eso dependeria de otro repo. Fijan
que la copia este entera, que cada corrida tenga su camino completo y que la
pagina no le pida nada a otro servidor.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "docs" / "cockpit.html"
_ETIQUETA = '<script id="narvi-snapshot" type="application/json">'


def test_la_demo_esta_en_docs():
    assert DEMO.exists(), (
        f"falta {DEMO}: se arma desde Kern con "
        "`python scripts/build_cockpit_page.py --copy-to <mellon>/docs/cockpit.html`"
    )


@pytest.fixture(scope="module")
def pagina() -> str:
    return DEMO.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def corrida(pagina: str) -> dict:
    assert pagina.count(_ETIQUETA) == 1, "la pagina tiene que traer una sola corrida congelada"
    m = re.search(re.escape(_ETIQUETA) + r"(.*?)</script>", pagina, re.DOTALL)
    assert m, "la etiqueta de la corrida no cierra"
    return json.loads(m.group(1))


def test_la_corrida_dice_de_que_commit_de_kern_salio(corrida):
    assert corrida["meta"]["kern_commit"]
    assert corrida["meta"]["generated_at"]


def test_cada_muestra_tiene_su_corrida_completa(corrida):
    """El mismo contrato que `run_sample` en Kern: ingesta y plan siempre; si el
    plan trae un cambio, o se aprobo y se deshizo, o la aprobacion se rechazo."""
    muestras = [s["id"] for s in corrida["samples"]["samples"]]
    assert muestras, "la corrida no trae muestras"
    assert sorted(muestras) == sorted(corrida["runs"])
    for nombre, run in corrida["runs"].items():
        assert {"intake", "solve"} <= set(run), nombre
        aprobacion = {"approve", "rollback", "approve_error"} & set(run)
        if run["solve"]["changeset"] is None:
            assert not aprobacion, nombre
        else:
            aprobada_y_deshecha = {"approve", "rollback"} <= set(run)
            assert aprobada_y_deshecha != ("approve_error" in run), nombre


def test_la_demo_no_le_pide_nada_a_otro_servidor(pagina):
    """Se abre con doble clic: ni scripts, ni estilos, ni fuentes de afuera."""
    externos = re.findall(
        r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//[^"']*"""
        r"""|url\(\s*["']?\s*(?:https?:)?//[^)"']*"""
        r"""|@import""",
        pagina,
        re.IGNORECASE,
    )
    assert externos == []
