"""La demo de mesa entera, de CSV a grafico.

Es el criterio de exito de la etapa 1 del spec, y las dos capas de CLI del kit
no tienen tests (punto 3 de la cola de pendientes del handoff). Esta arranca
con uno.

Firmas usadas aca (las tareas 5 a 7 cambiaron cosas despues de que se escribio
el brief original de esta tarea):

- `load_detections` devuelve `tuple[list[Detection], int | None]`.
- `build_tracks` exige `frames_total` como argumento obligatorio, sin default.
- `tracks_to_eventlog` devuelve `tuple[EventLog, MeasurementCoverage]`.

Por eso `run_field` necesita `frames_total` de algun lado: del CSV (linea de
metadatos `# frames_total=<int>`, que escribe `vision.write_detections`) o de
un parametro explicito. Si no hay ninguno de los dos, falla con un mensaje que
dice que hacer -- ver `test_avisa_si_falta_frames_total_en_todos_lados`.
"""

import json
from datetime import date

import pandas as pd
import pytest

from fdekit.cli import build_parser, cmd_field, run_field
from fdekit.layout import Layout

REFS = "x_px,y_px,x_m,y_m\n0,0,0,0\n100,0,10,0\n100,100,10,10\n0,100,0,10\n"
# La geometria de la maqueta, no la del CD: 10x10 m de escritorio. Los pitches
# se eligen distintos de los del CD (3.0 / 1.2 por defecto) a proposito: si
# coincidieran por casualidad, el test de geometria de mas abajo no notaria la
# diferencia entre pasar el layout de la maqueta y no pasar ninguno.
MESA = Layout(aisles=4, bays=10, levels=2, aisle_pitch=2.5, bay_pitch=0.7)

# El video de la maqueta dura mas cuadros de los que el marcador aparece: el
# denominador de la cobertura tiene que ser mayor que el ultimo frame visto,
# si no la cobertura sale 100% por casualidad y el test no distingue nada.
FRAMES_TOTAL = 200


def _filas_deteccion() -> list[str]:
    filas = ["marker_id,frame,x_px,y_px"]
    # Se queda 6 s en un punto, se mueve, se queda 6 s en otro. 10 fps.
    filas += [f"M1,{f},30.0,20.0" for f in range(0, 60, 5)]
    filas += [f"M1,{f},60.0,30.0" for f in range(100, 160, 5)]
    return filas


def _detecciones_sin_metadata() -> str:
    return "\n".join(_filas_deteccion()) + "\n"


def _detecciones_con_metadata() -> str:
    return f"# frames_total={FRAMES_TOTAL}\n" + _detecciones_sin_metadata()


# Las dos paradas de `_filas_deteccion` caen, con la geometria MESA, en
# 01-003-1 (el punto (3,2) m) y 02-004-1 (el punto (6,3) m).
PARADAS_MESA = ("01-003-1", "02-004-1")

# El log del WMS para esas dos paradas: un pedido, dos lineas de PICK. El
# modelo rutea DOCK -> 01-003-1 -> 02-004-1 -> DOCK = 4,6 + 7,4 + 7,8 = 19,8 m.
LOG_WMS = (
    "case_id,activity,timestamp,resource,location\n"
    "PED-1,PICK,2026-09-14 10:00:00,,01-003-1\n"
    "PED-1,PICK,2026-09-14 10:00:30,,02-004-1\n"
)


def _escribir_caso(tmp_path, con_metadata=True):
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    contenido = _detecciones_con_metadata() if con_metadata else _detecciones_sin_metadata()
    (tmp_path / "det.csv").write_text(contenido, encoding="utf-8")
    (tmp_path / "wms.csv").write_text(LOG_WMS, encoding="utf-8")
    return dict(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )


