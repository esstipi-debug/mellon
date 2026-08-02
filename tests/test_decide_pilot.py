"""Fase 0: el piloto de proceso y el hueco H1.

La regla que atraviesa estos tests: **sin linea base ni contrafactual el
proyecto es infalsable**, y cualquier resultado se puede narrar como exito. Es
la misma violacion que el kit denuncia en los demas.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from fdekit.decide.pilot import (
    SEMANAS_HASTA_VEREDICTO,
    TASA_MINIMA,
    UMBRAL_MUERTE,
    baseline_from_calendar,
    evaluate_pilot,
    load_calendar,
    pilot_spec,
    protocol,
    scaffold,
    score_survey,
    score_tally,
    survey_template,
    tally_instructions,
    tally_template,
    weekly_panel,
)

INICIO = date(2026, 6, 1)


def cal_csv(tmp_path, semanas=8, series=("comite", "control-ops"), horas=1.0, asis=4,
            agenda=True, factor_post=1.0, corte=None):
    filas = []
    for s in series:
        for w in range(semanas):
            d = INICIO + timedelta(weeks=w)
            h = horas
            if corte and d >= corte and s == series[0]:
                h = horas * factor_post
            ini = pd.Timestamp(d) + pd.Timedelta(hours=9)
            filas.append({
                "subject": s,
                "start": ini,
                "end": ini + pd.Timedelta(hours=h),
                "attendees": ";".join(f"p{i}" for i in range(asis)),
                "body": "agenda escrita con varios puntos y detalle" if agenda else "",
            })
    p = tmp_path / "cal.csv"
    pd.DataFrame(filas).to_csv(p, index=False)
    return p


# ------------------------------------------------------------ linea base


def test_el_calendario_da_la_variable_dependiente(tmp_path):
    b = baseline_from_calendar(load_calendar(cal_csv(tmp_path)))
    assert b["semanas_observadas"] == 8
    assert b["horas_persona_semana"] == pytest.approx(8.0)  # 2 series x 1h x 4 personas
    assert b["reuniones_por_semana"] == 2.0
    assert b["series_recurrentes"] == 2


def test_detecta_reuniones_sin_agenda_escrita(tmp_path):
    b = baseline_from_calendar(load_calendar(cal_csv(tmp_path, agenda=False)))
    assert b["pct_sin_agenda_escrita"] == 100.0


def test_el_link_de_teams_no_cuenta_como_agenda():
    """Medir agenda por largo bruto haria que toda reunion con link parezca
    tenerla, que es justo al reves de lo que se quiere detectar."""
    from fdekit.decide.pilot import _tiene_agenda

    solo_link = (
        "________________________________________\n"
        "Unirse a la reunion de Microsoft Teams\n"
        "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc123\n"
        "ID de reunion: 123 456 789  |  Codigo de acceso: aB1cD2\n"
        "Obtener ayuda | Opciones de reunion\n"
        "________________________________________"
    )
    assert _tiene_agenda(solo_link) is False
    assert _tiene_agenda(solo_link + "\n1. Revisar slotting clase A\n2. Cerrar turno noche") is True


def test_una_agenda_corta_de_verdad_cuenta():
    from fdekit.decide.pilot import _tiene_agenda

    assert _tiene_agenda("1. Slotting clase A. 2. Turno noche. 3. Presupuesto Q4") is True
    assert _tiene_agenda("hola") is False


def test_propone_candidatas_a_control_y_explica_por_que(tmp_path):
    b = baseline_from_calendar(load_calendar(cal_csv(tmp_path)))
    assert b["candidatas_a_control"]
    assert "Hawthorne" in b["nota_control"]


def test_el_export_sin_columnas_minimas_falla_con_mensaje_util(tmp_path):
    p = tmp_path / "malo.csv"
    pd.DataFrame({"subject": ["x"], "start": ["2026-01-01"]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="attendees"):
        load_calendar(p)


def test_el_spec_de_medicion_es_firmable():
    spec = pilot_spec("Jefe de operaciones", "control-ops")
    assert spec.validate() == []  # nada pendiente: listo para firmar
    assert "Hawthorne" in " ".join(spec.known_confounders)


def test_el_spec_sin_control_se_marca_como_problema():
    spec = pilot_spec("Jefe de operaciones", "")
    assert any("control" in i for i in spec.validate())


# --------------------------------------------------------------- planilla


def _tally(tmp_path, filas):
    p = tmp_path / "planilla.csv"
    pd.DataFrame(filas).to_csv(p, index=False)
    return p


def fila(punto, que="", dueno="", fecha="", porque="", reunion="c1"):
    return {
        "reunion": reunion, "fecha": "2026-08-03", "punto_agenda": punto,
        "que": que, "dueno": dueno, "fecha_compromiso": fecha, "porque": porque,
        "supuesto": "", "supuesto_vence": "",
    }


def test_la_plantilla_tiene_las_cinco_columnas():
    cab = tally_template().splitlines()[0]
    for c in ("que", "dueno", "fecha_compromiso", "porque", "supuesto"):
        assert c in cab


def test_una_fila_por_punto_de_agenda_no_por_decision(tmp_path):
    """El denominador tiene que existir ANTES de la reunion, o la tasa se
    vuelve autocumplida: si solo se anotan las decisiones tomadas, la tasa de
    declaracion es siempre 100%."""
    p = _tally(tmp_path, [
        fila("slotting", que="reslotear", dueno="M", fecha="2026-09-30", porque="69%"),
        fila("turno noche"),  # punto que no se cerro: la fila vacia ES el dato
    ])
    r = score_tally(p)
    assert r["puntos_de_agenda"] == 2
    assert r["con_algo_escrito"] == 1
    assert r["tasa_declaracion"] == 0.5


def test_sobre_el_setenta_por_ciento_se_sigue(tmp_path):
    p = _tally(tmp_path, [
        fila(f"p{i}", que="algo", dueno="M", fecha="2026-09-30", porque="razon")
        for i in range(8)
    ] + [fila("p8"), fila("p9")])
    r = score_tally(p)
    assert r["tasa_declaracion"] == 0.8
    assert r["ok"] is True
    assert "seguir a fase 1" in r["veredicto"]


def test_bajo_el_minimo_no_se_sigue_y_se_dice_por_que(tmp_path):
    p = _tally(tmp_path, [fila("p1", que="algo", dueno="M", fecha="x", porque="y")]
               + [fila(f"p{i}") for i in range(2, 6)])
    r = score_tally(p)
    assert r["ok"] is False
    assert "NO seguir" in r["veredicto"]
    assert "El software no arregla esto" in r["veredicto"]


def test_el_campo_que_mas_falta_es_el_diagnostico(tmp_path):
    """Si falta el 'porque', la frase se dice a medias y se corrige al
    facilitador. Si falta el dueno, el problema es politico."""
    p = _tally(tmp_path, [
        fila(f"p{i}", que="algo", dueno="M", fecha="2026-09-30", porque="")
        for i in range(5)
    ])
    r = score_tally(p)
    assert r["campo_que_mas_falta"] == "porque"
    assert "a medias" in r["veredicto"] or r["ok"]


def test_falta_de_dueno_se_lee_como_problema_politico(tmp_path):
    p = _tally(tmp_path, [fila(f"p{i}", que="algo", dueno="", fecha="", porque="") for i in range(5)])
    r = score_tally(p)
    assert r["campo_que_mas_falta"] in ("dueno", "fecha")
    assert r["ok"] is True  # 'que' esta escrito: la declaracion existe
    assert r["con_los_cuatro_campos"] == 0


def test_la_planilla_sin_denominador_falla(tmp_path):
    p = tmp_path / "sin.csv"
    pd.DataFrame({"que": ["algo"]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="denominador"):
        score_tally(p)


def test_la_hoja_de_sala_prohibe_el_software():
    h = tally_instructions()
    assert "No se usa software" in h
    assert "Queda decidido" in h
    assert "de memoria" in h  # prohibe reconstruir filas despues


# --------------------------------------------------------------- encuesta


def test_la_encuesta_tiene_tres_preguntas():
    cab = [l for l in survey_template().splitlines() if not l.startswith("#")][0]
    assert cab.count(",") == 5  # fecha, persona, grupo + 3 preguntas


def test_la_encuesta_compara_grupos_no_olas_de_si_mismo(tmp_path):
    p = tmp_path / "e.csv"
    filas = []
    for mes, valor in (("2026-06-01", 4), ("2026-07-01", 2)):
        for grupo, v in (("treat", valor), ("control", 4)):
            for i in range(4):
                filas.append({"fecha": mes, "persona": f"p{i}", "grupo": grupo,
                              "podian_ser_correo": v, "rediscutido": v,
                              "minutos_buscar": v * 5})
    pd.DataFrame(filas).to_csv(p, index=False)
    r = score_survey(p)
    assert len(r["por_ola"]) == 2
    assert r["por_ola"]["2026-07"]["podian_ser_correo"] == {"control": 4.0, "treat": 2.0}
    assert "treat contra control" in r["veredicto"]


# --------------------------------------------------- criterio de muerte


def test_una_caida_mayor_al_umbral_deja_seguir(tmp_path):
    corte = INICIO + timedelta(weeks=4)
    cal = load_calendar(cal_csv(tmp_path, semanas=8, factor_post=0.6, corte=corte))
    v = evaluate_pilot(weekly_panel(cal, ["comite"], ["control-ops"], corte))
    assert v.pct_vs_baseline < -UMBRAL_MUERTE * 100
    assert v.passes is True


def test_sin_caida_suficiente_se_apaga(tmp_path):
    corte = INICIO + timedelta(weeks=4)
    cal = load_calendar(cal_csv(tmp_path, semanas=8, factor_post=0.95, corte=corte))
    v = evaluate_pilot(weekly_panel(cal, ["comite"], ["control-ops"], corte))
    assert v.passes is False


def test_sin_las_cuatro_celdas_no_hay_contrafactual(tmp_path):
    corte = INICIO + timedelta(weeks=4)
    cal = load_calendar(cal_csv(tmp_path, semanas=8, series=("comite",)))
    v = evaluate_pilot(weekly_panel(cal, ["comite"], ["no-existe"], corte))
    assert v.passes is False
    assert "no hay contrafactual" in v.note


def test_el_veredicto_declara_si_el_diseno_tiene_potencia(tmp_path):
    """Un umbral que el diseno no puede detectar es una promesa que no se puede
    probar, y hay que decirlo antes de declarar nada."""
    corte = INICIO + timedelta(weeks=1)
    cal = load_calendar(cal_csv(tmp_path, semanas=3, factor_post=0.6, corte=corte))
    v = evaluate_pilot(weekly_panel(cal, ["comite"], ["control-ops"], corte))
    assert "mde_pct_con_estas_semanas" in v.detail
    assert isinstance(v.note, str) and v.note


# ------------------------------------------------------------ artefactos


def test_el_scaffold_escribe_los_cinco_artefactos(tmp_path):
    r = scaffold(tmp_path / "piloto", site="CD Pudahuel", metric_owner="Jefe de operaciones",
                 control_series="control-ops", start=INICIO)
    for f in r["archivos"]:
        assert (tmp_path / "piloto" / f).exists()
    assert "solo entran planilla.csv y hoja-de-sala.md" in r["recordatorio"]


def test_el_protocolo_declara_el_criterio_de_muerte_antes_de_empezar():
    p = protocol("CD Pudahuel", INICIO, "control-ops")
    assert f"{UMBRAL_MUERTE:.0%} contra" in p
    assert "Declararlo ahora es lo que lo hace falsable" in p
    assert (INICIO + timedelta(weeks=SEMANAS_HASTA_VEREDICTO)).isoformat() in p


def test_el_protocolo_prohibe_instalar_el_software(tmp_path):
    p = protocol("x", INICIO)
    assert "No hay que hacer" in p or "NO hay que hacer" in p
    assert "Instalar `fdekit.decide`" in p
    assert "Contarle al grupo de control" in p


def test_el_protocolo_advierte_del_efecto_hawthorne():
    p = protocol("x", INICIO)
    assert "Hawthorne" in p
    assert "sensacion de la sala" in p
