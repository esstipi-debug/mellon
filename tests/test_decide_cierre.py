"""H15 — propiedad, salida y uso punitivo del registro.

Tres huecos que nadie toco y que se pagan al final, cuando ya no se pueden
arreglar:

**De quien es el registro al cierre.** Contiene datos comerciales del cliente
—volumenes, tarifas, proveedores— y probablemente esta cubierto por el NDA.
Guardarlo en el repo del FDE puede ser incumplimiento. Se define en el kickoff,
no en la ultima semana.

**Uso punitivo.** El dia que el registro de compromisos se usa en una evaluacion
de desempeno, la gente deja de declarar decisiones y el sistema muere en dos
semanas **sin ninguna senal tecnica**. No hay control tecnico que lo impida:
solo que la forma de la salida no lo invite y que la norma este escrita.

**Egreso de datos.** El paso de extraccion es la ruta de salida del transcripto
del cliente que ninguna propuesta declaro. O el clasificador es 100% lexico y
determinista, o hay que declarar el egreso y pedir autorizacion. Aca es lexico,
y eso deja de ser una promesa en un documento para ser una propiedad del codigo.
"""

import json
from datetime import date

import pytest

from fdekit.decide import (
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
)
from fdekit.decide.cierre import entregar, lo_que_conserva_el_fde
from fdekit.decide.transcript import TranscriptStore

HOY = date(2026, 12, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")

SEGMENTOS = [
    {"start": 0.0, "end": 6.0, "text": "Buenos dias, gracias por venir."},
    {"start": 6.0, "end": 24.0, "text":
        "Queda decidido: reslotear la clase A a la zona dorada del CD Pudahuel."},
]


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=date(2026, 3, 2), roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo",
                        recording_allowed=True, retention_days=90),
        scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=date(2026, 3, 2),
        criteria="distancia media bajo 35 m antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1", scope="pudahuel",
    ))
    st.add_commitment(Commitment(
        id="", decision_id="D-001", what="mover 200 ubicaciones del pasillo 3",
        owner="Rodrigo Munoz", due=date(2026, 9, 1),
        evidence_of_done="reporte del WMS", meeting_id="m1",
    ))
    TranscriptStore(st.root, "m1").ingest_segments(SEGMENTOS)
    return st


# --------------------------------------------------------- la entrega


def test_sin_confirmar_no_destruye_nada(store, tmp_path):
    """Mismo contrato que `supersede`: mirar no cambia nada. Y aca importa mas
    que en ningun otro lado, porque lo que se destruye no vuelve."""
    r = entregar(store, tmp_path / "entrega", today=HOY, por="Marcela Perez")
    assert r["applied"] is False
    assert TranscriptStore(store.root, "m1").exists()
    assert "no se destruyo nada" in r["nota"]


def test_la_entrega_se_escribe_antes_de_destruir(store, tmp_path):
    """El orden es la garantia entera. Destruir primero y fallar al escribir
    deja al cliente sin registro y sin canal HABLADA, y no hay vuelta atras."""
    destino = tmp_path / "entrega"
    r = entregar(store, destino, today=HOY, por="Marcela Perez", apply=True)

    assert r["applied"] is True
    assert (destino / "registro.html").exists()
    assert (destino / "registro.md").exists()
    assert "Reslotear la clase A" in (destino / "registro.md").read_text(encoding="utf-8")
    assert not TranscriptStore(store.root, "m1").exists()


def test_si_la_entrega_no_se_puede_escribir_no_se_destruye(store, tmp_path):
    """La condicion que hace segura a la operacion. Si el destino no se puede
    escribir, el canal HABLADA tiene que seguir donde estaba."""
    ocupado = tmp_path / "ocupado"
    ocupado.write_text("no soy un directorio", encoding="utf-8")

    with pytest.raises((OSError, ValueError)):
        entregar(store, ocupado, today=HOY, por="Marcela Perez", apply=True)
    assert TranscriptStore(store.root, "m1").exists()


def test_la_destruccion_deja_constancia_de_que_se_destruyo(store, tmp_path):
    """Sin constancia, 'se destruyo' es la palabra del FDE contra la nada. La
    constancia prueba QUE se destruyo sin conservarlo: el sha coincide con el
    `transcript_sha256` de las anclas que lo citaban."""
    sha_antes = TranscriptStore(store.root, "m1").sha256()
    destino = tmp_path / "entrega"
    entregar(store, destino, today=HOY, por="Marcela Perez", apply=True)

    acta = json.loads((destino / "constancia-destruccion.json").read_text(encoding="utf-8"))
    assert acta["por"] == "Marcela Perez"
    assert acta["fecha"] == HOY.isoformat()
    assert acta["sesiones_destruidas"][0]["meeting_id"] == "m1"
    assert acta["sesiones_destruidas"][0]["sha256_al_destruir"] == sha_antes


