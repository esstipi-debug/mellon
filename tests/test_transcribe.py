"""Tests de la capa que NO depende de torch.

La logica de extraccion vive completa en Python puro justamente para poder
testearla. Lo unico sin cobertura es la llamada a Whisper — y esa se prueba con
un audio real en terreno, no con un mock que solo verifica que se llamo a una
funcion.
"""

import pytest

from fdekit.gemba import (
    GembaSession,
    classify_waste,
    draft_observations,
    parse_duration_s,
    parse_frequency_per_shift,
    review_queue,
)
from fdekit.gemba.transcribe import parse_operators, split_utterances, strip_accents


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


def test_borradores_extraen_lo_cuantificado():
    drafts = draft_observations(TRANSCRITO, area="Picking", shift="manana")
    listos = [d for d in drafts if d.ready]
    assert len(listos) >= 2

    d = listos[0]
    assert d.observation.waste_type == "MOVIMIENTO"
    assert d.observation.duration_s == pytest.approx(120)
    assert d.observation.frequency_per_shift == pytest.approx(20)
    assert d.observation.impact_h_per_shift == pytest.approx(120 * 20 / 3600)


def test_lo_no_cuantificado_va_a_la_cola_de_revision():
    drafts = draft_observations(TRANSCRITO)
    cola = review_queue(drafts)
    assert cola, "la frase sin numeros debe quedar pendiente"
    assert all(not d.ready for d in cola)
    # Ordenada para que la vuelta al pasillo sea una sola: primero los que solo
    # les falta un dato.
    assert [len(d.missing) for d in cola] == sorted(len(d.missing) for d in cola)


def test_saludos_no_generan_observaciones():
    drafts = draft_observations("Buenos dias. Gracias por venir a preguntar.")
    assert drafts == []


def test_acepta_segmentos_con_timestamp():
    segs = [
        {"start": 0.0, "end": 6.0, "text": "camino a buscarlo como 2 minutos, 20 veces al dia"},
        {"start": 6.0, "end": 9.0, "text": "ok"},
    ]
    drafts = draft_observations(segs)
    assert len(drafts) == 1
    assert drafts[0].start_s == 0.0


def test_anonimizacion_antes_de_persistir():
    drafts = draft_observations(
        "Rodrigo me dijo que camina a buscarlo 2 minutos, 20 veces al dia.",
        anonymize=("Rodrigo",),
    )
    assert "Rodrigo" not in drafts[0].observation.description
    assert "[NOMBRE]" in drafts[0].observation.description


def test_los_borradores_entran_a_la_sesion_y_al_pareto(tmp_path):
    s = GembaSession(tmp_path / "g.jsonl", site="CD", observer="fde")
    for d in draft_observations(TRANSCRITO, area="Picking"):
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
