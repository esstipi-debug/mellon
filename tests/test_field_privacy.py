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
    gate_output,
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


def test_k_cero_no_se_puede_construir_porque_apaga_la_compuerta():
    """`allows(n)` es `n >= k`: con k=0 devuelve verdadero para todo n.

    El dataclass no validaba `k` -- el unico de sus argumentos que viene del
    usuario -- mientras `gate_output` si validaba `n_subjects`, que nadie
    toca. Con k=0 la compuerta se vuelve un no-op y nada en la salida lo
    registra.
    """
    with pytest.raises(ValueError, match=">= 1"):
        AnonymityGate(k=0)


def test_k_negativo_tampoco_se_puede_construir():
    with pytest.raises(ValueError, match=">= 1"):
        AnonymityGate(k=-1)


def test_k_1_es_legitimo_y_el_mensaje_lo_dice():
    """Bajar a 1 es una decision explicita, no un error: la maqueta de mesa
    tiene un solo carro y el software no puede tomar esa decision por nadie."""
    assert AnonymityGate(k=1).allows(1) is True
    with pytest.raises(ValueError) as exc:
        AnonymityGate(k=0)
    assert "k=1 es el minimo" in str(exc.value)


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


# --- Ronda 5: coherencia con fallar cerrado --------------------------------
#
# Dos huecos que dejo la ronda 4 por listar `tuple` entre los contenedores
# aceptados y no exigir nada de las claves de dict. Los dos tienen el mismo
# fondo que la Series posicional: un valor sin nombre de campo al lado no se
# puede verificar contra nada.


def test_rechaza_namedtuple_pidiendo_asdict():
    # Un namedtuple es un registro, no una tupla plana. Recorrerlo por la rama
    # de tupla mira los valores pero nunca los nombres, y "operator" pasaria.
    from collections import namedtuple

    Ev = namedtuple("Ev", ["operator", "x"])
    with pytest.raises(AnonymityError, match="_asdict"):
        assert_no_identity(Ev(operator="OP-001", x=1))


def test_namedtuple_convertido_con_asdict_pasa_por_el_camino_bueno():
    # El camino que el mensaje de error recomienda tiene que funcionar, y el
    # campo prohibido tiene que verse una vez convertido.
    from collections import namedtuple

    Ev = namedtuple("Ev", ["operator", "x"])
    with pytest.raises(AnonymityError, match="operator"):
        assert_no_identity(Ev(operator="OP-001", x=1)._asdict())

    Medicion = namedtuple("Medicion", ["distance_m", "zona"])
    assert assert_no_identity(Medicion(distance_m=41.2, zona="A")._asdict()) is None


def test_canonicalize_rechaza_namedtuple():
    # Convertirlo a lista perderia los nombres de campo: el mismo defecto que
    # hace rechazar la Series posicional.
    from collections import namedtuple

    Ev = namedtuple("Ev", ["operator", "x"])
    with pytest.raises(AnonymityError, match="_asdict"):
        canonicalize(Ev(operator="OP-001", x=1))


def test_rechaza_dict_con_claves_enteras():
    # Un dict con claves enteras es un mapeo posicional disfrazado: sus
    # valores se recorrerian sin ningun nombre de campo contra el cual
    # verificarlos.
    with pytest.raises(AnonymityError, match="nombre de campo"):
        assert_no_identity({0: "MARKER-07", 1: "MARKER-08"})


def test_rechaza_dict_con_clave_entera_anidado():
    with pytest.raises(AnonymityError, match="nombre de campo"):
        assert_no_identity({"zonas": [{"distance_m": 41.2}, {7: "MARKER-07"}]})


def test_acepta_dict_con_clave_tupla_de_strings():
    # La tupla sigue permitida: es lo que produce canonicalize para columnas
    # MultiIndex, y se verifica elemento por elemento.
    payload = {("meta", "distance_m"): 41.2, ("meta", "zona"): "A"}
    assert assert_no_identity(payload) is None


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


# --- Arreglo final: comparacion de nombres de campo case/space-insensible ----


@pytest.mark.parametrize(
    "clave",
    ["Marker_ID", "MARKER_ID", "marker_id ", " marker_id", "Operator", "RUT"],
)
def test_variantes_de_mayusculas_y_espacios_de_un_campo_que_identifica_se_atrapan(clave):
    """Las cabeceras de un export de WMS vienen en mayusculas la mitad de las
    veces. Comparando por igualdad exacta, solo `marker_id` se atrapaba."""
    with pytest.raises(AnonymityError, match="identifica"):
        assert_no_identity({clave: "ARUCO-CRUDO-7"})


def test_resource_en_mayuscula_ya_no_desactiva_la_validacion_de_seudonimo():
    """El bypass total que estaba parqueado: en PSEUDONYM_FIELDS, una clave con
    otra capitalizacion no solo cambiaba la clasificacion del campo -- apagaba
    la verificacion de FORMA del valor, y `{"Resource": "Juan Perez"}` se
    certificaba limpio."""
    with pytest.raises(AnonymityError, match="seudonimo"):
        assert_no_identity({"Resource": "Juan Perez"})


