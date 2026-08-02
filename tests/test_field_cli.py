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


def test_la_demo_de_mesa_produce_espagueti_y_residual(tmp_path):
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

    assert (tmp_path / "out" / "espagueti_medido.png").exists()
    assert r["tracks"] == 1
    assert r["measured_m_in_window"] > 0
    assert "no tratar" in r["coverage_note"].lower()


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
    a = run_field(out=tmp_path / "a", layout=MESA, **comun)
    b = run_field(out=tmp_path / "b", layout=Layout(), **comun)

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
