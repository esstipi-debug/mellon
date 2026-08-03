import numpy as np
import pandas as pd
import pytest

from fdekit.baseline import diff_in_diff, parallel_trends_check, pre_post
from fdekit.baseline.design import BaselineSpec, icc_from_log, mde, required_days
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


def test_sin_ponderar_la_tasa_se_declara_como_de_muestra(dc):
    """`stratified_sample` sobre-representa la clase A 3:1 a proposito. Agregar
    con `k/n` crudo sobre esa muestra NO da la tasa poblacional. Mientras no se
    pasen las clases de la poblacion, el resultado tiene que decir que es la
    tasa de la muestra en vez de dejar que se lea como poblacional."""
    s = stratified_sample(dc.master, 300, seed=5)
    audit = audit_master(s, dc.truth[dc.truth["sku_id"].isin(s["sku_id"])])

    sin = audit_summary(audit, population=len(dc.master))
    assert "SIN PONDERAR" in sin["weighting"]
    assert sin["population_coverage_pct"] is None


def _audit_sintetica(por_clase_muestra: dict, tasas: dict) -> pd.DataFrame:
    """Auditoria armada a mano: `n` SKU por clase con la tasa de defecto exacta."""
    filas = []
    for cls, n in por_clase_muestra.items():
        malos = round(n * tasas[cls])
        for i in range(n):
            filas.append({"abc_class": cls, "dim_out_of_tol": i < malos})
    df = pd.DataFrame(filas)
    df["weight_out_of_tol"] = False
    df["location_mismatch"] = False
    df["any_defect"] = df["dim_out_of_tol"]
    df["cube_err_pct"] = 0.0
    return df


def test_la_post_estratificacion_pondera_por_la_poblacion_no_por_la_muestra():
    """El caso de manual, con numeros a mano para que la aritmetica quede fija.

    Muestra: 50 A / 30 B / 20 C con tasas 50% / 20% / 10%.
    Crudo:      (25 + 6 + 2) / 100                      = 33,0%
    Ponderado:  0,1*50% + 0,3*20% + 0,6*10%             = 17,0%

    Los 16 puntos de diferencia son enteros artefacto del diseno de muestreo.
    Reportar el 33% como 'tasa de defecto del catalogo' es un error de una linea
    que produce un numero perfectamente creible.
    """
    audit = _audit_sintetica({"A": 50, "B": 30, "C": 20}, {"A": 0.5, "B": 0.2, "C": 0.1})
    poblacion = {"A": 100, "B": 300, "C": 600}

    crudo = audit_summary(audit, population=1000)
    pond = audit_summary(audit, population=1000, population_by_class=poblacion)

    assert crudo["rates"]["dim_out_of_tol"]["rate_pct"] == pytest.approx(33.0, abs=0.05)
    assert pond["rates"]["dim_out_of_tol"]["rate_pct"] == pytest.approx(17.0, abs=0.05)
    # La tasa de la muestra se conserva al lado, para poder ver el sesgo.
    assert pond["rates"]["dim_out_of_tol"]["sample_rate_pct"] == pytest.approx(33.0, abs=0.05)
    assert "post-estratificado" in pond["weighting"]


def test_la_post_estratificacion_baja_el_sesgo_contra_la_clave_de_respuestas(dc):
    """La propiedad real del estimador es ser insesgado EN EXPECTATIVA, no caer
    mas cerca en cada muestra: en una muestra suelta el crudo puede ganar por
    azar. Por eso el test promedia varias muestras y mira el sesgo, que es lo
    que efectivamente se corrigio."""
    por_clase = dc.master["abc_class"].value_counts().to_dict()
    verdad = float(dc.defects["dim_error"].mean()) * 100

    crudos, ponderados = [], []
    for seed in range(40):
        s = stratified_sample(dc.master, 400, seed=seed)
        audit = audit_master(s, dc.truth[dc.truth["sku_id"].isin(s["sku_id"])])
        crudos.append(audit_summary(audit, population=len(dc.master))["rates"]["dim_out_of_tol"]["rate_pct"])
        ponderados.append(
            audit_summary(audit, population=len(dc.master), population_by_class=por_clase)[
                "rates"
            ]["dim_out_of_tol"]["rate_pct"]
        )

    sesgo_crudo = abs(float(np.mean(crudos)) - verdad)
    sesgo_pond = abs(float(np.mean(ponderados)) - verdad)
    assert sesgo_pond < sesgo_crudo