def test_la_demo_de_mesa_produce_espagueti_y_residual(tmp_path):
    """El entregable del branch: no metros medidos, sino un RESIDUAL medido.

    El README promete "la diferencia entre los dos es el hallazgo". Antes de
    este arreglo, `run_field` devolvia metros, paradas, ubicaciones y cobertura
    -- y ninguna comparacion contra el modelo. Este test se llamaba
    "produce_espagueti_y_residual" y no asertaba ningun residual.
    """
    comun = _escribir_caso(tmp_path)

    r = run_field(out=tmp_path / "out", log=tmp_path / "wms.csv", k=1, **comun)

    assert (tmp_path / "out" / "espagueti_medido.png").exists()
    assert r["espagueti_path"].endswith("espagueti_medido.png")
    assert r["espagueti_withheld_reason"] is None
    assert r["tracks"] == 1
    assert r["measured_m_in_window"] > 0
    assert "no tratar" in r["coverage_note"].lower()

    residual = r["residual"]
    assert residual is not None
    # El modelo rutea 19,8 m para el unico pedido; la camara midio el salto
    # entre las dos paradas (~3,16 m) y ninguno de los dos tramos al muelle.
    assert residual["modeled_m_per_order"] == pytest.approx(19.8, abs=0.1)
    assert residual["measured_m_per_order"] == pytest.approx(3.2, abs=0.1)
    assert residual["residual_pct"] == pytest.approx(-84.0, abs=1.0)
    # Residual negativo: el modelo es un piso, asi que esto NO dice "el modelo
    # sobreestima" -- dice que la medicion no cubre lo que el modelo si cuenta.
    assert residual["residual_flag"] == "sospechoso"
    assert residual["residual_flag_reason"]
    # Y `dock_legs_pct_of_modeled` dice cuanto de esa brecha son los tramos al
    # muelle, que la camara de mesa nunca ve.
    assert residual["dock_legs_pct_of_modeled"] == pytest.approx(62.6, abs=1.0)
    assert r["residual_reason"] == residual["residual_flag_reason"]


def test_sin_log_el_residual_es_null_con_motivo_y_no_ausencia_silenciosa(tmp_path):
    """Regla 3 aplicada al campo que falta.

    Omitir la clave se lee como "no hubo residual". `None` con motivo al lado
    se lee como lo que es: no se paso el modelo contra el cual comparar.
    """
    comun = _escribir_caso(tmp_path)

    r = run_field(out=tmp_path / "out", k=1, **comun)

    assert "residual" in r
    assert r["residual"] is None
    assert "--log" in r["residual_reason"]


def test_el_residual_completa_track_pct_con_los_pedidos_del_modelo(tmp_path):
    """El criterio de exito de la etapa 3 del spec es computable o no lo es.

    "≥60% de los pedidos con marcador visible" necesita un denominador de
    PEDIDOS. Nada en src/ seteaba `tracks_expected`, asi que `track_pct` era
    siempre None y lo unico reportado era cobertura de cuadros, que responde
    otra pregunta.
    """
    comun = _escribir_caso(tmp_path)

    sin_log = run_field(out=tmp_path / "a", k=1, **comun)
    con_log = run_field(out=tmp_path / "b", log=tmp_path / "wms.csv", k=1, **comun)

    assert sin_log["residual"] is None
    assert con_log["residual"]["track_pct"] == pytest.approx(100.0)
    assert "viajes esperados" in con_log["residual"]["coverage_note"]


