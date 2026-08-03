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
