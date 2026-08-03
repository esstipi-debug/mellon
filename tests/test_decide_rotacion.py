"""H9 — el actor que no estuvo: onboarding, rotacion y compromisos huerfanos.

Tres personas concretas, ninguna con ruta en el diseno original:

**El que se incorpora en la semana 10.** Necesita "que esta decidido, en que
orden, que sigue vivo, que supuestos sostienen todo". Es una consulta sobre
datos que ya existen, y es el unico artefacto que un recien llegado va a leer
entero.

**El que se va.** La rotacion de FDE y de contraparte es la norma, no la
excepcion. Sin ruta, a los seis meses una fraccion alta del registro apunta a
gente que ya no esta y el registro se vuelve ruido.

**El ejecutor de piso.** Supervisor de turno noche que tiene que ejecutar la
decision, no estuvo en ninguna reunion y no lee correo durante el turno. El
output del sistema es markdown en git: el canal de entrega es un hueco total.
"""

from datetime import date, timedelta

import pytest

from fdekit.decide import (
    Assumption,
    Commitment,
    Consent,
    DecideStore,
    Decision,
    Meeting,
    OpenQuestion,
)
from fdekit.decide.eventlog import build_event_log
from fdekit.decide.rotacion import (
    onboarding_brief,
    reassign_owner,
    tarjeta_de_piso,
    duenos_huerfanos,
)

HOY = date(2026, 8, 1)
ROSTER = ("Marcela Perez", "Fabian Soto", "Rodrigo Munoz")


@pytest.fixture
def store(tmp_path):
    st = DecideStore(tmp_path / "decide")
    st.add_meeting(Meeting(
        id="m1", date=date(2026, 3, 2), roster=ROSTER, facilitator="Marcela Perez",
        consent=Consent(True, "Marcela Perez", "interes_legitimo"), scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Reslotear la clase A a la zona dorada del CD Pudahuel",
        owner="Marcela Perez", date_decided=date(2026, 3, 2),
        criteria="distancia media bajo 35 m antes del 30-09",
        rationale="el 69% de las visitas son clase A", meeting_id="m1", scope="pudahuel",
    ))
    st.add_decision(Decision(
        id="", statement="Consolidar el picking en dos olas diarias",
        owner="Fabian Soto", date_decided=date(2026, 4, 6),
        criteria="2 olas a mas tardar el 30-09", rationale="habia cuatro y se pisaban",
        meeting_id="m1", scope="pudahuel", depends_on=["D-001"],
    ))
    st.add_commitment(Commitment(
        id="", decision_id="D-001", what="mover 200 ubicaciones del pasillo 3",
        owner="Rodrigo Munoz", due=date(2026, 9, 1),
        evidence_of_done="reporte del WMS", meeting_id="m1",
    ))
    st.add_assumption(Assumption(
        id="", decision_id="D-001", statement="el layout no cambia hasta septiembre",
        check_by=date(2026, 9, 1), source="jefe de operaciones", meeting_id="m1",
    ))
    return st


# ------------------------------------------------- el que se incorpora


def test_el_brief_ordena_las_decisiones_por_dependencia(store):
    """"Que esta decidido, EN QUE ORDEN". Una lista plana por fecha obliga al
    recien llegado a reconstruir solo por que existe cada decision, que es
    exactamente el trabajo que el brief tiene que ahorrarle."""
    b = onboarding_brief(store, "pudahuel", today=HOY)
    ids = [d["id"] for d in b["decisiones"]]
    assert ids.index("D-001") < ids.index("D-002")
    assert b["decisiones"][1]["depende_de"] == ["D-001"]


def test_el_brief_dice_la_edad_de_cada_supuesto(store):
    """Un supuesto de hace cinco meses y uno de la semana pasada sostienen la
    misma decision con confianza muy distinta, y el recien llegado no tiene
    forma de saber cual es cual."""
    b = onboarding_brief(store, "pudahuel", today=HOY)
    a = b["supuestos"][0]
    assert a["id"] == "A-001"
    assert a["edad_dias"] == (HOY - date(2026, 3, 2)).days