def test_la_normalizacion_no_unifica_separadores_a_proposito():
    """`MarkerID` en camelCase sigue pasando: unificar separadores es un paso
    aparte con su propia matriz de ataque, y mezclarlo aca traeria falsos
    positivos que casefold()+strip() no tiene. Se documenta el limite en vez de
    fingir que esta cubierto (regla 3)."""
    assert assert_no_identity({"MarkerID": "ARUCO-CRUDO-7"}) is None


def test_la_normalizacion_no_trae_falsos_positivos():
    assert assert_no_identity({"Location": "01-003-1", "Distance_M": 41.2}) is None


# --- Arreglo final: etiquetas duplicadas no borran la evidencia -------------


def test_series_con_etiquetas_duplicadas_se_rechaza_en_vez_de_perder_un_valor():
    """El peor modo de falla de una compuerta de privacidad: no falla abierta,
    borra la prueba. Con el indice repetido, el dict se queda con un valor y el
    identificador crudo desaparece ANTES de que la verificacion lo vea."""
    pytest.importorskip("pandas")
    import pandas as pd

    serie = pd.Series(["ARUCO-CRUDO-7", "sub-0123456789ab"], index=["resource", "resource"])
    with pytest.raises(AnonymityError, match="repetida"):
        canonicalize(serie)


def test_dataframe_con_columnas_duplicadas_se_rechaza():
    pytest.importorskip("pandas")
    import pandas as pd

    df = pd.DataFrame([["ARUCO-CRUDO-7", "sub-0123456789ab"]], columns=["resource", "resource"])
    with pytest.raises(AnonymityError, match="repetida"):
        canonicalize(df)


def test_series_con_etiquetas_distintas_sigue_convirtiendose():
    pytest.importorskip("pandas")
    import pandas as pd

    serie = pd.Series(["sub-0123456789ab", 41.2], index=["resource", "distance_m"])
    assert canonicalize(serie) == {"resource": "sub-0123456789ab", "distance_m": 41.2}


# --- Arreglo final: el mensaje no escribe la identidad que atrapo -----------


def test_el_mensaje_de_error_no_transcribe_el_valor_identificante():
    """La compuerta existe para que la identidad no cruce el borde. Un mensaje
    que la escribe entera va a stdout, al log y al ticket: filtra exactamente
    lo que vino a contener."""
    identidad = "Juan Perez RUT 12.345.678-9"
    with pytest.raises(AnonymityError) as exc:
        assert_no_identity({"resource": identidad})

    mensaje = str(exc.value)
    assert identidad not in mensaje
    assert "Perez" not in mensaje
    assert "12.345.678" not in mensaje
    # Nombra el campo y el tipo de problema, y da una pista de tres caracteres.
    assert "resource" in mensaje
    assert "seudonimo" in mensaje
    assert "'Jua...'" in mensaje


def test_el_mensaje_de_clave_no_valida_tampoco_transcribe_el_valor():
    # Una clave que no es nombre de campo (aca, bytes) puede traer identidad
    # adentro: el mensaje nombra el tipo y da tres caracteres, no la transcribe.
    with pytest.raises(AnonymityError) as exc:
        assert_no_identity({b"Juan Perez RUT 12.345.678-9": "x"})
    mensaje = str(exc.value)
    assert "12.345.678" not in mensaje
    assert "Perez" not in mensaje
    assert "bytes" in mensaje


# --- Regla 10 en el borde: gate_output --------------------------------------


def test_gate_output_retiene_locations_bajo_el_umbral():
    salida = {"locations": ["01-003-1", "02-004-1"], "stops": 2}
    r = gate_output(salida, n_subjects=1)

    assert r["locations"] is None
    assert "1 sujeto" in r["locations_withheld_reason"]
    assert r["stops"] == 2
    # No muta el original.
    assert salida["locations"] == ["01-003-1", "02-004-1"]


def test_gate_output_emite_locations_al_llegar_al_umbral():
    salida = {"locations": ["01-003-1"], "stops": 2}
    r = gate_output(salida, n_subjects=3)

    assert r["locations"] == ["01-003-1"]
    assert "locations_withheld_reason" not in r


def test_gate_output_respeta_un_k_explicito():
    salida = {"locations": ["01-003-1"]}
    assert gate_output(salida, n_subjects=1, gate=AnonymityGate(k=1))["locations"]


def test_gate_output_echa_el_umbral_usado_en_la_salida():
    """Con que k se emitio esto es parte del resultado, no del contexto perdido."""
    assert gate_output({"stops": 2}, n_subjects=9)["anonymity_k"] == 3
    con_uno = gate_output({"locations": ["01-003-1"]}, n_subjects=1, gate=AnonymityGate(k=1))
    assert con_uno["anonymity_k"] == 1
    assert con_uno["locations"] == ["01-003-1"]


def test_gate_output_corre_assert_no_identity_sobre_todo_el_diccionario():
    with pytest.raises(AnonymityError, match="identifica"):
        gate_output({"locations": [], "marker_id": "ARUCO-CRUDO-7"}, n_subjects=99)


def test_gate_output_rechaza_lo_que_no_es_un_dict_de_resultados():
    with pytest.raises(AnonymityError, match="dict de resultados"):
        gate_output(["01-003-1"], n_subjects=99)
