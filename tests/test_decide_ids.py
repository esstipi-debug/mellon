"""H12c — colision de IDs offline y multi-FDE.

Dos personas trabajando sin red sobre la misma cuenta asignan `D-041` las dos, y
el conflicto no aparece hasta el merge — cuando ya hay compromisos, supuestos y
alias colgando de los dos `D-041` distintos. Un archivo de lock no lo resuelve:
sin filesystem compartido no hay lock que valga.

La forma barata es que el ID lleve al autor. Trivial ahora, doloroso despues:
renombrar 200 decisiones significa reescribir a mano cada `depends_on`,
`supersedes`, `blocks`, `decision_id` y `symbol_id` del registro.

El default sigue siendo `D-001`: sin autor declarado nada cambia, porque el caso
de un solo FDE es el normal y meterle un prefijo seria ruido permanente.
"""

from datetime import date

import pytest

from fdekit.decide import (
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
    implementations,
)
from fdekit.decide.resolve import resolve

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


def _meeting(st):
    st.add_meeting(Meeting(
        id="m1", date=HOY, roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"), scope="pudahuel",
    ))


def _dec(st, n=1, **kw):
    return st.add_decision(Decision(
        id="", statement=f"Reslotear la clase A a la zona dorada, tanda {n}",
        owner="Marcela Perez", date_decided=HOY, criteria="antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1",
        scope="pudahuel", slots={"proceso": "slotting"}, **kw,
    ))


# ------------------------------------------------- el default no cambia


def test_sin_autor_los_ids_son_los_de_siempre(tmp_path):
    """El caso de un solo FDE es el normal. Meterle un prefijo seria ruido
    permanente para el 90% de los proyectos."""
    st = DecideStore(tmp_path / "d")
    _meeting(st)
    assert _dec(st).id == "D-001"
    assert _dec(st, 2).id == "D-002"


# --------------------------------------------------- con autor declarado


def test_el_autor_entra_en_el_id(tmp_path):
    st = DecideStore(tmp_path / "d", autor="JM")
    _meeting(st)
    assert _dec(st).id == "D-JM-001"


def test_dos_autores_no_colisionan_en_el_mismo_registro(tmp_path):
    """El caso entero. Los dos trabajaron sin red y los dos escribieron su
    primera decision; al juntar los arboles tienen que convivir."""
    raiz = tmp_path / "d"
    jm = DecideStore(raiz, autor="JM")
    _meeting(jm)
    a = _dec(jm, 1)

    ar = DecideStore(raiz, autor="AR")
    b = _dec(ar, 2)

    assert a.id == "D-JM-001"
    assert b.id == "D-AR-001"
    assert {d.id for d in DecideStore(raiz).decisions()} == {"D-JM-001", "D-AR-001"}


def test_cada_autor_lleva_su_propia_serie(tmp_path):
    """Si la serie fuera global, el segundo autor arrancaria en 002 y el numero
    dejaria de decir cuantas escribio el."""
    raiz = tmp_path / "d"
    jm = DecideStore(raiz, autor="JM")
    _meeting(jm)
    _dec(jm, 1), _dec(jm, 2), _dec(jm, 3)
    assert _dec(DecideStore(raiz, autor="AR"), 4).id == "D-AR-001"
    assert _dec(jm, 5).id == "D-JM-004"


def test_el_autor_se_valida(tmp_path):
    """Un autor con guiones parte el ID en pedazos y `get` deja de encontrarlo.
    Es la clase de dato que entra una vez y rompe el registro entero."""
    for malo in ("j-m", "JM-", "j m", "JOTAEME", "1", "J"):
        with pytest.raises(ValueError, match="autor"):
            DecideStore(tmp_path / "d", autor=malo)


# ------------------------------------ el ID compuesto tiene que servir


def test_se_puede_leer_de_vuelta(tmp_path):
    st = DecideStore(tmp_path / "d", autor="JM")
    _meeting(st)
    d = _dec(st)
    assert st.get("D-JM-001").statement == d.statement


def test_lo_que_cuelga_apunta_bien(tmp_path):
    """`decision_id` con el ID compuesto tiene que resolver, o los compromisos
    quedan huerfanos en silencio."""
    st = DecideStore(tmp_path / "d", autor="JM")
    _meeting(st)
    _dec(st)
    c = st.add_commitment(Commitment(
        id="", decision_id="D-JM-001", what="mover 200 ubicaciones del pasillo 3",
        owner="Rodrigo Munoz", due=date(2026, 9, 1),
        evidence_of_done="reporte del WMS", meeting_id="m1",
    ))
    assert c.id == "C-JM-001"
    assert [x.id for x in implementations(st, "D-JM-001")] == ["C-JM-001"]


def test_el_resolutor_reconoce_el_id_compuesto(tmp_path):
    """L0 son las anclas duras: un ID literal en la frase resuelve
    deterministico. Si el regex no lo reconoce, la capa mas barata y mas segura
    del resolutor deja de funcionar justo para los registros multi-FDE."""
    st = DecideStore(tmp_path / "d", autor="JM")
    _meeting(st)
    _dec(st)
    r = resolve("como quedo D-JM-001", st, st.get_meeting("m1"))
    assert (r.symbol_id, r.tier, r.layer) == ("D-JM-001", "EXTRACTED", "L0")


def test_el_id_simple_sigue_resolviendo(tmp_path):
    """La extension del regex no puede romper el caso comun."""
    st = DecideStore(tmp_path / "d")
    _meeting(st)
    _dec(st)
    for superficie in ("como quedo D-001", "lo de D001"):
        assert resolve(superficie, st, st.get_meeting("m1")).symbol_id == "D-001"


def test_el_export_no_se_rompe_con_el_id_compuesto(tmp_path):
    """`to_graphify` parte el ID por el guion para sacar el tipo de nodo."""
    from fdekit.decide.export import to_graphify

    st = DecideStore(tmp_path / "d", autor="JM")
    _meeting(st)
    _dec(st)
    g = to_graphify(st)
    nodo = next(n for n in g["nodes"] if n["id"] == "D-JM-001")
    assert nodo["type"] == "Decision"
