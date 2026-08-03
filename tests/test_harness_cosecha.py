"""El indice legible se DERIVA del corpus ejecutable, nunca al reves.

Misma decision que estado_captura (D5 de fundacion-huecos.md): un estado que
alguien tiene que acordarse de escribir es un estado que va a estar mal. La
memoria del proyecto ya mintio una vez por escribirse a mano.
"""

from pathlib import Path

from tools.harness.indice import indice
from tools.harness.cosecha import cosechar
from tools.harness.episodio import Episodio

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


def test_un_destilar_con_forma_invalida_no_tumba_la_cosecha():
    """destilar es el punto agentico, no determinista: una tupla de largo
    inesperado no puede llevarse puestos los episodios ya acumulados de la
    corrida. El episodio culpable se descarta con su motivo y se sigue."""

    llamadas = []

    def destilar_raro(ep):
        llamadas.append(ep)
        if len(llamadas) == 1:
            return ("solo_tres", "familia", "test_id")
        return _destilar_ok(ep)

    r = cosechar(
        [_ep(commit_antes="a"), _ep(commit_antes="antes")],
        destilar=destilar_raro,
        correr=_correr_ok,
        today="2026-08-02",
    )
    assert r.guardias == ("test_g",)
    assert len(r.descartados) == 1
    assert "solo_tres" in r.descartados[0][1]


def test_las_familias_se_deduplican_preservando_el_orden_de_aparicion():
    """Dos episodios de la misma clase de error no deben listarse dos veces:
    el campo dice que familias vigila, no cuantos guardias entraron."""

    r = cosechar(
        [_ep(commit_antes="antes"), _ep(commit_antes="antes")],
        destilar=_destilar_ok,
        correr=_correr_ok,
        today="2026-08-02",
    )
    assert r.guardias == ("test_g", "test_g")
    assert r.cobertura.familias_vigiladas == ("anualizacion",)


def test_la_frontera_se_chequea_antes_que_el_oraculo():
    """Un episodio que es invasor Y vacuo a la vez tiene que reportarse como
    frontera: si el orden se invirtiera, el motivo diria vacuo y esconderia
    la violacion, ademas de gastar el oraculo en una propuesta que el chequeo
    barato ya debia haber descartado."""

    def destilar_invasor_y_vacuo(_ep):
        return (
            "test_g",
            "anualizacion",
            "tests/guards/test_g.py::test_g",
            ["tests/guards/test_g.py", "src/fdekit/x.py"],
        )

    def correr_vacuo(_commit):
        return set()

    r = cosechar([_ep()], destilar=destilar_invasor_y_vacuo, correr=correr_vacuo, today="2026-08-02")
    assert r.guardias == ()
    assert "frontera" in r.descartados[0][1]
