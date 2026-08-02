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


def test_no_cuelga_en_estructura_ciclica():
    # Una estructura con ciclos no debe causar recursion infinita.
    d = {"key": "value"}
    d["self"] = d  # Crear ciclo
    assert_no_identity(d) is None  # Debe terminar sin error


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


def test_rechaza_clave_compuesta_con_campo_prohibido():
    # Una clave tupla —lo que produce canonicalize a partir de columnas
    # MultiIndex— se revisa elemento por elemento, no como tupla entera.
    payload = [{("meta", "marker_id"): "MARKER-07", ("meta", "distance_m"): 41.2}]
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(payload)


def test_estructura_muy_profunda_da_anonymity_error_no_recursion_error():
    # El contrato es "devuelve None o levanta AnonymityError". Un RecursionError
    # crudo rompe a quien solo captura AnonymityError.
    profundidad = 3000
    estructura = {"distance_m": 1.0}
    for _ in range(profundidad):
        estructura = {"nested": estructura}

    with pytest.raises(AnonymityError, match="profunda"):
        assert_no_identity(estructura)


# --- Ronda de arreglo 4: entender menos y rechazar mas ---------------------
#
# Las tres rondas anteriores agrandaron assert_no_identity para entender cada
# tipo nuevo que aparecia (DataFrame, Series, dataclass, namedtuple, objetos
# con __dict__), y cada review encontro el vecino siguiente. Esta ronda borra
# esas ramas: la funcion entiende contenedores y escalares simples, y todo lo
# demas se rechaza pidiendo canonicalize(). Los tests de abajo fijan la
# postura nueva — antes de esta ronda todos estos casos se comportaban mal.


def test_rechaza_dataframe_crudo_pidiendo_canonicalizar():
    # Un DataFrame ya no se recorre: se rechaza nombrando el tipo y pidiendo
    # la conversion. Es el contrato de fallar cerrado con superficie chica.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"marker_id": ["MARKER-07"], "distance_m": [41.2]})
    with pytest.raises(AnonymityError, match="DataFrame"):
        assert_no_identity(df)
    with pytest.raises(AnonymityError, match="canonicalize"):
        assert_no_identity(df)


def test_rechaza_series_cruda_pidiendo_canonicalizar():
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"marker_id": "MARKER-07"})
    with pytest.raises(AnonymityError, match="Series"):
        assert_no_identity(s)


def test_rechaza_dataclass_pidiendo_canonicalizar():
    # La rama de dataclass se borro: no es que el campo prohibido pase, es que
    # el objeto entero se rechaza antes de mirar adentro.
    from dataclasses import dataclass

    @dataclass
    class Event:
        operator: str
        distance_m: float

    with pytest.raises(AnonymityError, match="canonicalize"):
        assert_no_identity(Event(operator="OP-001", distance_m=41.2))


def test_rechaza_objeto_con_property():
    # Una property no vive en vars(obj): la rama de __dict__ certificaba
    # limpio este objeto porque su dato no estaba literalmente en el __dict__.
    class Evento:
        @property
        def marker_id(self):
            return "MARKER-07"

    with pytest.raises(AnonymityError, match="Evento"):
        assert_no_identity(Evento())


def test_rechaza_callable():
    # Una funcion tiene __dict__ (vacio) y antes pasaba como "objeto limpio".
    def fabricar_marker():
        return "MARKER-07"

    with pytest.raises(AnonymityError, match="canonicalize"):
        assert_no_identity(fabricar_marker)


def test_rechaza_pandas_categorical():
    # Un Categorical guarda sus valores en .categories, no en un __dict__ ni
    # en una forma que esta funcion sepa leer.
    pytest.importorskip("pandas")
    import pandas as pd

    cat = pd.Categorical(["MARKER-07", "MARKER-08"])
    with pytest.raises(AnonymityError, match="canonicalize"):
        assert_no_identity(cat)


def test_rechaza_objeto_con_slots_sin_dict():
    # Un objeto con __slots__ no tiene __dict__. Se rechaza igual que el
    # resto: la funcion no distingue entre objetos "faciles" y "dificiles".
    class Evento:
        __slots__ = ("operator", "distance_m")

        def __init__(self, operator, distance_m):
            self.operator = operator
            self.distance_m = distance_m

    with pytest.raises(AnonymityError, match="Evento"):
        assert_no_identity(Evento(operator="OP-001", distance_m=41.2))


def test_rechaza_tipo_arbitrario_no_reconocido():
    # Cualquier tipo que la funcion no sepa leer se rechaza, no se ignora.
    tipo_raro = iter([1, 2, 3])
    with pytest.raises(AnonymityError, match="no reconocido"):
        assert_no_identity(tipo_raro)