def test_el_censo_colapsa_el_intervalo(dc):
    """Auditar el catalogo entero no tiene error de muestreo. Que el intervalo
    desaparezca en vez de solo achicarse es la propiedad que hace el caso
    economico de automatizar la medicion dimensional."""
    audit = audit_master(dc.master, dc.truth)
    por_clase = dc.master["abc_class"].value_counts().to_dict()
    r = audit_summary(audit, population=len(dc.master), population_by_class=por_clase)

    d = r["rates"]["dim_out_of_tol"]
    assert d["ci_low_pct"] == d["rate_pct"] == d["ci_high_pct"]


def test_una_clase_sin_auditar_se_reporta_como_cobertura_parcial(dc):
    """Renormalizar el peso sobre lo cubierto sin decirlo convertiria un hueco
    en un promedio."""
    audit = audit_master(dc.master, dc.truth)
    por_clase = dc.master["abc_class"].value_counts().to_dict()
    r = audit_summary(
        audit[audit["abc_class"] != "C"], population=len(dc.master), population_by_class=por_clase
    )
    assert 0 < r["population_coverage_pct"] < 100


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


# ------------------------------------------------- tendencias paralelas


def _panel_tendencias(n_days: int, drift: float, noise: float, seed: int = 0) -> pd.DataFrame:
    """Panel pre con `n_days` dias por grupo. `drift` es la divergencia diaria
    real del grupo tratado; `noise` el ruido entre dias."""
    rng = np.random.default_rng(seed)
    filas = []
    for g in ("control", "treat"):
        for d in range(n_days):
            base = 50 + (drift * d if g == "treat" else 0.0)
            filas += [
                {
                    "grupo": g,
                    "dia": pd.Timestamp("2026-03-02") + pd.Timedelta(days=d),
                    "ciclo": base + rng.normal(0, noise),
                }
                for _ in range(40)
            ]
    return pd.DataFrame(filas)


CORTE = pd.Timestamp("2026-06-01")


def test_tendencias_paralelas_agrega_por_periodo_y_no_por_fila():
    """La version que nunca se corria ajustaba la recta sobre las filas crudas y
    contaba filas para decidir si tenia puntos: con un panel de pedidos veia
    2.100 'puntos' donde habia 3 dias. Tendencias paralelas es una propiedad de
    la media del grupo en el tiempo, no de cada pedido."""
    r = parallel_trends_check(_panel_tendencias(4, 0.0, 1.0), "ciclo", "grupo", "dia", CORTE)
    assert r["n_periods_pre"] == {"control": 4, "treat": 4}


def test_el_ruido_de_tres_dias_no_se_reporta_como_divergencia():
    """Un veredicto categorico desde tres dias de un proceso cuya mediana diaria
    se mueve 30% rechaza ruido como si fuera senal, y descarta el unico
    estimador que se puede defender. Con pocos dias el resultado honesto es 'no
    encontre, y tampoco podria haber encontrado'."""
    r = parallel_trends_check(_panel_tendencias(3, 0.0, 8.0), "ciclo", "grupo", "dia", CORTE)
    assert r["parallel_trends_ok"] is True
    assert r["conclusive"] is False
    assert "NO quedo verificado" in r["reason"]


def test_una_divergencia_real_y_grande_se_detecta_igual_con_pocos_dias():
    r = parallel_trends_check(_panel_tendencias(3, 5.0, 1.0), "ciclo", "grupo", "dia", CORTE)
    assert r["parallel_trends_ok"] is False
    assert "divergian" in r["reason"]


def test_con_ventana_larga_y_sin_divergencia_el_chequeo_es_concluyente():
    r = parallel_trends_check(_panel_tendencias(14, 0.0, 3.0), "ciclo", "grupo", "dia", CORTE)
    assert r["parallel_trends_ok"] is True
    assert r["conclusive"] is True
    assert r["reason"] == ""


def test_con_ventana_larga_se_detecta_una_divergencia_sutil():
    r = parallel_trends_check(_panel_tendencias(14, 1.5, 3.0), "ciclo", "grupo", "dia", CORTE)
    assert r["parallel_trends_ok"] is False
    assert r["conclusive"] is True


def test_sin_periodos_suficientes_no_se_afirma_nada():
    """`None` en `parallel_trends_ok` es 'sin verificar', que no es lo mismo que
    verificado. Devolver True aca seria firmar el supuesto sin mirarlo."""
    r = parallel_trends_check(_panel_tendencias(2, 0.0, 1.0), "ciclo", "grupo", "dia", CORTE)
    assert r["parallel_trends_ok"] is None
    assert r["conclusive"] is False


# ------------------------------------------------------------- ICC medido


def _panel_icc(n_days: int, k: int, sd_between: float, sd_within: float, seed: int = 0):
    """Panel con ICC conocido por construccion: sd_b^2 / (sd_b^2 + sd_w^2)."""
    rng = np.random.default_rng(seed)
    vals, dias = [], []
    for d in range(n_days):
        mu = rng.normal(0, sd_between)
        vals += list(mu + rng.normal(0, sd_within, k))
        dias += [d] * k
    return np.array(vals), np.array(dias)


