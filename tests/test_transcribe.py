"""Tests de la capa que NO depende de torch.

La logica de extraccion vive completa en Python puro justamente para poder
testearla. La llamada a Whisper no se prueba con un mock que solo verifica que
se llamo a una funcion: se prueba con un audio real, marcado `audio` y excluido
por defecto, igual que `vision`. Correr con: pytest -m audio

`tests/data/audio_muestra.wav` son 10 s de voz sintetizada con SAPI diciendo una
frase de bodega. Es audio real —no un tono— y no depende de que alguien tenga a
mano una grabacion de terreno.
"""

import sys

import pytest

from fdekit.gemba import (
    GembaSession,
    classify_waste,
    draft_observations,
    parse_duration_s,
    parse_frequency_per_shift,
    review_queue,
)
from fdekit.gemba import transcribe as _transcribe_fn  # noqa: F401  (ver abajo)
from fdekit.gemba.transcribe import (
    WASTE_LEXICON,
    _cobertura,
    parse_operators,
    split_utterances,
    strip_accents,
    waste_candidates,
)

# El paquete exporta una funcion llamada `transcribe`, que sombrea al modulo del
# mismo nombre: `import fdekit.gemba.transcribe as t` devuelve la funcion. Para
# monkeypatchear `WASTE_LEXICON` hace falta el modulo de verdad.
_transcribe = sys.modules["fdekit.gemba.transcribe"]


# ------------------------------------------------------------- normalizacion


def test_quita_acentos():
    assert strip_accents("día andén reposición") == "dia anden reposicion"


# ------------------------------------------------------------------ duracion


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("me demoro 2 minutos", 120),
        ("como 30 segundos", 30),
        ("son 2,5 minutos", 150),
        ("treinta segundos buscando", 30),
        ("dos minutos", 120),
        ("media hora parado", 1800),
        ("una hora y media esperando", 5400),
        ("hora y media", 5400),
        ("un minuto y medio", 90),
        ("3 horas", 10800),
    ],
)
def test_parseo_de_duracion(texto, esperado):
    assert parse_duration_s(texto) == pytest.approx(esperado)


def test_duracion_ausente_devuelve_none():
    assert parse_duration_s("esto se demora un monton") is None


def test_cada_n_minutos_es_frecuencia_no_duracion():
    """El error silencioso: la misma frase alimentando los dos campos multiplica
    el impacto por 40 y se lleva el Pareto entero."""
    assert parse_duration_s("me toca cada 10 minutos") is None
    assert parse_frequency_per_shift("me toca cada 10 minutos") == pytest.approx(48)


def test_duracion_y_frecuencia_conviven_en_la_misma_frase():
    frase = "me demoro 2 minutos y me pasa cada 30 minutos"
    assert parse_duration_s(frase) == pytest.approx(120)
    assert parse_frequency_per_shift(frase) == pytest.approx(16)


# ---------------------------------------------------------------- frecuencia


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("pasa 20 veces al dia", 20),
        ("unas 15 veces por turno", 15),
        ("tres veces por hora", 24),  # 3 x 8h de turno
        ("cada 10 minutos", 48),  # 8h / 10min
        ("cada media hora", None),  # 'media' no es numero: queda para el humano
        ("cada 2 horas", 4),
    ],
)
def test_parseo_de_frecuencia(texto, esperado):
    got = parse_frequency_per_shift(texto)
    if esperado is None:
        assert got is None
    else:
        assert got == pytest.approx(esperado)


def test_frecuencia_respeta_el_largo_del_turno():
    assert parse_frequency_per_shift("cada 30 minutos", shift_hours=12) == pytest.approx(24)


def test_operadores_afectados():
    assert parse_operators("nos pasa a los tres pickers") == 3
    assert parse_operators("me pasa a mi") == 1