def test_el_canal_DECIDIDA_sobrevive_a_la_destruccion(store, tmp_path):
    """La cita se copio, no se enlazo. Esa decision de diseno es justo lo que
    hace posible entregar un registro legible y destruir el habla el mismo dia."""
    entregar(store, tmp_path / "entrega", today=HOY, por="Marcela Perez", apply=True)
    assert store.get("D-001").statement.startswith("Reslotear")
    assert len(store.decisions()) == 1


def test_la_entrega_se_niega_si_queda_cola_sin_revisar(store, tmp_path):
    """Cerrar con borradores vivos destruye el habla de la que salieron y deja
    la cola apuntando a una fuente que ya no existe. Es exactamente el hueco
    que no se puede arreglar despues."""
    from fdekit.decide.draft import DraftStore, draft_decisions

    drafts = draft_decisions(
        "Queda decidido: bajar el corte de pedidos a las 13:00.",
        ROSTER, date(2026, 3, 2), meeting_id="m1",
    )
    DraftStore(store.root, "m1").append(drafts)

    with pytest.raises(ValueError, match="cola"):
        entregar(store, tmp_path / "entrega", today=HOY, por="Marcela Perez", apply=True)
    assert TranscriptStore(store.root, "m1").exists()


# ----------------------------------------------------- lo que se lleva el FDE


def test_el_fde_no_se_lleva_nada_del_cliente(store, tmp_path):
    """Volumenes, tarifas, proveedores y nombres son del cliente y estan bajo
    NDA. Lo unico que el FDE puede conservar son sus propios patrones."""
    q = lo_que_conserva_el_fde(store)
    texto = json.dumps(q, ensure_ascii=False)
    for prohibido in ("Marcela Perez", "Rodrigo Munoz", "Pudahuel", "pudahuel",
                      "200 ubicaciones", "D-001"):
        assert prohibido not in texto


def test_lo_que_conserva_el_fde_es_util_igual(store):
    """Si no queda nada aprovechable, la clausula se incumple en silencio la
    primera vez que a alguien le sirve un dato."""
    q = lo_que_conserva_el_fde(store)
    assert q["decisiones"] == 1
    assert q["compromisos"] == 1
    assert q["marcadores_del_lexico"]


# ----------------------------------------------------------- uso punitivo


def test_la_entrega_lleva_la_norma_escrita(store, tmp_path):
    """La norma no sirve si vive en un documento aparte que nadie abre: viaja
    con lo que se entrega."""
    destino = tmp_path / "entrega"
    entregar(store, destino, today=HOY, por="Marcela Perez", apply=True)
    md = (destino / "registro.md").read_text(encoding="utf-8")
    assert "desempeno" in md.lower()
    assert "por decision" in md.lower()


def test_el_markdown_agrupa_por_decision_y_no_por_persona(store, tmp_path):
    """Misma regla que la pagina HTML, y por el mismo motivo: esto se lee fuera
    del equipo."""
    store.add_commitment(Commitment(
        id="", decision_id="D-001", what="reetiquetar las ubicaciones movidas",
        owner="Rodrigo Munoz", due=date(2026, 9, 15),
        evidence_of_done="foto del pasillo", meeting_id="m1",
    ))
    destino = tmp_path / "entrega"
    entregar(store, destino, today=HOY, por="Marcela Perez", apply=True)
    md = (destino / "registro.md").read_text(encoding="utf-8")

    bloque = md.split("## ")[1]
    assert "C-001" in bloque and "C-002" in bloque


# ------------------------------------------------------------ egreso de datos


def test_la_extraccion_no_sale_de_la_maquina(store):
    """El unico hueco de H15 que se puede volver una propiedad del codigo en vez
    de una promesa en un documento.

    Los enfoques del estudio proponian "un LLM sobre una ventana de segmentos"
    para extraer decisiones. Whisper es local; ese paso probablemente no. Es una
    ruta de salida del transcripto del cliente que ninguna propuesta declaro.

    Aca el clasificador es 100% lexico y determinista, y esto lo fija: ningun
    modulo de `decide` puede abrir una conexion.
    """
    import ast
    from pathlib import Path

    prohibidos = {
        "requests", "httpx", "urllib", "urllib3", "http", "socket", "aiohttp",
        "openai", "anthropic", "transformers", "torch", "boto3",
    }
    raiz = Path(__file__).resolve().parent.parent / "src" / "fdekit" / "decide"
    ofensores = []
    for py in sorted(raiz.glob("*.py")):
        arbol = ast.parse(py.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [n.name for n in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            for n in nombres:
                if n.split(".")[0] in prohibidos:
                    ofensores.append(f"{py.name}: {n}")

    assert ofensores == [], (
        "un modulo de `decide` importa algo que puede sacar datos de la maquina: "
        f"{ofensores}. El transcripto del cliente no sale de aca, y eso es una "
        "propiedad del codigo, no una promesa en un documento."
    )
