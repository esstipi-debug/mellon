"""Tests de canalizacion de dudas (3 vias), reconciliacion Granola y ROI."""

from datetime import date, datetime, timezone

from fdekit.decide.granola import (
    VIA_1_CITA_DOCUMENTO,
    VIA_2_LAGUNA_DRI,
    VIA_3_LLAMADA_QUIRURGICA,
    DocumentChunkACL,
    DoubtItem,
    compute_interception_roi,
    reconcile_granola_session,
    triage_doubt,
)


def _corpus_pudahuel() -> list[DocumentChunkACL]:
    todos = frozenset({"FDE", "Camila", "Rodrigo", "Andres"})
    solo_gerencia = frozenset({"FDE", "Gerente"})
    return [
        DocumentChunkACL(
            doc_id="out/A3.md",
            section_ref="sec-2",
            text="Datos maestros: 25.2% de SKUs con defecto dimensional y desvio mediano de 150.7%.",
            acl_principals=todos,
        ),
        DocumentChunkACL(
            doc_id="out/A3.md",
            section_ref="sec-4",
            text="La espera dominante es de cola en ORDER_RELEASED a PICK con 707.23h acumuladas.",
            acl_principals=todos,
        ),
        DocumentChunkACL(
            doc_id="confidencial/bonos.md",
            section_ref="sec-1",
            text="El presupuesto confidencial del turno domingo de auditoria es de 15000 dolares.",
            acl_principals=solo_gerencia,
        ),
    ]


def test_via_1_responde_con_cita_del_reporte_y_cero_reunion():
    chunks = _corpus_pudahuel()
    duda = DoubtItem(
        id="D-01",
        author="Camila",
        text="Que porcentaje de SKUs tiene defecto dimensional en los datos maestros?",
    )
    res = triage_doubt(
        doubt=duda,
        chunks=chunks,
        recipient_ids=("FDE", "Camila", "Rodrigo", "Andres"),
        dri_user_id="FDE",
    )
    assert res.route == VIA_1_CITA_DOCUMENTO
    assert res.meeting_minutes == 0
    assert res.abstained is False
    assert "25.2%" in res.exact_quote
    assert res.source_ref == "out/A3.md:sec-2"


def test_cero_fugas_acl_nunca_cita_chunk_restringido_y_se_abstiene():
    chunks = _corpus_pudahuel()
    # Pregunta especificamente por el contenido del documento confidencial, pero
    # en un canal donde estan Camila y Rodrigo (que no tienen ACL sobre bonos.md).
    duda = DoubtItem(
        id="D-02",
        author="Rodrigo",
        text="Cual es el presupuesto confidencial del turno domingo de auditoria?",
    )
    res = triage_doubt(
        doubt=duda,
        chunks=chunks,
        recipient_ids=("FDE", "Camila", "Rodrigo", "Andres"),
        dri_user_id="FDE",
    )
    assert res.acl_filtered_out == 1
    assert res.route == VIA_2_LAGUNA_DRI
    assert res.abstained is True
    assert res.exact_quote == ""
    assert "15000" not in res.exact_quote
    assert res.required_attendees == ("FDE",)
    assert res.meeting_minutes == 0


def test_via_3_desacuerdo_agenda_llamada_quirurgica_15m_solo_con_involucrados():
    chunks = _corpus_pudahuel()
    duda = DoubtItem(
        id="D-03",
        author="Andres",
        text="No estoy de acuerdo con mover la dotacion antes de limpiar el maestro, prefiero secuenciar.",
    )
    res = triage_doubt(
        doubt=duda,
        chunks=chunks,
        recipient_ids=("FDE", "Camila", "Rodrigo", "Andres"),
        dri_user_id="FDE",
    )
    assert res.route == VIA_3_LLAMADA_QUIRURGICA
    assert res.meeting_minutes == 15
    assert res.required_attendees == ("Andres", "FDE")


def test_reconciliacion_granola_cierra_dudas_y_promueve_no_respondidas():
    dudas_slack = [
        DoubtItem(
            id="D-01",
            author="Andres",
            text="Corremos primero la auditoria de SKUs Clase A o el cambio de dotacion?",
        ),
        DoubtItem(
            id="D-02",
            author="Rodrigo",
            text="En que ventana horaria del domingo se mide la muestra fisica?",
        ),
    ]
    segmentos_audio = [
        {
            "start": 192.0,
            "end": 205.0,
            "text": (
                "Queda decidido: correr primero la auditoria de SKUs Clase A, dueno FDE, "
                "antes del 2026-10-25, porque elimina el reproceso de carton."
            ),
        },
        {
            "start": 465.0,
            "end": 478.0,
            "text": "Andres se compromete a reasignar cuatro operarios al turno pico antes del 2026-10-30.",
        },
    ]
    now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    rec = reconcile_granola_session(
        skeleton_doubts=dudas_slack,
        text_or_segments=segmentos_audio,
        roster=("FDE", "Andres", "Rodrigo"),
        meeting_date=date(2026, 10, 16),
        meeting_id="quirurgica-pudahuel-01",
        now=now,
    )
    cob = rec.cobertura()
    assert cob["cuadra"] is True
    assert cob["total_dudas_agenda"] == 2
    assert cob["resueltas_en_audio"] == 1
    assert cob["promovidas_a_pregunta_abierta"] == 1
    assert rec.resolved_doubt_ids == ("D-01",)
    assert rec.unanswered_doubt_ids == ("D-02",)

    # La duda D-02 que nadie respondio en los 15 minutos no desaparece:
    # queda promovida a DecisionDraft(kind="question").
    preguntas = [d for d in rec.drafts if d.kind == "question"]
    assert len(preguntas) == 1
    assert "duda_agenda_sin_respuesta:D-02" in preguntas[0].notes


def test_contraste_economico_20_usd_hora_y_bloque_de_foco_recuperado():
    # Caso 1: Reunion de 1 hora, 8 personas a 20 USD/h vs video de 2 min
    roi_1h = compute_interception_roi(
        attendees_count=8,
        scheduled_hours=1.0,
        hourly_rate_usd=20.0,
        video_minutes=2.0,
        vote_overhead_minutes=1.0,
    )
    assert roi_1h["gross_sync_cost_usd"] == 160.0
    assert roi_1h["total_async_cost_usd"] == 8.15
    assert roi_1h["net_saved_usd"] == 151.85
    assert roi_1h["defended_focus_minutes_per_person"] == 55
    assert roi_1h["cuadra"] is True

    # Caso 2: Reunion de 3 horas, 8 personas a 20 USD/h vs video de 2 min + llamada quirurgica (3 pers, 15m)
    roi_3h_surg = compute_interception_roi(
        attendees_count=8,
        scheduled_hours=3.0,
        hourly_rate_usd=20.0,
        video_minutes=2.0,
        vote_overhead_minutes=1.0,
        surgical_call_attendees=3,
        surgical_call_minutes=15.0,
    )
    assert roi_3h_surg["gross_sync_cost_usd"] == 480.0
    assert roi_3h_surg["total_async_cost_usd"] == 23.15
    assert roi_3h_surg["net_saved_usd"] == 456.85
    assert roi_3h_surg["defended_focus_minutes_per_person"] == 175
    assert roi_3h_surg["cuadra"] is True