@pytest.mark.parametrize("sd_b,sd_w", [(0.0, 10.0), (1.43, 10.0), (5.0, 10.0)])
def test_icc_recupera_el_valor_construido(sd_b, sd_w):
    """Si el estimador no recupera un ICC que uno mismo inyecto, no sirve para
    reemplazar la constante que venia a reemplazar."""
    teorico = sd_b**2 / (sd_b**2 + sd_w**2)
    v, g = _panel_icc(30, 200, sd_b, sd_w)
    r = icc_from_log(v, g)

    assert r["usable"]
    assert r["ci_low"] <= teorico <= r["ci_high"]


def test_el_icc_puntual_sobre_pocos_dias_es_blando_y_el_intervalo_lo_muestra():
    """El punto solo es la misma clase de numero que el 0,02 que reemplaza. Con
    pocos grupos el intervalo tiene que ser ancho, y el campo `reason` tiene que
    decirlo en vez de dejar pasar una precision falsa."""
    v, g = _panel_icc(5, 200, 2.0, 10.0)
    r = icc_from_log(v, g)

    assert r["ci_high"] - r["ci_low"] > 0.05
    assert "4 semanas" in r["reason"]


def test_un_icc_negativo_no_baja_el_tamano_de_muestra():
    """Un ICC negativo es ruido, no una propiedad. Llevarlo al diseno daria un
    efecto de diseno bajo 1 —clustering que 'ayuda'— y subestimaria la muestra.
    Se reporta crudo y se acota a 0 para el calculo."""
    rng = np.random.default_rng(3)
    # Dias con MENOS dispersion entre si que adentro: el ICC estimado da < 0.
    v = np.concatenate([rng.normal(0, 10, 50) for _ in range(8)])
    g = np.repeat(np.arange(8), 50)
    v = v - np.repeat([v[g == d].mean() for d in range(8)], 50)  # medias iguales a cero

    r = icc_from_log(v, g)
    assert r["icc"] <= 0
    assert r["icc_for_design"] == 0.0
    assert required_days(sd=10, effect=2, units_per_day=300, icc=r["icc_for_design"])[
        "design_effect"
    ] == pytest.approx(1.0)


def test_sin_grupos_suficientes_el_icc_queda_sin_medir_no_en_cero():
    """`None` es 'no se midio'. Devolver 0 seria afirmar que no hay correlacion
    intra-dia, que es justo el supuesto que hace que un piloto significativo no
    se replique."""
    v, g = _panel_icc(1, 200, 2.0, 10.0)
    r = icc_from_log(v, g)

    assert r["usable"] is False
    assert r["icc"] is None
    assert "SIN MEDIR" in r["reason"]
    assert "mas ventana historica" in r["reason"]


def test_un_log_agregado_por_dia_no_permite_estimar_icc():
    """Con un solo valor por dia la varianza intra-dia es cero: hay que pedir el
    log a nivel de pedido, y decirlo en vez de devolver un numero."""
    r = icc_from_log(np.arange(10.0), np.arange(10))
    assert r["usable"] is False
    assert "nivel de pedido" in r["reason"]


def test_un_cambio_de_nivel_conocido_infla_el_icc_si_no_se_remueve():
    """Lo que siempre aparece en una ventana historica real: un peak. Sin
    removerlo se cuela como si fuera correlacion intra-dia. Es la diferencia
    entre medir el ruido del dia y medir la estacionalidad."""
    v, g = _panel_icc(12, 200, 1.0, 10.0, seed=7)
    periodo = np.where(g < 6, "normal", "peak")
    v_peak = v + np.where(periodo == "peak", 12.0, 0.0)  # el peak sube el nivel

    inflado = icc_from_log(v_peak, g)
    corregido = icc_from_log(v_peak, g, strata=periodo)

    assert inflado["icc"] > corregido["icc"]
    assert corregido["strata_removed"] is True


def test_el_tamano_de_grupo_efectivo_no_es_el_promedio_con_dias_desparejos():
    """Usar el promedio simple sesga el ICC hacia arriba justo cuando hay dias
    de peak, que es cuando importa."""
    v = np.concatenate([np.random.default_rng(1).normal(0, 1, n) for n in (50, 50, 500)])
    g = np.concatenate([np.repeat(0, 50), np.repeat(1, 50), np.repeat(2, 500)])
    r = icc_from_log(v, g)

    assert r["mean_group_size_effective"] < 200.0  # el promedio simple es 200
