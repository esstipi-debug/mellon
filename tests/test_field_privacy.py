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
    canonicalize,
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


def test_rechaza_series_desde_dict_con_clave_prohibida():
    # Una Series construida desde dict con clave prohibida debe fallar.
    # La clave se convierte en indice.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"marker_id": "MARKER-07"})
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(s)


def test_rechaza_series_desde_dict_en_lista():
    # Una Series dentro de una lista debe atraparse igual.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"operator_id": "OP-001"})
    with pytest.raises(AnonymityError, match="operator_id"):
        assert_no_identity([s])


def test_rechaza_series_con_indice_pseudonym_field_crudo():
    # Una Series cuyo indice tiene una etiqueta en PSEUDONYM_FIELDS pero valor crudo.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"resource": "MARKER-07", "distance": 41.2})
    with pytest.raises(AnonymityError, match="resource"):
        assert_no_identity(s)


def test_rechaza_resource_con_entero():
    # Un campo 'resource' con un entero (no string, no None, no NA) debe fallar.
    d = {"resource": 42, "distance_m": 41.2}
    with pytest.raises(AnonymityError, match="resource"):
        assert_no_identity(d)


def test_rechaza_resource_con_objeto_arbitrario():
    # Un campo 'resource' con un objeto arbitrario debe fallar.
    class Marker:
        pass

    d = {"resource": Marker(), "distance_m": 41.2}
    with pytest.raises(AnonymityError, match="resource"):
        assert_no_identity(d)


def test_rechaza_seudonimo_con_newline():
    # Un seudonimo con salto de linea final no debe pasar (regresion \Z).
    d = {"resource": "sub-a1b2c3d4e5f6\n", "distance_m": 41.2}
    with pytest.raises(AnonymityError, match="resource"):
        assert_no_identity(d)


def test_acepta_resource_none():
    # resource=None debe ser permitido (case legitimate en EventLog).
    d = {"resource": None, "distance_m": 41.2}
    assert_no_identity(d) is None


def test_acepta_resource_pd_na():
    # resource=pd.NA debe ser permitido (case legitimo en EventLog).
    pytest.importorskip("pandas")
    import pandas as pd

    d = {"resource": pd.NA, "distance_m": 41.2}
    assert_no_identity(d) is None


def test_acepta_resource_seudonimo_valido():
    # resource con un seudonimo bien formado debe pasar.
    d = {"resource": "sub-a1b2c3d4e5f6", "distance_m": 41.2}
    assert_no_identity(d) is None


# --- Ronda de arreglo 3: fallar cerrado en vez de lista negra ---------------
#
# Las tres rondas anteriores cerraron, cada una, el caso que se le señalo y
# dejaron abierta la variante vecina mas obvia (DataFrame, indice de Series,
# ahora MultiIndex e indice de DataFrame). Los tests de abajo son ataques que
# pasaban en silencio ANTES de esta ronda.


def test_rechaza_dataframe_con_columnas_multiindex():
    # Una columna MultiIndex tipo ("meta", "marker_id") no matchea IDENTITY_FIELDS
    # si se compara la tupla entera. Hay que aplanar y revisar cada elemento.
    pytest.importorskip("pandas")
    import pandas as pd

    columnas = pd.MultiIndex.from_tuples([("meta", "marker_id"), ("meta", "distance_m")])
    df = pd.DataFrame([["MARKER-07", 41.2]], columns=columnas)
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(df)


def test_rechaza_series_con_indice_multiindex():
    # Mismo ataque que el DataFrame, pero sobre el indice de una Series.
    pytest.importorskip("pandas")
    import pandas as pd

    indice = pd.MultiIndex.from_tuples([("meta", "operator_id"), ("meta", "distance_m")])
    s = pd.Series(["OP-001", 41.2], index=indice)
    with pytest.raises(AnonymityError, match="operator_id"):
        assert_no_identity(s)


def test_rechaza_dataframe_con_marker_id_como_indice_de_fila():
    # df.set_index("marker_id") mueve el nombre de campo al indice: el VALOR
    # de cada fila ya no es "marker_id", pero el NOMBRE del eje si lo es.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"marker_id": ["MARKER-07"], "distance_m": [41.2]}).set_index("marker_id")
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(df)


def test_rechaza_dataframe_con_index_name_marker_id():
    # Mismo hueco, via asignacion directa de index.name en vez de set_index.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"distance_m": [41.2]})
    df.index.name = "marker_id"
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(df)


def test_rechaza_objeto_con_slots_sin_dict():
    # Un objeto con __slots__ no tiene __dict__: antes de esta ronda pasaba
    # en silencio porque no matcheaba ningun isinstance conocido.
    class Evento:
        __slots__ = ("operator", "distance_m")

        def __init__(self, operator, distance_m):
            self.operator = operator
            self.distance_m = distance_m

    evt = Evento(operator="OP-001", distance_m=41.2)
    with pytest.raises(AnonymityError, match="Evento"):
        assert_no_identity(evt)


def test_rechaza_tipo_arbitrario_no_reconocido():
    # Cualquier tipo que la funcion no sepa leer se rechaza, no se ignora.
    tipo_raro = iter([1, 2, 3])
    with pytest.raises(AnonymityError, match="no reconocido"):
        assert_no_identity(tipo_raro)


def test_estructura_muy_profunda_da_anonymity_error_no_recursion_error():
    # El contrato es "devuelve None o levanta AnonymityError". Un RecursionError
    # crudo rompe a quien solo captura AnonymityError.
    profundidad = 3000
    estructura = {"distance_m": 1.0}
    for _ in range(profundidad):
        estructura = {"nested": estructura}

    with pytest.raises(AnonymityError, match="profunda"):
        assert_no_identity(estructura)


def test_canonicalize_de_dataframe_con_indice_prohibido_se_atrapa_despues():
    # canonicalize() hace reset_index() antes de to_dict("records"): el
    # indice prohibido se convierte en columna comun, y assert_no_identity
    # (que ya sabe leer dicts y listas) lo atrapa sin codigo especial.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"marker_id": ["MARKER-07"], "distance_m": [41.2]}).set_index("marker_id")
    resultado = canonicalize(df)

    assert isinstance(resultado, list)
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(resultado)


# --- Re-confirmar los casos legitimos: esta ronda no debe romperlos --------


def test_legitimo_resource_none_sigue_pasando():
    assert assert_no_identity({"resource": None, "distance_m": 41.2}) is None


def test_legitimo_resource_pd_na_sigue_pasando():
    pytest.importorskip("pandas")
    import pandas as pd

    assert assert_no_identity({"resource": pd.NA, "distance_m": 41.2}) is None


def test_legitimo_seudonimo_bien_formado_sigue_pasando():
    assert assert_no_identity({"resource": "sub-a1b2c3d4e5f6", "distance_m": 41.2}) is None


def test_legitimo_resource_no_esta_en_identity_fields():
    assert "resource" not in IDENTITY_FIELDS


def test_legitimo_dataframe_con_resource_seudonimizado_sigue_pasando():
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"resource": ["sub-a1b2c3d4e5f6"], "distance_m": [41.2]})
    assert assert_no_identity(df) is None
