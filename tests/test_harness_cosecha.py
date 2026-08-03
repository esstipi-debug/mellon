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
        (d / (nombre + ".py")).write_text(texto, encoding="utf-8")
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
    assert "todavia no hay guardias" in md.lower()


_GUARDIA_COLUMNAS = '''"""Guardia para probar columnas."""

LECCION = {
    "regla": "regla_valor_unico",
    "familia": "familia_valor_unico",
    "commit": "abc1234",
    "fecha": "2026-08-03",
    "dueno": "dueno_user",
}


def test_x():
    assert True
'''


def test_cada_columna_de_leccion_se_lista_correctamente(tmp_path):
    """Verifica que familia, regla, commit, fecha y dueno se distingan.
    Una mutacion podria intercambiar columnas: esto lo mata."""
    md = indice(_guards(tmp_path, test_col=_GUARDIA_COLUMNAS))
    assert "| familia_valor_unico | regla_valor_unico |" in md
    assert "`abc1234`" in md
    assert "2026-08-03" in md
    assert "dueno_user" in md


def test_archivos_sin_extension_py_no_aparecen_en_el_indice(tmp_path):
    """Un archivo README.md no es guardia: el filtro .py no debe ejercitarse."""
    d = tmp_path / "guards"
    d.mkdir()
    (d / "README.md").write_text("# Guardias\n", encoding="utf-8")
    (d / "test_ok.py").write_text(_GUARDIA, encoding="utf-8")
    md = indice(d)
    assert "test_ok" in md
    assert "README" not in md