# ------------------------------------------------------------ clasificacion


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("me quedo esperando que llegue la ola", "ESPERA"),
        ("tengo que caminar hasta el otro pasillo a buscar", "MOVIMIENTO"),
        ("el sistema me manda la caja chica y no cierra", "DEFECTO"),
        ("lo anoto en el WMS y ademas anoto en una planilla aparte", "SOBREPROCESO"),
        ("ya avise mil veces y nadie escucha", "TALENTO"),
    ],
)
def test_clasificacion_de_desperdicio(texto, esperado):
    waste, conf = classify_waste(texto)
    assert waste == esperado
    assert conf > 0


def test_texto_sin_senal_no_se_clasifica():
    waste, conf = classify_waste("buenos dias, como estas")
    assert waste is None
    assert conf == 0.0


@pytest.mark.parametrize(
    "texto",
    [
        "el operario espera dos minutos en el anden porque el pallet no tiene hueco",
        "el turno espera la grua horquilla",
        "el sistema demora y todos esperan",
    ],
)
def test_espera_en_tercera_persona_se_clasifica(texto):
    """El lexico estaba escrito entero en primera persona.

    'espero', 'esperar', 'esperando' — el operador contando lo que le pasa.
    Pero `draft_observations` tambien recibe al FDE narrando a su propio
    telefono lo que VE, y ahi la forma es 'el operario espera'. Sin 'espera'
    en el lexico esa frase no clasificaba, y `draft_observations` la
    descartaba entera: una observacion de manual, con duracion y frecuencia,
    que no producia nada.
    """
    waste, conf = classify_waste(texto)
    assert waste == "ESPERA"
    assert conf >= 0.5, "no deberia necesitar confirmacion humana: es inequivoca"


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("el picker camina hasta el rack del fondo", "MOVIMIENTO"),
        ("ella busca el SKU en otro pasillo", "MOVIMIENTO"),
        ("se agacha para el nivel bajo del rack", "MOVIMIENTO"),
        ("recorre todo el pasillo 12 antes de encontrarlo", "MOVIMIENTO"),
        ("cruza el pasillo cada vez que le falta una caja", "MOVIMIENTO"),
        ("da la vuelta completa al rack", "MOVIMIENTO"),
        ("los dos pickers esperan la ola", "ESPERA"),
        ("se demora el WMS y nadie puede pistolear", "ESPERA"),
        ("va hasta el rack del fondo", "MOVIMIENTO"),
        # Sin 'no calza' ni 'hasta el anden': si la frase trae una segunda
        # keyword del mismo tipo, el test pasa igual con el lexico viejo y no
        # prueba la conjugacion que dice probar. Verificado sacando 'rehace' y
        # 'traslada' de a una.
        ("rehace la etiqueta del pallet", "DEFECTO"),
        ("devuelve el pallet a recepcion", "DEFECTO"),
        ("lo hace de nuevo con la etiqueta correcta", "DEFECTO"),
        ("revisa de nuevo el conteo antes de cerrar", "SOBREPROCESO"),
        ("vuelve a contar las cajas en el anden", "SOBREPROCESO"),
        ("tambien lo anota en la planilla de papel", "SOBREPROCESO"),
        ("ademas anota la hora en un cuaderno", "SOBREPROCESO"),
        ("traslada la mercaderia a recepcion", "TRANSPORTE"),
        ("lleva el pallet desde bodega", "TRANSPORTE"),
        ("mueve el pallet desde el rack al anden", "TRANSPORTE"),
        ("se acumula producto en el pasillo de recepcion", "INVENTARIO"),
        ("se amontona todo frente al anden 3", "INVENTARIO"),
        ("se apila carga suelta al costado del rack", "INVENTARIO"),
        ("adelanta el armado del pedido de la tarde", "SOBREPRODUCCION"),
        ("prepara de mas para la ola de la tarde", "SOBREPRODUCCION"),
        ("nadie le pregunta al que hace el trabajo", "TALENTO"),
        ("lo viene diciendo hace meses", "TALENTO"),
    ],
)
def test_los_8_tipos_clasifican_en_tercera_persona(texto, esperado):
    """El FDE narrando lo que ve, no el operario contando lo que le pasa.

    Los dos modos de uso son reales y producen persona gramatical distinta. El
    lexico cubria solo el segundo. Medido antes de arreglarlo: 26 de 36 formas
    de tercera persona no clasificaban, y MOVIMIENTO y TRANSPORTE estaban en
    cobertura cero — o sea que grabarse a uno mismo recorriendo el CD no
    producia ninguna observacion de los dos desperdicios mas frecuentes.

    Un tipo por caso, para que cuando uno se rompa el nombre del test diga cual.
    """
    waste, conf = classify_waste(texto)
    assert waste == esperado
    assert conf >= 0.5, "sin ambiguedad real no deberia pedir confirmacion humana"