def test_el_brief_no_incluye_lo_muerto(store):
    """Leer una decision revertida como vigente es peor que no leer nada."""
    d = store.get("D-002")
    d.status = "REVERTIDA"
    store.save(d)
    b = onboarding_brief(store, "pudahuel", today=HOY)
    assert [x["id"] for x in b["decisiones"]] == ["D-001"]


def test_el_brief_se_acota_por_scope(store):
    """Un CD no es otro. Sin el filtro, el brief del que llega a Pudahuel trae
    tres anos de Quilicura."""
    d = store.get("D-002")
    d.scope = "quilicura"
    store.save(d)
    b = onboarding_brief(store, "pudahuel", today=HOY)
    assert [x["id"] for x in b["decisiones"]] == ["D-001"]
    assert "quilicura" in b["nota"] or b["fuera_de_scope"] == 1


def test_el_brief_declara_lo_que_no_muestra(store):
    """Misma doctrina que `Coverage`: nombra primero lo que dejo afuera. Un
    brief que se lee como completo y no lo es le da al recien llegado la peor
    confianza posible."""
    b = onboarding_brief(store, "pudahuel", today=HOY)
    assert "no es" in b["nota"].lower() or "no incluye" in b["nota"].lower()
    assert b["cobertura"]["decisiones_en_disco"] >= len(b["decisiones"])


def test_el_brief_marca_lo_que_no_es_auditable(store):
    """Una sembrada y una decidida en sala no valen lo mismo, y el que llega es
    justo el que no puede distinguirlas por contexto."""
    store.add_decision(Decision(
        id="", statement="El corte de pedidos del CD Pudahuel es a las 14:00",
        owner="Marcela Perez", date_decided=date(2026, 3, 1),
        criteria="100% cortados antes de las 14:00", rationale="el transporte sale 15:00",
        meeting_id="m1", scope="pudahuel", origen="SIEMBRA",
    ))
    b = onboarding_brief(store, "pudahuel", today=HOY)
    sembrada = next(d for d in b["decisiones"] if d["id"] == "D-003")
    assert sembrada["auditable"] is False
    assert sembrada["origen"] == "SIEMBRA"


# ---------------------------------------------------------- el que se va


def test_reasignar_mueve_todo_lo_vivo_de_una_persona(store):
    r = reassign_owner(store, "Rodrigo Munoz", "Fabian Soto", today=HOY, apply=True)
    assert r["applied"] is True
    assert store.get("C-001").owner == "Fabian Soto"
    assert "C-001" in r["reasignados"]


def test_sin_apply_es_solo_el_reporte(store):
    """Mismo contrato que `supersede`: mirar no cambia nada."""
    r = reassign_owner(store, "Rodrigo Munoz", "Fabian Soto", today=HOY)
    assert r["applied"] is False
    assert store.get("C-001").owner == "Rodrigo Munoz"
    assert "C-001" in r["reasignados"]


def test_reasignar_no_toca_lo_muerto(store):
    """Un compromiso CUMPLIDO lo cumplio quien lo cumplio. Reasignarlo reescribe
    quien hizo el trabajo."""
    c = store.get("C-001")
    c.status = "CUMPLIDO"
    store.save(c)
    r = reassign_owner(store, "Rodrigo Munoz", "Fabian Soto", today=HOY, apply=True)
    assert store.get("C-001").owner == "Rodrigo Munoz"
    assert "C-001" in r["intactos"]


