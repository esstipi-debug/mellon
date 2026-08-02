import numpy as np
import pandas as pd
import pytest

from fdekit.baseline import diff_in_diff, pre_post
from fdekit.baseline.design import BaselineSpec, mde, required_days
from fdekit.dataquality import (
    audit_master,
    audit_summary,
    link_defects_to_rework,
    sampling_plan,
    stratified_sample,
)
from fdekit.synth import DCConfig, generate_dc


@pytest.fixture(scope="module")
def dc():
    return generate_dc(DCConfig(seed=9, n_orders=900, n_skus=800, dim_error_rate=0.25))


def test_muestra_crece_al_exigir_menos_error():
    a = sampling_plan(10_000, margin_of_error=0.10)["sample_size"]
    b = sampling_plan(10_000, margin_of_error=0.03)["sample_size"]
    assert b > a


def test_muestra_nunca_supera_la_poblacion():
    assert sampling_plan(50, margin_of_error=0.01)["sample_size"] <= 50


def test_muestreo_estratificado_sobrerrepresenta_clase_a(dc):
    s = stratified_sample(dc.master, 300, seed=1)
    share_muestra = (s["abc_class"] == "A").mean()
    share_pob = (dc.master["abc_class"] == "A").mean()
    assert share_muestra > share_pob


def test_auditoria_detecta_los_defectos_inyectados(dc):
    s = stratified_sample(dc.master, 400, seed=2)
    medido = dc.truth[dc.truth["sku_id"].isin(s["sku_id"])]
    audit = audit_master(s, medido)

    verdad = dc.defects.set_index("sku_id")["dim_error"]
    detectado = audit.set_index("sku_id")["dim_out_of_tol"]
    comun = verdad.index.intersection(detectado.index)
    # Con tolerancia de 10% y errores inyectados de 35%+ la deteccion debe ser
    # practicamente perfecta. Si baja, la tolerancia quedo mal calibrada.
    acuerdo = (verdad.loc[comun] == detectado.loc[comun]).mean()
    assert acuerdo > 0.97


def test_resumen_trae_intervalo_de_confianza(dc):
    s = stratified_sample(dc.master, 200, seed=3)
    audit = audit_master(s, dc.truth[dc.truth["sku_id"].isin(s["sku_id"])])
    res = audit_summary(audit, population=len(dc.master))
    r = res["rates"]["any_defect"]
    assert r["ci_low_pct"] <= r["rate_pct"] <= r["ci_high_pct"]
    assert res["projected_defective_skus"]["low"] <= res["projected_defective_skus"]["high"]


def test_vinculo_defecto_reproceso_es_significativo(dc):
    """La triangulacion: los pedidos que tocan SKU con maestro malo deben
    reprocesarse mas. Si este test falla, el generador dejo de encadenar los
    defectos y la demo pierde su mejor hallazgo."""
    s = stratified_sample(dc.master, 500, seed=4)
    audit = audit_master(s, dc.truth[dc.truth["sku_id"].isin(s["sku_id"])])
    link = link_defects_to_rework(audit, dc.events, dc.order_lines)
    assert link["risk_ratio"] > 1.5
    assert link["p_value"] < 0.01
    assert link["population_attributable_fraction_pct"] > 0


def test_mde_baja_al_crecer_la_muestra():
    assert mde(sd=10, n_per_group=1000) < mde(sd=10, n_per_group=100)


def test_icc_infla_la_muestra_necesaria():
    """Ignorar la correlacion intra-dia es lo que hace que un piloto
    'significativo' no se replique."""
    sin_icc = required_days(sd=10, effect=2, units_per_day=300, icc=0.0)
    con_icc = required_days(sd=10, effect=2, units_per_day=300, icc=0.02)
    assert con_icc["n_per_group_adjusted"] > sin_icc["n_per_group_adjusted"]
    assert con_icc["days_per_group"] > sin_icc["days_per_group"]


def test_spec_sin_control_se_marca_como_problema():
    spec = BaselineSpec(
        metric_name="x",
        metric_definition="a / b",
        data_source="t",
        unit_of_analysis="pedido",
        direction="lower_is_better",
        target_change_pct=-10,
        baseline_window_days=21,
        owner_client_side="jefe",
        known_confounders=("peak",),
    )
    issues = spec.validate()
    assert any("control" in i for i in issues)


def test_pre_post_detecta_efecto_real():
    rng = np.random.default_rng(0)
    pre = rng.normal(100, 10, 500)
    post = rng.normal(90, 10, 500)
    r = pre_post(pre, post)
    assert r["delta"] < 0
    assert r["significant"]
    assert "control" in r["warning"]


def test_did_corrige_la_estacionalidad():
    """Los dos grupos empeoran 10 por el peak; el tratado ademas mejora 8. El
    pre/post naive ve +2 (parece que empeoro). DiD debe recuperar el -8."""
    rng = np.random.default_rng(1)
    n = 800
    rows = []
    for g, per, mu in [
        ("control", "pre", 100),
        ("control", "post", 110),
        ("treat", "pre", 100),
        ("treat", "post", 102),
    ]:
        rows.append(pd.DataFrame({"v": rng.normal(mu, 8, n), "group": g, "period": per}))
    panel = pd.concat(rows, ignore_index=True)

    did = diff_in_diff(panel, "v", "group", "period")
    assert did["naive_pre_post_delta"] > 0  # naive dice que empeoro
    assert -10 < did["did_estimate"] < -6  # DiD recupera el efecto real
    assert did["significant"]


def test_did_falla_con_celda_vacia():
    panel = pd.DataFrame({"v": [1.0, 2.0], "group": ["treat", "treat"], "period": ["pre", "post"]})
    with pytest.raises(ValueError, match="celda vacia"):
        diff_in_diff(panel, "v", "group", "period")


def test_did_no_afirma_certeza_cuando_no_hay_dispersion():
    """Varianza cero significa datos sinteticos, o agregados tan grueso que
    quedo una sola observacion por celda. Devolver p=0 seria afirmar certeza
    absoluta a partir de la ausencia de datos, que es peor que no dar el numero.
    """
    panel = pd.DataFrame({
        "v": [10.0, 10.0, 8.0, 8.0, 10.0, 10.0, 10.0, 10.0],
        "group": ["treat"] * 4 + ["control"] * 4,
        "period": ["pre", "pre", "post", "post"] * 2,
    })
    did = diff_in_diff(panel, "v", "group", "period")
    assert did["did_estimate"] == -2.0  # el estimador puntual existe igual
    assert did["testable"] is False
    assert did["p_value"] is None
    assert did["ci_low"] is None
    assert did["significant"] is False
    assert "certeza a partir de la ausencia" in did["warning_varianza"]


def test_did_con_dispersion_si_es_contrastable():
    rng = np.random.default_rng(3)
    rows = [
        pd.DataFrame({"v": rng.normal(mu, 6, 200), "group": g, "period": p})
        for g, p, mu in [("control", "pre", 100), ("control", "post", 100),
                         ("treat", "pre", 100), ("treat", "post", 88)]
    ]
    did = diff_in_diff(pd.concat(rows, ignore_index=True), "v", "group", "period")
    assert did["testable"] is True
    assert did["warning_varianza"] == ""
    assert did["significant"] is True