@pytest.mark.parametrize(
    "texto",
    [
        "el turno empieza a las ocho de la manana",
        "trabajo aca hace tres anos",
        "el cafe de la maquina esta malo",
        "ayer llovio bastante en la manana",
        # Discurso referido. TALENTO es "avise y nadie me escucho", no "alguien
        # dijo algo". Con 'le dijo' en el lexico estas tres daban TALENTO con
        # confianza 1.0 — o sea `ready`, o sea al Pareto sin revision humana.
        "el supervisor le dijo que fuera al anden 3",
        "el jefe de turno le dijo donde estaba el SKU",
    ],
)
def test_ampliar_el_lexico_no_clasifica_conversacion_normal(texto):
    """El precio de ampliar un lexico por substring son los falsos positivos.

    Un enunciado de cortesia que entra al Pareto como desperdicio es peor que
    uno que se pierde: el que se pierde deja el Pareto corto, el falso positivo
    lo deja mintiendo. Estas frases son las que rodean a una observacion real
    en cualquier grabacion de pasillo.
    """
    assert classify_waste(texto) == (None, 0.0)


@pytest.mark.parametrize(
    "texto",
    [
        # 'de mas' cruzaba limite de palabra: "desde mas" es "des" + "de mas".
        "lo trae desde mas alla del pasillo 9",
        "viene desde mas atras en la fila",
        # Y aun bien delimitada, "de mas o menos" quiere decir "aproximadamente".
        "tarda de mas o menos dos minutos en llegar",
    ],
)
def test_de_mas_no_clasifica_por_aparecer_suelta(texto):
    """'de mas' era una keyword de dos palabras cortas, y eso no alcanza.

    Daba SOBREPRODUCCION con confianza 1.0 —o sea `ready`, o sea al Pareto sin
    que nadie lo mire— sobre frases que no hablan de producir de mas. Dos de
    estas ni siquiera contienen la expresion: la contienen por accidente, porque
    "desde" termina en "de" y el match es por substring.

    El reemplazo son las formas ancladas al verbo ('preparo de mas', 'prepara
    de mas'), que es como esta escrito el resto del lexico.
    """
    assert classify_waste(texto) == (None, 0.0)


@pytest.mark.parametrize(
    "texto",
    [
        "me llevo la pistola de repuesto por si acaso",
        "dejo un pallet libre por si acaso",
    ],
)
def test_por_si_acaso_es_un_motivo_no_un_desperdicio(texto):
    """'por si acaso' dice POR QUE se hace algo, no QUE se hace.

    Es un adverbial de motivo: se pega al verbo que venga y no identifica
    ningun desperdicio por si solo. "Reviso de nuevo por si acaso" es
    SOBREPROCESO por 'reviso de nuevo', no por 'por si acaso'; "dejo un pallet
    libre por si acaso" no es sobreproceso de ninguna manera.

    Verificado sacandola: ningun test del repo la cubria. Solo generaba falsos
    positivos con confianza 1.0.
    """
    assert classify_waste(texto) == (None, 0.0)