# --- canonicalize: los dos defectos que arreglo la ronda 4 ------------------


def test_canonicalize_de_series_posicional_levanta():
    # Este era el peor defecto encontrado en cuatro rondas: la conversion
    # devolvia {0: "MARKER-07", 1: "MARKER-08"} y assert_no_identity despues
    # certificaba limpio un dict con dos identificadores crudos adentro,
    # porque se habia perdido la asociacion campo -> valor. Y el flujo que lo
    # producia era el que el propio mensaje de error recomienda.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series(["MARKER-07", "MARKER-08"])
    with pytest.raises(AnonymityError, match="posicional"):
        canonicalize(s)


def test_canonicalize_de_series_con_etiquetas_da_dict_plano():
    # Sin envoltura {"name": ..., "values": ...}: esa clave "name" inventada
    # por la conversion chocaba con la verificacion y hacia fallar toda Series
    # con nombre.
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"resource": "sub-a1b2c3d4e5f6", "distance_m": 41.2}, name="fila_0")
    resultado = canonicalize(s)

    assert resultado == {"resource": "sub-a1b2c3d4e5f6", "distance_m": 41.2}
    assert "values" not in resultado
    assert assert_no_identity(resultado) is None


def test_canonicalize_de_series_con_nombre_prohibido_levanta():
    pytest.importorskip("pandas")
    import pandas as pd

    s = pd.Series({"distance_m": 41.2}, name="operator_id")
    with pytest.raises(AnonymityError, match="operator_id"):
        canonicalize(s)


def test_canonicalize_de_dataframe_con_indice_prohibido_se_atrapa_despues():
    # canonicalize() hace reset_index() antes de to_dict("records"): el
    # indice prohibido se convierte en clave comun, y assert_no_identity
    # (que sabe leer dicts y listas) lo atrapa sin codigo especial.
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"marker_id": ["MARKER-07"], "distance_m": [41.2]}).set_index("marker_id")
    resultado = canonicalize(df)

    assert isinstance(resultado, list)
    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(resultado)


def test_canonicalize_de_dataframe_con_index_name_prohibido_se_atrapa_despues():
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"distance_m": [41.2]})
    df.index.name = "marker_id"

    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(canonicalize(df))


def test_canonicalize_de_dataframe_con_columnas_multiindex_se_atrapa_despues():
    # to_dict("records") deja las columnas MultiIndex como claves tupla; la
    # verificacion las revisa elemento por elemento.
    pytest.importorskip("pandas")
    import pandas as pd

    columnas = pd.MultiIndex.from_tuples([("meta", "marker_id"), ("meta", "distance_m")])
    df = pd.DataFrame([["MARKER-07", 41.2]], columns=columnas)

    with pytest.raises(AnonymityError, match="marker_id"):
        assert_no_identity(canonicalize(df))


def test_canonicalize_es_idempotente_sobre_estructuras_simples():
    payload = {"resource": "sub-a1b2c3d4e5f6", "zonas": [{"distance_m": 41.2}]}
    assert canonicalize(payload) == payload
    assert canonicalize(canonicalize(payload)) == payload


def test_canonicalize_rechaza_lo_que_no_sabe_convertir():
    class Evento:
        pass

    with pytest.raises(AnonymityError, match="Evento"):
        canonicalize(Evento())


# --- "name" salio de IDENTITY_FIELDS ---------------------------------------


def test_name_inocuo_pasa():
    # El nombre de una zona, de un archivo o de una ubicacion no es identidad
    # personal. Tener "name" en la lista hacia fallar cualquier dict con esa
    # clave, y un falso positivo que dispara siempre entrena a la gente a
    # desactivar la verificacion.
    assert assert_no_identity({"name": "zona A", "distance_m": 41.2}) is None


def test_las_variantes_especificas_de_nombre_si_identifican():
    for campo in ("operator_name", "worker_name", "employee_name", "full_name", "nombre"):
        assert campo in IDENTITY_FIELDS
        with pytest.raises(AnonymityError, match=campo):
            assert_no_identity({campo: "Marcela", "distance_m": 41.2})


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


def test_legitimo_records_de_dataframe_con_resource_seudonimizado_sigue_pasando():
    # Exactamente lo que hace la tarea 6: assert_no_identity(df.to_dict("records")).
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame({"resource": ["sub-a1b2c3d4e5f6"], "distance_m": [41.2]})
    assert assert_no_identity(df.to_dict("records")) is None