def test_la_salida_no_lleva_identidad(tmp_path):
    from fdekit.field.privacy import assert_no_identity

    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_con_metadata(), encoding="utf-8")

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
    diferencia -- y la taza sobre el escritorio quedaria reportada en el
    pasillo 2 modulo 2, que es un numero sin significado fisico.
    """
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_con_metadata(), encoding="utf-8")

    comun = dict(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
    )
    # k=1: con una sola pista, el borde de salida retiene `locations` bajo el
    # default k=3 -- que es justamente lo que verifica
    # `test_locations_no_se_emite_bajo_el_umbral_de_anonimato`. Aca se baja a
    # proposito porque lo que se prueba es la geometria, no la compuerta.
    a = run_field(out=tmp_path / "a", layout=MESA, k=1, **comun)
    b = run_field(out=tmp_path / "b", layout=Layout(), k=1, **comun)

    # Las paradas son las mismas dos; lo que cambia es a que ubicacion caen.
    assert a["stops"] == b["stops"] == 2
    assert a["locations"] != b["locations"]


def test_avisa_si_el_csv_de_referencias_no_tiene_cuatro_filas(tmp_path):
    (tmp_path / "refs.csv").write_text("x_px,y_px,x_m,y_m\n0,0,0,0\n", encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_con_metadata(), encoding="utf-8")

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


def test_usa_frames_total_del_csv_cuando_esta_declarado(tmp_path):
    """El CSV trae la linea de metadatos: no hace falta pasar frames_total."""
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_con_metadata(), encoding="utf-8")

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )
    assert f"/{FRAMES_TOTAL} " in r["coverage_note"]


def test_usa_frames_total_explicito_cuando_falta_en_el_csv(tmp_path):
    """El CSV no trae la linea de metadatos: `frames_total` explicito alcanza."""
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_sin_metadata(), encoding="utf-8")

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
        frames_total=FRAMES_TOTAL,
    )
    assert f"/{FRAMES_TOTAL} " in r["coverage_note"]


def test_avisa_si_falta_frames_total_en_todos_lados(tmp_path):
    """Sin metadata en el CSV y sin `frames_total` explicito: falla, no adivina.

    Un `frames_total` inventado (p.ej. derivado del frame maximo visto)
    produciria una cobertura del 100% permanente y vaciaria el modulo entero
    de cobertura -- exactamente lo que la regla 3 prohibe.
    """
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_sin_metadata(), encoding="utf-8")

    with pytest.raises(ValueError, match="write_detections|--frames"):
        run_field(
            detections=tmp_path / "det.csv",
            refs=tmp_path / "refs.csv",
            out=tmp_path / "out",
            fps=10.0,
            t0=pd.Timestamp("2026-09-14 10:00:00"),
            today=date(2026, 9, 14),
            layout=MESA,
        )


def test_run_field_nunca_mira_el_reloj(tmp_path, monkeypatch):
    """Regla 4: el reloj se lee UNA sola vez, en el borde -- nunca en el analisis.

    Dos comprobaciones. Primera: `pd.Timestamp.now()` se rompe antes de
    llamar; si `run_field` lo llamara por su cuenta en vez de usar el `t0`
    recibido, la llamada explotaria. Segunda: `t0` y `today` no tienen
    default en la firma (`inspect.signature` lo confirma) -- sin default no
    hay forma de omitirlos sin querer y caer de vuelta al reloj real, que es
    el otro modo en que "regla 4" se rompe en silencio.
    """
    import inspect

    def _reloj_roto(*a, **kw):
        raise AssertionError("run_field no deberia leer el reloj directamente")

    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, *a, **kw: _reloj_roto()))

    parametros = inspect.signature(run_field).parameters
    assert parametros["t0"].default is inspect.Parameter.empty
    assert parametros["today"].default is inspect.Parameter.empty

    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_con_metadata(), encoding="utf-8")

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )
    assert r["tracks"] == 1


def test_cli_field_despacha_con_set_defaults_func(tmp_path):
    """El CLI no despacha con `args.cmd`: el subparser `field` fija `func`."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "field",
            "--detections",
            str(tmp_path / "det.csv"),
            "--refs",
            str(tmp_path / "refs.csv"),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert args.func is cmd_field
    assert args.frames is None


def test_cli_field_end_to_end(tmp_path, capsys):
    """La demo de mesa de punta a punta, pasando por el parser y `cmd_field`."""
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(_detecciones_sin_metadata(), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "field",
            "--detections",
            str(tmp_path / "det.csv"),
            "--refs",
            str(tmp_path / "refs.csv"),
            "--out",
            str(tmp_path / "out"),
            "--fps",
            "10",
            "--frames",
            str(FRAMES_TOTAL),
            # Una sola taza sobre el escritorio: con el k=3 por defecto el PNG
            # no se escribe, porque el grafico ES el itinerario de ese unico
            # sujeto. --k 1 asume esa decision de forma explicita.
            "--k",
            "1",
            "--aisles",
            "4",
            "--bays",
            "10",
            "--aisle-pitch",
            "3",
            "--bay-pitch",
            "1",
        ]
    )
    rc = args.func(args)
    assert rc == 0

    salida = capsys.readouterr().out
    assert "coverage_note" in salida
    assert (tmp_path / "out" / "espagueti_medido.png").exists()