def test_sacar_los_modificadores_no_pierde_el_desperdicio_real():
    """La mitad que importa: el arreglo no puede llevarse la senal legitima.

    Un test que solo comprueba que dejo de clasificar de mas no distingue
    'arregle el falso positivo' de 'rompi la categoria'.
    """
    assert classify_waste("lo reviso de nuevo por si acaso")[0] == "SOBREPROCESO"
    assert classify_waste("vuelvo a contar por si acaso")[0] == "SOBREPROCESO"
    assert classify_waste("prepara de mas para la ola de la tarde")[0] == "SOBREPRODUCCION"
    assert classify_waste("preparo de mas y despues sobra")[0] == "SOBREPRODUCCION"


def test_esperando_no_le_roba_el_enunciado_a_inventario():
    """Pallets que se acumulan es INVENTARIO, aunque digan 'esperando'.

    Este test no protege un bug que exista hoy: protege el arreglo obvio del
    que NO existe hoy. El lexico de ESPERA no tiene 'espera' —solo 'esperando',
    'espero', 'esperar'— asi que "el operario espera dos minutos" no clasifica
    y `draft_observations` lo descarta entero. El arreglo que se cae de maduro
    es agregar 'espera' al lexico.

    Ese arreglo rompe esta frase. `classify_waste` puntua con `kw in t`: si
    'espera' entra al lexico, 'esperando' la contiene y el enunciado suma DOS
    hits a ESPERA por una sola aparicion. Empata con los dos hits reales de
    INVENTARIO ('pallets esperando' y 'se junta'), y el desempate lo termina
    decidiendo el orden de las claves de `WASTE_LEXICON` — ESPERA esta primero.
    La clasificacion pasaria a depender del orden literal del diccionario.

    Verificado revirtiendo: con 'espera' agregado y sin deduplicar solapes,
    esto devuelve ESPERA con confianza 0.0. La suite completa sigue en verde
    igual, porque ningun otro test mira este caso.
    """
    waste, conf = classify_waste("hay pallets esperando al lado del anden, se junta todo")
    assert waste == "INVENTARIO", (
        "un keyword que es substring de otro no puede contar como evidencia aparte"
    )
    assert conf > 0


# El caso canonico de empate: mover un pallet dos veces ES transporte y ES
# reproceso. La frase no es ambigua por mal escrita — el desperdicio es genuina
# y simultaneamente de dos tipos.
EMPATE = "mueve el pallet dos veces para sacar el de atras"


def test_un_empate_declara_los_dos_tipos_en_vez_de_elegir_uno():
    """Empatar en el tope no es tener un ganador con poca confianza.

    `classify_waste` ordenaba por puntaje con `sorted`, que es estable, asi que
    un empate lo resolvia el orden de insercion de `WASTE_LEXICON`. Devolvia el
    primero de la lista con confianza 0.0 y perdia la identidad del otro.
    """
    assert set(waste_candidates(EMPATE)) == {"TRANSPORTE", "SOBREPROCESO"}


def test_el_empate_no_lo_decide_el_orden_del_lexico(monkeypatch):
    """La invariante que faltaba: reordenar el lexico no cambia el resultado.

    Verificado antes del arreglo: con el orden actual esa frase daba
    SOBREPROCESO, y poniendo TRANSPORTE primero en el diccionario daba
    TRANSPORTE. La clasificacion dependia de en que linea del archivo estaba
    escrita cada categoria.
    """
    antes = waste_candidates(EMPATE)

    invertido = {
        k: WASTE_LEXICON[k]
        for k in ["TRANSPORTE"] + [x for x in WASTE_LEXICON if x != "TRANSPORTE"]
    }
    monkeypatch.setattr(_transcribe, "WASTE_LEXICON", invertido)

    assert set(waste_candidates(EMPATE)) == set(antes)


