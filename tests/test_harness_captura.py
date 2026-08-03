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
