"""El log de evidencia del harness: append-only, como el event log del kit.

D3 de fundacion-huecos.md dice que el event log no pierde filas: gana una
columna. Lo mismo aca. Un episodio que no dio leccion se MARCA, no se borra --
un log de eventos al que se le sacan eventos es exactamente la mentira
silenciosa que la regla 3 prohibe.
"""

import json

import pytest

from tools.harness.captura import registrar_corrida
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