def test_el_empate_va_a_la_cola_nombrando_el_tipo_como_lo_que_falta():
    """El dano concreto: el ambiguo encabezaba la cola diciendo estar completo.

    `review_queue` ordena por `(len(missing), -confidence)`. Un empate dejaba
    `missing=()` —nada que pedir— asi que se ordenaba ANTES que un borrador al
    que solo le faltaba la frecuencia. El revisor abria la cola y lo primero que
    veia era una observacion con duracion, frecuencia y un tipo elegido por el
    orden del diccionario, con un 0.0 en una columna como unica advertencia.

    `missing` ya era el mecanismo para 'esto lo tiene que decidir un humano'.
    El tipo de desperdicio entra ahi como cualquier otro campo sin dato.
    """
    drafts, _ = draft_observations(EMPATE + ", 30 segundos, 15 veces por turno")
    d = drafts[0]
    assert "waste_type" in d.missing
    assert not d.ready
    assert set(d.tied_wastes) == {"TRANSPORTE", "SOBREPROCESO"}
    # Y sale en el dict que se persiste: un empate que solo vive en memoria es
    # un empate que el revisor no ve.
    assert set(d.to_dict()["tied_wastes"]) == {"TRANSPORTE", "SOBREPROCESO"}


def test_sin_empate_no_se_inventa_ambiguedad():
    """El caso normal no puede pagar el costo del caso ambiguo."""
    assert waste_candidates("el picker camina hasta el rack del fondo") == ("MOVIMIENTO",)

    drafts, _ = draft_observations(
        "el picker camina hasta el rack, 2 minutos, 20 veces al dia"
    )
    d = drafts[0]
    assert d.tied_wastes == ()
    assert "waste_type" not in d.missing
    assert d.ready


def test_texto_sin_desperdicio_no_tiene_candidatos():
    assert waste_candidates("buenos dias, como estas") == ()


def test_clasificacion_funciona_sin_acentos_y_con_ellos():
    a, _ = classify_waste("tengo que ir a buscarlo al otro pasillo")
    b, _ = classify_waste("TENGO QUE IR A BUSCARLO AL OTRO PASILLO")
    assert a == b == "MOVIMIENTO"


# ---------------------------------------------------------------- borradores


TRANSCRITO = (
    "Buenos dias. Mira, lo que mas me atrasa es cuando el sistema me manda a una "
    "ubicacion y no esta el producto, ahi tengo que caminar a buscarlo como 2 minutos, "
    "y pasa unas 20 veces al dia. "
    "Despues en packing la caja que me sugiere no cierra y lo hago de nuevo, son "
    "3 minutos cada vez, unas 15 veces por turno. "
    "Y bueno, a veces me quedo esperando la ola. "
    "Gracias por venir a preguntar."
)


# ------------------------------------------------------------------ cobertura


def test_lo_descartado_queda_declarado_y_no_desaparece():
    """Un enunciado sin desperdicio clasificable se descartaba en silencio.

    `draft_observations` devolvia una lista mas corta y nada mas. No hay forma
    de distinguir "el operario dijo tres cosas y una era cortesia" de "el
    operario dijo tres cosas y el lexico no entiende dos". La primera es
    correcta; la segunda es la herramienta perdiendo el hallazgo que salio a
    buscar, en la mitad exacta del kit donde eso importa.

    Es la regla dura 1 (lo no cuantificado va a una cola con dueno) y la 3 (no
    mentir en silencio). El repo ya lo resolvio para el parser de chat:
    `ChatLog.cobertura()` existe porque "el parser dice 148 mensajes, el humano
    cree que son todos, y las 42 que se cayeron no dejan rastro".
    """
    _, cob = draft_observations(TRANSCRITO)
    assert cob["sin_desperdicio"] >= 1
    assert any("Gracias" in m for m in cob["muestras_sin_desperdicio"])
    assert "SIN CLASIFICAR" in cob["nota"]