def test_cli_field_con_log_imprime_el_residual(tmp_path, capsys):
    """De punta a punta con --log: el residual sale por stdout.

    Es la prueba de que el entregable existe como PRODUCTO y no solo como
    funcion importable: `compare_travel` estaba escrita y testeada desde la
    tarea 8, y no la llamaba ninguna linea de codigo de produccion.
    """
    _escribir_caso(tmp_path)

    parser = build_parser()
    args = parser.parse_args(
        [
            "field",
            "--detections", str(tmp_path / "det.csv"),
            "--refs", str(tmp_path / "refs.csv"),
            "--log", str(tmp_path / "wms.csv"),
            "--out", str(tmp_path / "out"),
            "--fps", "10",
            "--k", "1",
            "--aisles", "4",
            "--bays", "10",
            "--aisle-pitch", "2.5",
            "--bay-pitch", "0.7",
        ]
    )
    assert args.func(args) == 0

    salida = json.loads(capsys.readouterr().out)
    assert salida["residual"]["residual_pct"] is not None
    assert salida["residual"]["residual_flag"] in {"esperado", "sospechoso"}


# ------------------------------------------- puntos fuera de planta (max_distance)


def _detecciones_con_salto_fuera_de_planta() -> str:
    """Las mismas dos paradas, mas un tramo que salta 500 m fuera de planta.

    Las referencias mapean 0-100 px a 0-10 m, asi que 5000 px son 500 m: lo
    tipico de una homografia mal calibrada.
    """
    filas = _filas_deteccion()
    # Cuatro segundos a 10 fps: lo suficiente para que, SIN el limite, el
    # punto pegado al borde del layout genere una parada real de mas.
    filas += [f"M1,{f},5000.0,5000.0" for f in range(160, 205, 5)]
    return f"# frames_total={FRAMES_TOTAL}\n" + "\n".join(filas) + "\n"


def test_un_punto_fuera_de_planta_se_descarta_y_la_cobertura_lo_dice(tmp_path):
    """`max_distance_m` deja de ser codigo inerte.

    `run_field` nunca lo pasaba, y el default `None` DESACTIVA el chequeo
    entero: el punto a 500 m se pegaba a la esquina del layout, contaba como
    parada real y la cobertura no decia nada. Ahora el limite se deriva de la
    geometria y siempre se pasa.
    """
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(
        _detecciones_con_salto_fuera_de_planta(), encoding="utf-8"
    )

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
        k=1,
    )

    # El limite sale de la geometria (2 x el mayor pitch de MESA = 5 m), no de
    # un numero fijo ni de que alguien se acuerde de pasarlo.
    assert r["max_distance_m"] == pytest.approx(5.0)
    # El punto de 500 m no invento una ubicacion de borde...
    assert set(r["locations"]) == set(PARADAS_MESA)
    # ...y la cobertura lo declara nombrando la causa probable.
    assert "fuera de planta" in r["coverage_note"]
    assert "homografia mal calibrada" in r["coverage_note"]


def test_sin_el_limite_el_punto_fuera_de_planta_se_pegaba_al_borde(tmp_path):
    """El contraste que prueba que el chequeo hace algo.

    Con `max_distance_m` grande (el equivalente al `None` de antes), el mismo
    punto se mapea a una ubicacion del layout y la cobertura no menciona nada.
    """
    (tmp_path / "refs.csv").write_text(REFS, encoding="utf-8")
    (tmp_path / "det.csv").write_text(
        _detecciones_con_salto_fuera_de_planta(), encoding="utf-8"
    )

    r = run_field(
        detections=tmp_path / "det.csv",
        refs=tmp_path / "refs.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
        max_distance_m=10_000.0,
        k=1,
    )

    assert len(r["locations"]) > len(PARADAS_MESA)
    assert "fuera de planta" not in r["coverage_note"]


# ----------------------------------------------- borde de salida (reglas 9 y 10)


def test_locations_no_se_emite_bajo_el_umbral_de_anonimato(tmp_path):
    """Regla 10, aplicada en el borde y no solo definida en un modulo.

    Con un solo sujeto, `locations` es el itinerario completo de una persona
    identificable. `AnonymityGate` existia, estaba testeada y exportada, y no
    la invocaba ninguna linea de codigo de produccion.
    """
    comun = _escribir_caso(tmp_path)

    r = run_field(out=tmp_path / "out", **comun)  # k=3 por defecto, 1 pista

    assert r["locations"] is None
    motivo = r["locations_withheld_reason"]
    assert "1 sujeto" in motivo
    assert "k=3" in motivo
    # El resto de la salida sigue saliendo: la compuerta retiene el agregado
    # identificante, no la medicion entera.
    assert r["measured_m_in_window"] > 0
    assert r["stops"] == 2