def test_reasignar_deja_rastro_pero_no_inventa_un_evento_del_ciclo_de_vida(store):
    """La trampa: `HIST_RE` convierte cualquier token en MAYUSCULAS del historial
    en una actividad del event log. Escribir 'REASIGNADA:' agrega una actividad
    a `variants`, cambia `touches_to_decide` y por lo tanto **corre la linea base
    del XmR**, cuyos limites la regla 6 exige congelados. Y nadie lo ve: los
    numeros siguen saliendo."""
    antes = set(build_event_log(store).df["activity"])
    reassign_owner(store, "Marcela Perez", "Fabian Soto", today=HOY, apply=True)

    hist = " ".join(store.get("D-001").historial_statements)
    assert "Marcela Perez" in hist and "Fabian Soto" in hist
    assert set(build_event_log(store).df["activity"]) == antes


def test_reasignar_a_alguien_que_no_esta_en_ningun_roster_se_niega(store):
    """El roster es el scope lexico del sistema. Reasignar a un nombre que no
    existe cambia un dueno real por uno inventado, y todo lo que cuelga queda
    apuntando a nadie — que es peor que el problema que se venia a resolver."""
    with pytest.raises(ValueError, match="roster"):
        reassign_owner(store, "Rodrigo Munoz", "Quien Sea", today=HOY, apply=True)


def test_el_barrido_encuentra_lo_que_apunta_a_gente_que_ya_no_esta(store):
    """A los seis meses una fraccion alta del registro apunta a gente que se
    fue. Sin barrido no hay forma de verlo hasta que alguien pregunta por algo
    y no hay a quien preguntarle."""
    h = duenos_huerfanos(store, activos=("Marcela Perez", "Fabian Soto"), today=HOY)
    assert h["huerfanos"]["Rodrigo Munoz"] == ["C-001"]
    assert h["total"] == 1


def test_el_barrido_no_cuenta_lo_muerto(store):
    c = store.get("C-001")
    c.status = "CANCELADO"
    store.save(c)
    h = duenos_huerfanos(store, activos=("Marcela Perez", "Fabian Soto"), today=HOY)
    assert h["total"] == 0


# ------------------------------------------------------ el ejecutor de piso


def test_la_tarjeta_de_piso_cabe_en_tres_lineas(store):
    """El supervisor de turno noche no estuvo en la reunion y no lee correo
    durante el turno. Si no cabe en un mensaje, no llega."""
    t = tarjeta_de_piso(store, "C-001")
    assert len(t.splitlines()) <= 3
    assert "C-001" in t
    assert "2026-09-01" in t
    assert "reporte del WMS" in t


def test_la_tarjeta_dice_por_que_y_no_solo_que(store):
    """Un compromiso sin su decision es una orden. El ejecutor de piso es el que
    mas necesita el porque y el que menos acceso tiene a el."""
    t = tarjeta_de_piso(store, "C-001")
    assert "clase A" in t or "69%" in t


def test_la_tarjeta_no_nombra_a_nadie_que_no_sea_el_dueno(store):
    """H14: el dueno es la unica persona nombrable, porque su nombre es
    constitutivo de la obligacion. La tarjeta sale del sistema hacia un canal
    sin control (WhatsApp, la hoja de trabajo), asi que es justo donde un
    tercero mencionado deja de ser reversible."""
    d = store.get("D-001")
    d.rationale = "el 69% de las visitas son clase A y Fabian Soto no da abasto"
    store.save(d)
    t = tarjeta_de_piso(store, "C-001")
    assert "Fabian Soto" not in t
    assert "Rodrigo Munoz" in t


def test_la_tarjeta_de_un_compromiso_corrido_lo_dice(store):
    """Mandar la fecha nueva sin decir que es la tercera deja al ejecutor de
    piso como el unico del sistema que no sabe que esto viene corriendo."""
    from fdekit.decide.query import slip

    slip(store, "C-001", date(2026, 10, 1), motivo="el proveedor movio la entrega",
         por="Rodrigo Munoz", today=HOY)
    t = tarjeta_de_piso(store, "C-001")
    assert "1a vez" in t or "corrida" in t
