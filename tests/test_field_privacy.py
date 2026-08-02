"""Regla 9: la identidad no cruza el borde del dispositivo.

Esto no es una politica escrita en un PDF, es una propiedad del codigo. Los
tests de abajo SON la garantia que se muestra en la sala del cliente.
"""

import pytest

from fdekit.field.privacy import (
    IDENTITY_FIELDS,
    AnonymityError,
    AnonymityGate,
    assert_no_identity,
    new_session_salt,
    pseudonymize,
)


def test_el_seudonimo_es_estable_dentro_de_la_sesion():
    salt = new_session_salt()
    assert pseudonymize("MARKER-07", salt) == pseudonymize("MARKER-07", salt)


def test_el_seudonimo_cambia_entre_sesiones():
    # La sal no se persiste: manana nadie —ni nosotros— puede revertir el mapeo
    # de ayer. Es lo que hace que la anonimizacion no sea reversible por diseno.
    a = pseudonymize("MARKER-07", new_session_salt())
    b = pseudonymize("MARKER-07", new_session_salt())
    assert a != b


def test_el_seudonimo_no_contiene_el_original():
    salt = new_session_salt()
    p = pseudonymize("PICK-MARCELA", salt)
    assert "MARCELA" not in p.upper()
    assert p.startswith("sub-")


def test_dos_sujetos_distintos_no_colisionan():
    salt = new_session_salt()
    assert pseudonymize("MARKER-07", salt) != pseudonymize("MARKER-08", salt)


def test_la_compuerta_bloquea_bajo_k():
    g = AnonymityGate(k=3)
    assert g.allows(3) is True
    assert g.allows(2) is False

    with pytest.raises(AnonymityError, match="3"):
        g.check(2, "zona A turno noche")


def test_la_compuerta_nombra_que_bloqueo():
    # Un error que no dice que agregado se bloqueo obliga a adivinar.
    with pytest.raises(AnonymityError, match="zona A"):
        AnonymityGate(k=3).check(1, "zona A")


def test_ningun_campo_de_identidad_sobrevive_el_borde():
    ok = {"subject": "sub-a1b2c3d4e5f6", "distance_m": 41.2}
    assert_no_identity(ok) is None

    for campo in IDENTITY_FIELDS:
        with pytest.raises(AnonymityError, match=campo):
            assert_no_identity({campo: "lo que sea", "distance_m": 1.0})


def test_la_deteccion_de_identidad_es_recursiva():
    # Un identificador escondido tres niveles abajo es igual de identificador.
    payload = {"zonas": [{"tracks": [{"marker_id": "MARKER-07"}]}]}
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(payload)


def test_rechaza_dataframe_con_columna_prohibida():
    # Un DataFrame cuya columna es prohibida debe fallar.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({
        "marker_id": ["MARKER-07"],
        "distance_m": [41.2]
    })
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(df)


def test_rechaza_dataframe_con_resource_crudo():
    # Un DataFrame con columna 'resource' pero valor crudo (no seudonimo) debe fallar.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({
        "resource": ["MARKER-07"],
        "distance_m": [41.2]
    })
    with pytest.raises(AnonymityError, match="resource"):
        assert_no_identity(df)


def test_acepta_dataframe_con_resource_seudonimizado():
    # Un DataFrame con columna 'resource' pero valor en forma de seudonimo debe pasar.
    # Este es el caso legitimo del que depende la tarea 6.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({
        "resource": ["sub-a1b2c3d4e5f6"],
        "distance_m": [41.2]
    })
    assert_no_identity(df) is None


def test_rechaza_series_con_nombre_prohibido():
    # Una pandas.Series cuyo atributo .name es un campo prohibido debe fallar.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series([1, 2, 3], name="operator_id")
    with pytest.raises(AnonymityError, match="operator_id"):
        assert_no_identity(s)


def test_rechaza_dataclass_con_campo_prohibido():
    # Un dataclass que contiene un campo prohibido debe fallar.
    from dataclasses import dataclass

    @dataclass
    class Event:
        operator: str
        distance_m: float

    event = Event(operator="OP-001", distance_m=41.2)
    with pytest.raises(AnonymityError, match="operator"):
        assert_no_identity(event)


def test_rechaza_objeto_con_dict_prohibido():
    # Un objeto con atributos (via __dict__) que incluya un campo prohibido debe fallar.
    class Evento:
        def __init__(self):
            self.sensor_id = "SENSOR-001"
            self.distance_m = 41.2

    evt = Evento()
    with pytest.raises(AnonymityError, match="sensor_id"):
        assert_no_identity(evt)


def test_rechaza_namedtuple_con_campo_prohibido():
    # Una namedtuple que contiene un campo prohibido debe fallar.
    from collections import namedtuple

    Evento = namedtuple("Evento", ["rut", "distance_m"])
    evt = Evento(rut="12345678-9", distance_m=41.2)
    with pytest.raises(AnonymityError, match="rut"):
        assert_no_identity(evt)


def test_no_cuelga_en_estructura_ciclica():
    # Una estructura con ciclos no debe causar recursion infinita.
    d = {"key": "value"}
    d["self"] = d  # Crear ciclo
    assert_no_identity(d) is None  # Debe terminar sin error
