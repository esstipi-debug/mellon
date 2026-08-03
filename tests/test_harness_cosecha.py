"""El indice legible se DERIVA del corpus ejecutable, nunca al reves.

Misma decision que estado_captura (D5 de fundacion-huecos.md): un estado que
alguien tiene que acordarse de escribir es un estado que va a estar mal. La
memoria del proyecto ya mintio una vez por escribirse a mano.
"""

from pathlib import Path

from tools.harness.indice import indice
from tools.harness.cosecha import cosechar
from tools.harness.episodio import Episodio, agregar, leer, marcar
from tools.harness.roles import viola_frontera

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


def _ep(commit_antes="antes", commit_despues="despues", estado="abierto", archivos_tocados=None):
    """El default de `archivos_tocados` vive dentro de la frontera del testigo.

    Es el diff de git, y la cosecha ahora lo verifica contra la misma frontera
    que la declaracion del agente: un default con `src/` haria que todos los
    casos de este archivo se descartaran por frontera y taparia lo que cada
    test quiere medir. El caso de `src/` en el diff tiene su propio test.
    """
    return Episodio(
        fecha="2026-08-02",
        commit_antes=commit_antes,
        commit_despues=commit_despues,
        tests_que_fallaban=("t::uno",),
        archivos_tocados=("tests/guards/test_g.py",) if archivos_tocados is None else archivos_tocados,
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
    """La prohibicion se verifica sobre lo que el agente declara Y sobre el diff."""

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


# ------------------------------------------- la frontera y sus dos fuentes


def test_el_diff_del_episodio_voltea_aunque_destilar_declare_solo_tests():
    """Hallazgo 1: la frontera no puede verificarse contra la autodeclaracion.

    `destilar` es el punto agentico y el propio modulo declara que no es
    confiable. Si el guardia mira solo lo que el agente dice haber tocado, un
    agente que omite `src/fdekit/value/levers.py` de su lista pasa el control.
    `ep.archivos_tocados` viene del diff de git (`git log --name-only`) y es la
    fuente que no se puede fabricar: tiene que mirarse siempre.

    Mata la mutacion de volver a `viola_frontera("testigo", tocados)` a secas.
    """
    ep = _ep(archivos_tocados=("src/fdekit/value/levers.py",))

    def destilar_que_omite(_e):
        return ("test_g", "anualizacion", "tests/guards/test_g.py::test_g", ["tests/guards/test_g.py"])

    r = cosechar([ep], destilar=destilar_que_omite, correr=_correr_ok, today="2026-08-02")

    assert r.guardias == ()
    motivo = r.descartados[0][1]
    assert "frontera" in motivo
    assert "diff" in motivo, "el motivo tiene que nombrar al diff como la fuente de la violacion"
    assert "src/fdekit/value/levers.py" in motivo


def test_una_omision_del_agente_se_reporta_como_mas_grave_que_una_declarada():
    """Que el diff muestre algo que el agente no declaro no es lo mismo que una
    violacion declarada: la primera dice que la declaracion entera es
    inservible. Quien lee el descarte tiene que poder distinguirlas."""
    ep = _ep(archivos_tocados=("src/fdekit/value/levers.py",))

    def destilar_que_omite(_e):
        return ("test_g", "anualizacion", "tests/guards/test_g.py::test_g", ["tests/guards/test_g.py"])

    r = cosechar([ep], destilar=destilar_que_omite, correr=_correr_ok, today="2026-08-02")
    assert "omitio" in r.descartados[0][1]


def test_con_las_dos_fuentes_limpias_el_guardia_entra():
    """La contracara del test anterior: el chequeo doble no puede volverse un
    guardia que descarta todo. Si declaracion y diff estan los dos dentro de
    `tests/`, el episodio llega al oraculo y produce guardia."""
    ep = _ep(archivos_tocados=("tests/guards/test_g.py", "tests/test_value.py"))
    r = cosechar([ep], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.guardias == ("test_g",)
    assert r.descartados == ()


# ------------------------------------------------------ el oraculo que revienta


def test_un_correr_que_revienta_no_tumba_la_cosecha():
    """Hallazgo 3: `correr` shellea a git y a pytest, asi que reventar es su
    modo de falla normal. Sin el try, el primer episodio con un `correr` roto se
    lleva puestos todos los guardias ya acumulados en la corrida.

    Mata la mutacion de sacar el try alrededor de `veredicto`.
    """
    llamadas = []

    def correr_que_revienta(commit):
        llamadas.append(commit)
        if len(llamadas) <= 1:
            raise RuntimeError("git worktree add fallo: el arbol esta sucio")
        return _correr_ok(commit)

    r = cosechar(
        [_ep(commit_antes="a"), _ep(commit_antes="antes")],
        destilar=_destilar_ok,
        correr=correr_que_revienta,
        today="2026-08-02",
    )

    assert r.guardias == ("test_g",), "el episodio sano tiene que sobrevivir al que reviento"
    assert len(r.descartados) == 1
    assert "oraculo exploto" in r.descartados[0][1]
    assert "git worktree add fallo" in r.descartados[0][1]


# ---------------------------------------------------------- bugs_atrapados


def test_bugs_atrapados_sin_medir_no_se_reporta_como_cero():
    """Hallazgo 4: `bugs_atrapados` en 0 se lee como 'medimos y no atrapamos
    ninguno'. Nada mapea un episodio a uno de los 17 casos de HANDOFF.md, asi
    que el dato no existe -- y ausencia de dato no es un resultado."""
    r = cosechar([_ep()], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.cobertura.bugs_atrapados is None
    assert "SIN MEDIR" in r.cobertura.nota()
    assert "atrapa 0 de 17" not in r.cobertura.nota()


def test_bugs_atrapados_se_puebla_solo_si_el_llamador_lo_provee():
    r = cosechar([_ep()], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02", bugs_atrapados=1)
    assert r.cobertura.bugs_atrapados == 1
    assert "atrapa 1 de 17" in r.cobertura.nota()


# --------------------------------------------------------------- marcas


def test_el_resultado_trae_las_marcas_para_que_el_llamador_cierre_el_log():
    """Hallazgo 5: sin esto el log queda en `abierto` para siempre y cada
    cosecha reprocesa todo. `cosechar` no abre el log -- no sabe de que archivo
    salieron los episodios -- pero devuelve el indice y el estado nuevo."""
    r = cosechar(
        [_ep(commit_antes="antes"), _ep(commit_antes="a"), _ep(commit_antes="z", estado="destilado")],
        destilar=lambda e: _destilar_ok(e) if e.commit_antes == "antes" else None,
        correr=_correr_ok,
        today="2026-08-02",
    )
    assert r.marcas == ((0, "destilado"), (1, "descartado"))


def test_un_episodio_que_no_esta_abierto_no_genera_marca():
    """Ya tiene estado: remarcarlo lo pisaria con uno que no le corresponde."""
    r = cosechar([_ep(estado="irreproducible")], destilar=_destilar_ok, correr=_correr_ok, today="2026-08-02")
    assert r.marcas == ()


def test_las_marcas_de_la_cosecha_se_aplican_al_log_de_verdad(tmp_path):
    """El circulo completo: el llamador lee, cosecha y marca. Si `marcas` no
    alcanzara para hacerlo, la promesa del docstring de episodio.py seria
    falsa."""
    log = tmp_path / "episodios.jsonl"
    agregar(log, _ep(commit_antes="antes"))
    agregar(log, _ep(commit_antes="a"))

    eps = leer(log)
    r = cosechar(
        eps,
        destilar=lambda e: _destilar_ok(e) if e.commit_antes == "antes" else None,
        correr=_correr_ok,
        today="2026-08-02",
    )
    for indice_ep, estado in r.marcas:
        marcar(log, indice_ep, estado)

    assert [e.estado for e in leer(log)] == ["destilado", "descartado"]


# ------------------------------------------------- roles: normalizacion


def test_una_ruta_con_dotdot_no_se_cuela_por_el_prefijo():
    """Hallazgo 2: `tests/../src/fdekit/value/levers.py` empieza con `tests/` y
    no es un archivo de tests. La premisa vieja -- que las rutas llegan
    normalizadas del diff -- era falsa: tambien llegan del agente.

    Mata la mutacion de volver a `a.startswith(permitidos)` a secas.
    """
    assert viola_frontera("testigo", ["tests/../src/fdekit/value/levers.py"]) == [
        "tests/../src/fdekit/value/levers.py"
    ]


def test_una_ruta_con_barras_invertidas_se_normaliza_igual():
    """En Windows `a\\..\\b` es la misma ruta que `a/../b`.

    El caso que discrimina es el mixto: `tests/..\\src\\x.py` empieza con
    `tests/`, asi que el prefijo lo deja pasar, y si el `..` se colapsa con
    posixpath sin traducir antes las barras invertidas, el separador de Windows
    no se reconoce y la ruta sigue leyendose como si viviera bajo `tests/`.

    Mata la mutacion de sacar el `.replace("\\\\", "/")` de `_normalizada`.
    """
    assert viola_frontera("testigo", ["tests/..\\src\\fdekit\\x.py"]) == ["tests/..\\src\\fdekit\\x.py"]


def test_una_ruta_de_tests_en_estilo_windows_sigue_permitida():
    """La contracara: traducir las barras no puede volverse un guardia que
    prohibe los paths que Windows entrega legitimamente dentro de `tests/`."""
    assert viola_frontera("testigo", ["tests\\guards\\test_x.py"]) == []


def test_una_ruta_que_escapa_del_arbol_es_violacion():
    assert viola_frontera("testigo", ["../otro_repo/tests/test_x.py"]) != []


def test_un_dotdot_que_vuelve_a_tests_sigue_estando_permitido():
    """La normalizacion no puede volverse un guardia que prohibe todo: una ruta
    que despues de colapsar `..` sigue dentro de `tests/` esta bien."""
    assert viola_frontera("testigo", ["tests/guards/../test_x.py", "tests/./test_y.py"]) == []


def test_la_frontera_no_toca_el_disco():
    """Nada de `resolve()`: consulta el filesystem y sigue symlinks, asi que el
    veredicto dependeria de que el arbol este montado. Una ruta inexistente
    tiene que evaluarse igual."""
    assert viola_frontera("testigo", ["tests/no/existe/test_x.py"]) == []
    assert viola_frontera("testigo", ["src/no/existe/x.py"]) == ["src/no/existe/x.py"]


# --------------------------------------- indice: procedencia y archivos rotos


_GUARDIA_SIN_COMMIT = '''"""Guardia al que le falta el commit."""

LECCION = {
    "regla": "una regla cualquiera",
    "familia": "anualizacion",
    "fecha": "2026-08-03",
    "dueno": "stipi",
}


def test_x():
    assert True
'''


def test_un_leccion_incompleto_se_lista_como_sin_procedencia(tmp_path):
    """Hallazgo 6: `Procedencia` levanta ValueError si falta commit o dueno,
    pero el indice lo leia con `.get(..., '-')` y mostraba el guardia como sano
    con un guion cosmetico. Un LECCION al que le falta un campo obligatorio no
    tiene procedencia, igual que si faltara entero -- y el indice tiene que
    decir CUAL falta.

    Mata la mutacion de volver a `lec.get('commit', '-')` sin chequear.
    """
    md = indice(_guards(tmp_path, test_sin_commit=_GUARDIA_SIN_COMMIT))
    assert "test_sin_commit" in md
    assert "sin procedencia" in md
    assert "commit" in md
    assert "`-`" not in md, "no puede mostrarse como un guardia sano con el commit en guion"


def test_el_indice_dice_cual_campo_de_procedencia_falta(tmp_path):
    """Nombrar los campos no alcanza con buscarlos en todo el markdown: los tres
    aparecen en el encabezado de la tabla. Hay que mirar el RENGLON del guardia,
    que es donde alguien va a leer que le falta."""
    faltan_dos = 'LECCION = {"regla": "r", "familia": "f"}\n\n\ndef test_x():\n    assert True\n'
    md = indice(_guards(tmp_path, test_mocho=faltan_dos))
    renglon = next(l for l in md.splitlines() if "test_mocho" in l)
    assert "le falta" in renglon
    assert "commit" in renglon
    assert "fecha" in renglon
    assert "dueno" in renglon


def test_un_leccion_con_campo_vacio_tampoco_tiene_procedencia(tmp_path):
    """`Procedencia` levanta con commit vacio, no solo con commit ausente."""
    vacio = _GUARDIA.replace('"commit": "b2267bd",', '"commit": "",')
    md = indice(_guards(tmp_path, test_vacio=vacio))
    assert "sin procedencia" in md


def test_un_py_con_bytes_no_utf8_no_apaga_el_indice(tmp_path):
    """Hallazgo 8: el arreglo anterior cubrio el `.pyc` volviendo al
    `glob("*.py")`, pero un `.py` corrupto seguia llegando a `read_text` sin
    proteccion. Es el mismo modo de falla que el modulo existe para impedir."""
    d = tmp_path / "guards"
    d.mkdir()
    (d / "test_ok.py").write_text(_GUARDIA, encoding="utf-8")
    (d / "test_corrupto.py").write_bytes(b"LECCION = {'regla': '\xff\xfe roto'}\n")

    md = indice(d)

    assert "una sola anualizacion" in md, "el guardia sano tiene que seguir listandose"
    assert "test_corrupto" in md
    assert "ilegible" in md