def test_la_cobertura_cuadra():
    """La aritmetica cierra o el numero no sirve.

    Sin esta suma, `cobertura` es otro numero que hay que creer. Con ella, un
    enunciado que se caiga por un camino que nadie penso —un split raro, un
    filtro nuevo— aparece como descuadre en vez de evaporarse.
    """
    drafts, cob = draft_observations(TRANSCRITO)
    assert cob["con_borrador"] == len(drafts)
    assert (
        cob["con_borrador"] + cob["sin_desperdicio"] + cob["muy_cortos"]
        == cob["enunciados"]
    )
    assert cob["cuadra"] is True


def test_cuadra_es_falso_cuando_la_suma_no_cierra():
    """`cuadra` tiene que poder dar False, o no esta midiendo nada.

    En la primera version `muy_cortos` se derivaba por resta
    (`len(crudos) - len(items)`), asi que absorbia cualquier enunciado perdido
    y la suma cerraba siempre. Verificado inyectando una fuga que botaba un
    enunciado sin contarlo: `cuadra` seguia en True. Ahora los cortos se cuentan
    directo y este test fija la unica propiedad que hace util al booleano.
    """
    cob = _cobertura(enunciados=10, muy_cortos=1, sin_desperdicio=["x"], borradores=2)
    assert cob["cuadra"] is False


def test_la_cobertura_cuenta_los_fragmentos_muy_cortos():
    """El split tambien descarta, y tambien lo hacia callado.

    `split_utterances` bota todo fragmento de 12 caracteres o menos. Es
    razonable —'Si.', 'Ya.'— pero es un segundo descarte silencioso corriente
    arriba del primero, y no tenerlo contado deja la aritmetica sin cerrar.
    """
    _, cob = draft_observations("Si. No. Ya. El picker camina hasta el rack del fondo.")
    assert cob["muy_cortos"] == 3
    assert cob["enunciados"] == 4
    assert cob["cuadra"] is True


def test_las_muestras_descartadas_salen_anonimizadas():
    """La cobertura se muestra y se persiste: pasa por la misma anonimizacion.

    Un descarte que se declara textual es un canal nuevo por donde el nombre de
    un operador sale del sitio. `anonymize=` tiene que aplicar antes de que el
    texto llegue a la cobertura, no solo antes de que llegue al borrador.
    """
    _, cob = draft_observations(
        "Rodrigo dijo que gracias por venir a preguntar.",
        anonymize=("Rodrigo",),
    )
    todas = " ".join(cob["muestras_sin_desperdicio"])
    assert "Rodrigo" not in todas
    assert "[NOMBRE]" in todas


# ---------------------------------------------------------------- borradores


def test_borradores_extraen_lo_cuantificado():
    drafts, _ = draft_observations(TRANSCRITO, area="Picking", shift="manana")
    listos = [d for d in drafts if d.ready]
    assert len(listos) >= 2

    d = listos[0]
    assert d.observation.waste_type == "MOVIMIENTO"
    assert d.observation.duration_s == pytest.approx(120)
    assert d.observation.frequency_per_shift == pytest.approx(20)
    assert d.observation.impact_h_per_shift == pytest.approx(120 * 20 / 3600)


def test_lo_no_cuantificado_va_a_la_cola_de_revision():
    drafts, _ = draft_observations(TRANSCRITO)
    cola = review_queue(drafts)
    assert cola, "la frase sin numeros debe quedar pendiente"
    assert all(not d.ready for d in cola)
    # Ordenada para que la vuelta al pasillo sea una sola: primero los que solo
    # les falta un dato.
    assert [len(d.missing) for d in cola] == sorted(len(d.missing) for d in cola)