def test_el_png_no_se_escribe_bajo_el_umbral_de_anonimato(tmp_path):
    """El PNG es salida a disco y tambien pasa por el borde.

    Antes de este arreglo `plot_spaghetti` escribia el archivo ANTES de que se
    armara `salida` y antes de `gate_output`: con k=3 y una sola pista el JSON
    retenia `locations` con su motivo y en el mismo directorio quedaba el
    grafico con el recorrido completo del unico sujeto. Retener la lista y
    dibujarla al lado no retiene nada.
    """
    comun = _escribir_caso(tmp_path)

    r = run_field(out=tmp_path / "out", log=tmp_path / "wms.csv", **comun)  # k=3

    assert not (tmp_path / "out" / "espagueti_medido.png").exists()
    assert r["espagueti_path"] is None
    motivo = r["espagueti_withheld_reason"]
    assert "1 sujeto" in motivo
    assert "k=3" in motivo
    assert "--k 1" in motivo
    # El resto de la medicion sigue saliendo: la compuerta retiene lo
    # identificante, no el numero.
    assert r["locations"] is None
    assert r["measured_m_in_window"] > 0
    assert r["residual"]["residual_pct"] is not None


def test_con_k_1_el_png_si_se_escribe(tmp_path):
    """El contraste: bajar el umbral a proposito es una decision legitima."""
    comun = _escribir_caso(tmp_path)

    r = run_field(out=tmp_path / "out", k=1, **comun)

    assert (tmp_path / "out" / "espagueti_medido.png").exists()
    assert r["espagueti_path"] == str(tmp_path / "out" / "espagueti_medido.png")
    assert r["espagueti_withheld_reason"] is None
    assert r["locations"] == list(PARADAS_MESA)


def test_la_salida_registra_el_k_con_el_que_se_emitio(tmp_path):
    """Un resultado con k=1 y uno con k=3 no son el mismo resultado.

    Sin `anonymity_k` en la salida, la decision de bajar el umbral es
    invisible para quien lee el JSON despues.
    """
    comun = _escribir_caso(tmp_path)

    con_default = run_field(out=tmp_path / "a", **comun)
    con_uno = run_field(out=tmp_path / "b", k=1, **comun)

    assert con_default["anonymity_k"] == 3
    assert con_uno["anonymity_k"] == 1


def test_el_parser_rechaza_k_cero_temprano_y_con_que_hacer(tmp_path, capsys):
    """`--k 0` no baja el umbral: apaga la compuerta (allows(n) = n >= 0).

    Falla en el parser para que el error salga antes de procesar el video, y
    no recien al emitir.
    """
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "field",
                "--detections", str(tmp_path / "det.csv"),
                "--refs", str(tmp_path / "refs.csv"),
                "--k", "0",
            ]
        )
    err = capsys.readouterr().err
    assert "--k" in err
    assert ">= 1" in err


def test_el_parser_acepta_k_1(tmp_path):
    """k=1 es el minimo legitimo, no un caso de borde a bloquear."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "field",
            "--detections", str(tmp_path / "det.csv"),
            "--refs", str(tmp_path / "refs.csv"),
            "--k", "1",
        ]
    )
    assert args.k == 1


def test_toda_la_salida_pasa_por_assert_no_identity(tmp_path, monkeypatch):
    """El borde es un lugar por el que se pasa siempre, no una funcion util.

    Si `run_field` emitiera sin pasar por `gate_output`, romper
    `assert_no_identity` no cambiaria nada y este test pasaria igual.
    """
    from fdekit.field import privacy

    def _explotar(payload):
        raise privacy.AnonymityError("el borde se ejecuto")

    monkeypatch.setattr(privacy, "assert_no_identity", _explotar)

    comun = _escribir_caso(tmp_path)
    with pytest.raises(privacy.AnonymityError, match="el borde se ejecuto"):
        run_field(out=tmp_path / "out", k=1, **comun)
