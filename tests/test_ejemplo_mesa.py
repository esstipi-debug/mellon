"""El ejemplo de `examples/mesa/` corre y da lo que su README promete.

Un ejemplo que dejo de funcionar es peor que no tener ejemplo: el que lo corre
no sabe si se equivoco el o el repo, y en un artefacto cuyo trabajo es que
alguien ajeno lo ejecute en cinco minutos, eso lo inutiliza entero.

Estos tests corren LOS ARCHIVOS DE `examples/`, no una copia inline. Es la
diferencia entre verificar el ejemplo y verificar otra cosa parecida: si alguien
edita un CSV o lo borra, esto falla. `tests/test_field_cli.py` ya cubre la
logica con datos inline; aca lo que se prueba es que lo que esta publicado en
el repo sigue siendo cierto.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fdekit.cli import run_field
from fdekit.layout import Layout

EJEMPLO = Path(__file__).resolve().parent.parent / "examples" / "mesa"

# La geometria que el README manda pasar por CLI. Un escritorio de 10x10 m no es
# un CD de doce pasillos: sin esto la taza cae en "pasillo 2 modulo 2" y el
# numero sale igual sin querer decir nada.
MESA = Layout(aisles=4, bays=10, levels=2, aisle_pitch=2.5, bay_pitch=0.7)


@pytest.fixture
def corrida(tmp_path):
    return run_field(
        detections=EJEMPLO / "det.csv",
        refs=EJEMPLO / "refs.csv",
        log=EJEMPLO / "wms.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
    )


def test_los_tres_csv_del_ejemplo_existen():
    """Si falta uno, el README miente y el comando que publica no corre."""
    faltan = [n for n in ("det.csv", "refs.csv", "wms.csv") if not (EJEMPLO / n).is_file()]
    assert not faltan, f"examples/mesa/ incompleto: {faltan}"
    assert (EJEMPLO / "README.md").is_file()


def test_el_denominador_de_cobertura_viaja_en_el_archivo():
    """`# frames_total=200` en la primera linea no es decorativo.

    Es el denominador. Sin el, `build_tracks` no tiene contra que dividir y el
    ultimo frame visto pasaria por total: la cobertura daria 100% por
    casualidad. Que viaje DENTRO del CSV es lo que hace que el ejemplo se pueda
    mover de carpeta sin perder el dato.
    """
    primera = (EJEMPLO / "det.csv").read_text(encoding="utf-8").splitlines()[0]
    assert primera == "# frames_total=200"


def test_el_ejemplo_da_los_numeros_que_su_readme_promete(corrida):
    """Los numeros publicados y los reales no pueden divergir en silencio."""
    residual = corrida["residual"]
    assert residual is not None
    assert residual["modeled_m_per_order"] == pytest.approx(19.8, abs=0.1)
    assert residual["measured_m_per_order"] == pytest.approx(3.2, abs=0.1)
    assert residual["residual_pct"] == pytest.approx(-84.0, abs=1.0)
    assert residual["dock_legs_pct_of_modeled"] == pytest.approx(62.6, abs=1.0)


def test_el_ejemplo_esta_elegido_para_que_el_residual_salga_mal(corrida):
    """El caso que ensena no es el que cierra.

    Un residual negativo se lee facil como "el modelo clavo". Es al reves: el
    modelo solo puede subestimar porque asume ruta optima, asi que un negativo
    apunta a un problema de medicion. El ejemplo existe para mostrar ESO, y por
    eso el flag tiene que venir en 'sospechoso' con motivo.
    """
    residual = corrida["residual"]
    assert residual["residual_flag"] == "sospechoso"
    assert residual["residual_flag_reason"]
    assert "12.0%" in residual["coverage_note"]


def test_con_el_k_por_defecto_el_espagueti_no_toca_el_disco(corrida, tmp_path):
    """Un solo sujeto no llega al umbral de anonimato, y el PNG no se escribe.

    Lo que se verifica no es el mensaje sino el DISCO: retener el campo del
    JSON y dejar el PNG al lado seria teatro de privacidad, y es justamente lo
    que el motivo dice que no se hace.
    """
    assert corrida["espagueti_path"] is None
    assert corrida["espagueti_withheld_reason"]
    assert corrida["anonymity_k"] == 3
    assert not list((tmp_path / "out").glob("*.png"))


def test_bajando_el_umbral_a_proposito_si_sale_el_png(tmp_path):
    """El README dice que con `--k 1` se obtiene. Tiene que ser cierto."""
    r = run_field(
        detections=EJEMPLO / "det.csv",
        refs=EJEMPLO / "refs.csv",
        log=EJEMPLO / "wms.csv",
        out=tmp_path / "out",
        fps=10.0,
        t0=pd.Timestamp("2026-09-14 10:00:00"),
        today=date(2026, 9, 14),
        layout=MESA,
        k=1,
    )
    assert r["espagueti_withheld_reason"] is None
    assert (tmp_path / "out" / "espagueti_medido.png").is_file()