def test_saludos_no_generan_observaciones():
    drafts, cob = draft_observations("Buenos dias. Gracias por venir a preguntar.")
    assert drafts == []
    # Cero borradores, pero no cero enunciados: los dos saludos quedan contados.
    # Que la lista salga vacia no autoriza a decir que el audio estaba vacio.
    assert cob["enunciados"] == 2
    # Y quedan contados por separado, porque cayeron por motivos distintos:
    # 'Buenos dias.' mide 12 caracteres justos y no llega al minimo; 'Gracias
    # por venir a preguntar.' si llega y el lexico no le encuentra desperdicio.
    # Distinguirlos es lo que permite saber si hay que ampliar el lexico o
    # revisar el split.
    assert cob["muy_cortos"] == 1
    assert cob["sin_desperdicio"] == 1
    assert cob["cuadra"] is True


def test_acepta_segmentos_con_timestamp():
    segs = [
        {"start": 0.0, "end": 6.0, "text": "camino a buscarlo como 2 minutos, 20 veces al dia"},
        {"start": 6.0, "end": 9.0, "text": "ok"},
    ]
    drafts, cob = draft_observations(segs)
    assert len(drafts) == 1
    assert drafts[0].start_s == 0.0
    # El segmento 'ok' se descarta por corto, igual que en el camino de texto.
    assert cob["muy_cortos"] == 1
    assert cob["cuadra"] is True


def test_anonimizacion_antes_de_persistir():
    drafts, _ = draft_observations(
        "Rodrigo me dijo que camina a buscarlo 2 minutos, 20 veces al dia.",
        anonymize=("Rodrigo",),
    )
    assert "Rodrigo" not in drafts[0].observation.description
    assert "[NOMBRE]" in drafts[0].observation.description


def test_los_borradores_entran_a_la_sesion_y_al_pareto(tmp_path):
    s = GembaSession(tmp_path / "g.jsonl", site="CD", observer="fde")
    borradores, _ = draft_observations(TRANSCRITO, area="Picking")
    for d in borradores:
        if d.ready:
            s.add(d.observation)

    par = s.pareto()
    assert not par.empty
    assert par["cum_pct"].iloc[-1] == pytest.approx(100.0)
    assert len(GembaSession(tmp_path / "g.jsonl")) == len(s)


def test_split_ignora_fragmentos_muy_cortos():
    assert split_utterances("Si. No. Esta es una frase con contenido real.") == [
        "Esta es una frase con contenido real."
    ]


def test_transcribe_sin_torch_da_mensaje_util(monkeypatch, tmp_path):
    """Si falta el extra, el error tiene que decir que hacer — incluido el
    camino sin instalar nada."""
    import builtins

    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name in ("torch", "transformers"):
            raise ImportError("no module")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    from fdekit.gemba import transcribe

    with pytest.raises(ImportError, match="fde-field-kit\\[audio\\]"):
        transcribe(tmp_path / "x.wav")


# --------------------------------------------------- el prompt de vocabulario
#
# El prompt inicial es lo que hace que 'anden' no salga 'Andem' y 'pallet' no
# salga 'paillet'. Cuando falla, la transcripcion igual sale —y por eso vale
# seguir— pero sale PEOR, y eso hay que decirlo. Regla dura 3.
#
# Estos tres corren sin torch: `_prompt_kwargs` es la capa pura del prompt.


def test_el_prompt_que_falla_deja_aviso_en_vez_de_callarse():
    """El caso que motivo el arreglo: sin red, el processor no carga, y antes
    la transcripcion salia degradada sin que nadie se enterara."""
    from fdekit.gemba.transcribe import _prompt_kwargs

    def se_cae(*a, **k):
        raise RuntimeError("sin red")

    kwargs, aviso, aplicado = _prompt_kwargs(
        "openai/whisper-tiny", ["hueco", "anden"], "cpu", loader=se_cae
    )

    assert kwargs == {}, "sin prompt no se manda prompt_ids a medias"
    assert aplicado is False
    assert "vocabulario" in aviso.lower()
    assert "sin red" in aviso, "el aviso dice POR QUE fallo, no solo que fallo"


def test_sin_vocabulario_no_hay_aviso_porque_no_se_prometio_nada():
    """`None` es 'no se pidio', distinto de `False` que es 'se pidio y fallo'.
    Misma semantica que `in_event_log`."""
    from fdekit.gemba.transcribe import _prompt_kwargs

    kwargs, aviso, aplicado = _prompt_kwargs("openai/whisper-tiny", [], "cpu")

    assert kwargs == {}
    assert aviso == ""
    assert aplicado is None


def test_el_transcript_arranca_sin_avisos_y_sin_promesa_de_vocabulario():
    from fdekit.gemba.transcribe import Transcript

    t = Transcript(text="hola")
    assert t.avisos == []
    assert t.vocabulario_aplicado is None


# ------------------------------------------------------------ audio real
#
# Excluido por defecto: necesita torch, transformers y bajar un modelo.


@pytest.mark.audio
def test_transcribe_devuelve_texto_y_segmentos_de_un_audio_real():
    from fdekit.gemba.transcribe import transcribe as _transcribe

    tr = _transcribe(
        "tests/data/audio_muestra.wav", model_id="openai/whisper-tiny", language="es"
    )

    assert "operario" in tr.text.lower()
    assert len(tr.segments) >= 1
    primero = tr.segments[0]
    # Sin fijar el valor exacto: el chunking de Whisper cambia entre versiones y
    # lo que se prueba aca es el mapeo de `timestamp` a start/end, no el modelo.
    assert primero["start"] is not None and primero["start"] >= 0.0
    assert primero["end"] > primero["start"], "los timestamps tienen que avanzar"
    assert primero["text"]
    assert tr.model == "openai/whisper-tiny"
    assert tr.language == "es"
    assert tr.source.endswith("audio_muestra.wav")
    assert tr.avisos == [], "la ruta feliz no deja avisos"
    assert tr.vocabulario_aplicado is True


@pytest.mark.audio
def test_el_vocabulario_cambia_la_transcripcion_de_verdad():
    """La falsificacion del prompt: si sacarlo no cambia nada, el prompt es
    decorativo y el aviso del test de arriba no vale la pena.

    Medido con whisper-tiny sobre la muestra: con prompt sale 'anden' y
    'pallet'; sin prompt salen 'Andem' y 'paillet'.
    """
    from fdekit.gemba.transcribe import transcribe as _transcribe

    con = _transcribe(
        "tests/data/audio_muestra.wav", model_id="openai/whisper-tiny", language="es"
    )
    sin = _transcribe(
        "tests/data/audio_muestra.wav",
        model_id="openai/whisper-tiny",
        language="es",
        vocabulary=[],
    )

    assert con.text != sin.text
    assert "anden" in con.text.lower()
    assert "anden" not in sin.text.lower()
    assert sin.vocabulario_aplicado is None, "no se pidio vocabulario, no fallo"


@pytest.mark.audio
def test_transcribe_to_session_entrega_los_avisos_al_que_llama(tmp_path):
    """El aviso tiene que llegar hasta el que decide, no morir en el Transcript:
    si el vocabulario fallo, TODOS estos borradores salieron de texto degradado.
    """
    from fdekit.gemba import GembaSession
    from fdekit.gemba.transcribe import transcribe_to_session

    s = GembaSession(tmp_path / "g.jsonl", observer="ana")
    added, pendientes, avisos, cobertura = transcribe_to_session(
        "tests/data/audio_muestra.wav",
        s,
        area="picking",
        model_id="openai/whisper-tiny",
        language="es",
    )

    assert isinstance(avisos, list)
    assert avisos == [], "ruta feliz: nada que declarar"
    assert len(added) + len(pendientes) >= 1

    # La cobertura viaja por el mismo camino que los avisos y por la misma
    # razon: sin denominador, "se agregaron N observaciones" se lee como "el
    # audio tenia N". Con audio real es donde mas importa, porque ahi los
    # enunciados que el lexico no entiende son de verdad y no de laboratorio.
    assert cobertura["con_borrador"] == len(added) + len(pendientes)
    assert cobertura["cuadra"] is True
