"""Las aserciones de audit_assertions_sap.sql, corridas de verdad en sqlite3.

El SQL se escribio como especificacion y nunca se habia ejecutado. Tres de sus
cinco aserciones no fallaban: mentian. Una linea de OC con tres repartos salia
tres veces; la copia de un asiento en el libro paralelo daba una diferencia que
no existe; un 105 del dia despues del go-live contra un 103 del dia antes daba
una violacion de masa falsa.

Cada test es una sonda de dos corridas, como `sonda_dos_corridas` en Kern: el
mismo SQL contra una base sana y contra la misma base con un cambio. Si el
cambio es un defecto, tiene que aparecer al menos una fila con el codigo de
violacion exacto; si es una variacion legitima (un libro paralelo, una fecha
contable anterior al corte), el veredicto no se puede mover. Un test que solo
mira la base sana no distingue un guardia que funciona de uno que nunca
devuelve nada.

Solo stdlib: sqlite3 en memoria, ningun archivo escrito.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

SQL = Path(__file__).resolve().parent.parent / "audit_assertions_sap.sql"
GO_LIVE = "2026-11-01"
MANDT = "100"
MJAHR = "2026"

Carga = Callable[[sqlite3.Connection], None]

_DDL = """
CREATE TABLE s4_mkpf (mandt TEXT, mblnr TEXT, mjahr TEXT, budat TEXT, cpudt TEXT, cputm TEXT);
CREATE TABLE s4_mseg (
    mandt TEXT, mblnr TEXT, mjahr TEXT, zeile TEXT, bwart TEXT, matnr TEXT, werks TEXT,
    lgort TEXT, menge REAL, meins TEXT, dmbtr REAL, waers TEXT, shkzg TEXT, erfnam TEXT,
    ebeln TEXT, ebelp TEXT
);
CREATE TABLE s4_ekpo (
    mandt TEXT, ebeln TEXT, ebelp TEXT, matnr TEXT, werks TEXT, netpr REAL, menge REAL,
    aedat TEXT
);
CREATE TABLE s4_eket (mandt TEXT, ebeln TEXT, ebelp TEXT, etenr TEXT, eindt TEXT, menge REAL);
CREATE TABLE s4_mara (mandt TEXT, matnr TEXT, plifz INTEGER);
CREATE TABLE s4_acdoca (
    mandt TEXT, rldnr TEXT, gjahr TEXT, racct TEXT, hsl REAL, budat TEXT, awref TEXT
);
CREATE TABLE fde_telemetry_scrap_events (
    transaction_id TEXT, sap_mandt_reference TEXT, sap_mblnr_reference TEXT,
    sap_mjahr_reference TEXT, sap_zeile_reference TEXT,
    is_cryptographically_verified BOOLEAN, scale_weight_divergence_pct REAL
);
CREATE TABLE fde_blind_cycle_counts (
    sap_mandt_ref TEXT, sap_mblnr_ref TEXT, sap_mjahr_ref TEXT, sap_zeile_ref TEXT,
    counter_user_badge TEXT, blind_token_hash TEXT, is_system_stock_revealed_on_rf BOOLEAN
);
CREATE TABLE fde_demand_forecast_baselines (matnr TEXT, werks TEXT, daily_consumption_rate REAL);
CREATE TABLE fde_governance_approvals (
    approval_id TEXT, mandt_ref TEXT, ebeln_ref TEXT, ebelp_ref TEXT, approval_level TEXT,
    digital_signature_verified BOOLEAN
);
"""


# ------------------------------------------------------------ el SQL real


def cargar_aserciones(path: Path) -> dict[int, str]:
    """Cada sentencia del archivo, numerada por su comentario `-- ASSERTION N:`.

    `sqlite3.complete_statement` decide donde termina cada sentencia, asi que un
    `;` dentro de un comentario o de un literal no la corta. Una sentencia sin
    numero, un numero repetido o un resto sin cerrar revientan aca: perder una
    asercion en silencio daria una suite verde que no la probo.
    """
    sentencias: dict[int, str] = {}
    buf: list[str] = []
    numero: int | None = None
    for linea in path.read_text(encoding="utf-8").splitlines(keepends=True):
        marca = re.match(r"--\s*ASSERTION\s+(\d+):", linea.strip())
        if marca:
            numero = int(marca.group(1))
        buf.append(linea)
        texto = "".join(buf)
        if not sqlite3.complete_statement(texto):
            continue
        if numero is None:
            raise ValueError(f"sentencia sin comentario ASSERTION N:\n{texto}")
        if numero in sentencias:
            raise ValueError(f"ASSERTION {numero} aparece dos veces")
        sentencias[numero] = texto
        buf, numero = [], None
    resto = [l for l in "".join(buf).splitlines() if l.strip() and not l.strip().startswith("--")]
    if resto:
        raise ValueError(f"el archivo termina con una sentencia sin cerrar: {resto[:3]}")
    return sentencias


ASERCIONES = cargar_aserciones(SQL)


def fila(con: sqlite3.Connection, tabla: str, **campos: object) -> None:
    columnas = ", ".join(campos)
    marcas = ", ".join("?" for _ in campos)
    con.execute(f"INSERT INTO {tabla} ({columnas}) VALUES ({marcas})", tuple(campos.values()))


def correr(n: int, *cargas: Carga) -> list[sqlite3.Row]:
    """La asercion `n` contra una base nueva en memoria con estas cargas."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    try:
        con.executescript(_DDL)
        for carga in cargas:
            carga(con)
        return con.execute(ASERCIONES[n], {"deployment_go_live_date": GO_LIVE}).fetchall()
    finally:
        con.close()


def dos_corridas(n: int, sano: Carga, cambio: Carga) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """Las dos corridas de la sonda: la base sana, y la misma base con el cambio."""
    return correr(n, sano), correr(n, sano, cambio)


def codigo(f: sqlite3.Row) -> str:
    """El codigo de violacion: lo que va antes de `:` en `audit_violation_reason`."""
    return f["audit_violation_reason"].split(":", 1)[0]


def codigos(filas: list[sqlite3.Row]) -> list[str]:
    return [codigo(f) for f in filas]


def test_el_archivo_trae_las_cinco_aserciones():
    """Si el corte del archivo perdiera una asercion, los tests de esa asercion
    no podrian ni nombrarla: esto falla primero y dice cual falta."""
    assert sorted(ASERCIONES) == [1, 2, 3, 4, 5]


# ------------------------------------------------------- datos de prueba


def movimiento(
    con: sqlite3.Connection,
    mblnr: str,
    bwart: str,
    cpudt: str,
    *,
    budat: str | None = None,
    zeile: str = "0001",
    **mseg: object,
) -> None:
    """Un documento material de una linea: cabecera MKPF y su linea MSEG."""
    fila(con, "s4_mkpf", mandt=MANDT, mblnr=mblnr, mjahr=MJAHR, budat=budat or cpudt,
         cpudt=cpudt, cputm="10:00:00")
    fila(con, "s4_mseg", mandt=MANDT, mblnr=mblnr, mjahr=MJAHR, zeile=zeile, bwart=bwart, **mseg)


def asiento(con: sqlite3.Connection, awref: str, hsl: float, *, racct: str = "00501000",
            budat: str = "2026-11-03", rldnr: str = "0L") -> None:
    fila(con, "s4_acdoca", mandt=MANDT, rldnr=rldnr, gjahr=MJAHR, racct=racct, hsl=hsl,
         budat=budat, awref=awref)


def sql(sentencia: str) -> Carga:
    return lambda con: con.execute(sentencia)


# ------------------------------------------- asercion 1: bajas sin sensor


def a1_sano(con: sqlite3.Connection) -> None:
    movimiento(con, "4900000101", "551", "2026-11-03", matnr="MAT-S", werks="P001",
               menge=10.0, dmbtr=1000.0, shkzg="H", erfnam="U1")
    fila(con, "fde_telemetry_scrap_events", transaction_id="T-1", sap_mandt_reference=MANDT,
         sap_mblnr_reference="4900000101", sap_mjahr_reference=MJAHR, sap_zeile_reference="0001",
         is_cryptographically_verified=True, scale_weight_divergence_pct=0.01)


@pytest.mark.parametrize(
    "defecto",
    [
        sql("DELETE FROM fde_telemetry_scrap_events"),
        sql("UPDATE fde_telemetry_scrap_events SET is_cryptographically_verified = 0"),
        sql("UPDATE fde_telemetry_scrap_events SET scale_weight_divergence_pct = 0.05"),
    ],
    ids=["sin_telemetria", "firma_no_verificada", "divergencia_5_por_ciento"],
)
def test_a1_una_baja_sin_prueba_del_sensor_se_reporta(defecto):
    sano, mutado = dos_corridas(1, a1_sano, defecto)
    assert sano == []
    assert codigos(mutado) == ["SECURITY_ALERT"]


@pytest.mark.xfail(strict=True, reason=(
    "pendiente: con is_cryptographically_verified y la divergencia en NULL, "
    "`= FALSE` y `> 0.03` dan NULL y la baja pasa como verificada"
))
def test_a1_una_verificacion_desconocida_no_cuenta_como_verificada():
    _, mutado = dos_corridas(1, a1_sano, sql(
        "UPDATE fde_telemetry_scrap_events "
        "SET is_cryptographically_verified = NULL, scale_weight_divergence_pct = NULL"
    ))
    assert len(mutado) >= 1


# ------------------------------------------ asercion 2: conteo a ciegas


def a2_sano(con: sqlite3.Connection) -> None:
    movimiento(con, "4900000201", "701", "2026-11-03", matnr="MAT-C", werks="P001",
               menge=5.0, dmbtr=50.0, shkzg="S", erfnam="U1")
    fila(con, "fde_blind_cycle_counts", sap_mandt_ref=MANDT, sap_mblnr_ref="4900000201",
         sap_mjahr_ref=MJAHR, sap_zeile_ref="0001", counter_user_badge="U2",
         blind_token_hash="h-1", is_system_stock_revealed_on_rf=False)


@pytest.mark.parametrize(
    ("defecto", "esperado"),
    [
        (sql("UPDATE fde_blind_cycle_counts SET counter_user_badge = 'U1'"),
         "SEGREGATION_OF_DUTIES_VIOLATION"),
        (sql("UPDATE fde_blind_cycle_counts SET blind_token_hash = NULL"), "INTEGRITY_BREACH"),
        (sql("UPDATE fde_blind_cycle_counts SET is_system_stock_revealed_on_rf = 1"),
         "GOODHART_VIOLATION"),
        (sql("DELETE FROM fde_blind_cycle_counts"), "INTEGRITY_BREACH"),
    ],
    ids=["contador_es_quien_contabiliza", "sin_token", "stock_mostrado", "sin_registro_de_conteo"],
)
def test_a2_un_ajuste_sin_conteo_a_ciegas_se_reporta(defecto, esperado):
    sano, mutado = dos_corridas(2, a2_sano, defecto)
    assert sano == []
    assert codigos(mutado) == [esperado]


# ------------------------------- asercion 3: compra por MOQ sin aprobacion

# Precio 20, 100.000 unidades y 500 por dia: 200 dias de cobertura. Destruccion
# de caja, a mano: 20 * 50.000 * (200 / 365) * 0,245 - 20 * 0,03 * 100.000
# = 134.246,575 - 60.000 = 74.246,575.
DESTRUCCION_UNA_LINEA = 74246.575


def a3_oc(repartos: int) -> Carga:
    def cargar(con: sqlite3.Connection) -> None:
        fila(con, "s4_ekpo", mandt=MANDT, ebeln="4500000001", ebelp="00010", matnr="MAT-A",
             werks="P001", netpr=20.0, menge=100000.0, aedat="2026-11-05")
        for i in range(1, repartos + 1):
            fila(con, "s4_eket", mandt=MANDT, ebeln="4500000001", ebelp="00010",
                 etenr=f"{i:04d}", eindt=f"2026-12-{i:02d}", menge=100000.0 / repartos)
        fila(con, "s4_mara", mandt=MANDT, matnr="MAT-A", plifz=30)
        fila(con, "fde_demand_forecast_baselines", matnr="MAT-A", werks="P001",
             daily_consumption_rate=500.0)
        fila(con, "fde_governance_approvals", approval_id="AP-1", mandt_ref=MANDT,
             ebeln_ref="4500000001", ebelp_ref="00010", approval_level="CFO_EXECUTIVE_RED_LANE",
             digital_signature_verified=True)
    return cargar


SIN_APROBACION = sql("DELETE FROM fde_governance_approvals")


def test_a3_una_oc_sin_aprobacion_se_reporta():
    sano, mutado = dos_corridas(3, a3_oc(repartos=1), SIN_APROBACION)
    assert sano == []
    assert codigos(mutado) == ["GOVERNANCE_BYPASS"]


def test_a3_tres_repartos_son_una_sola_violacion_y_no_triplican_la_caja():
    """Contraejemplo 1. EKET trae una fila por reparto: cruzada sin agregar,
    la linea de OC salia tres veces y la suma del resultado triplicaba la caja."""
    sano, mutado = dos_corridas(3, a3_oc(repartos=3), SIN_APROBACION)
    assert sano == []
    assert codigos(mutado) == ["GOVERNANCE_BYPASS"]
    total = sum(f["net_working_capital_destruction_usd"] for f in mutado)
    assert total == pytest.approx(DESTRUCCION_UNA_LINEA, abs=0.01)


def test_a3_la_aprobacion_de_otro_mandante_no_tapa_la_oc():
    """El grano de la aprobacion es (mandt, ebeln, ebelp): una aprobacion del
    mandante 200 con el mismo numero de OC no aprueba la del 100."""
    sano, mutado = dos_corridas(3, a3_oc(repartos=1), sql(
        "UPDATE fde_governance_approvals SET mandt_ref = '200'"
    ))
    assert sano == []
    assert codigos(mutado) == ["GOVERNANCE_BYPASS"]


@pytest.mark.xfail(strict=True, reason=(
    "pendiente: sin pronostico de demanda la cobertura da NULL, `> 90` da NULL y "
    "la OC no sale: no poder evaluarla se lee como que cumple"
))
def test_a3_una_oc_sin_pronostico_no_se_da_por_buena():
    _, mutado = dos_corridas(3, a3_oc(repartos=1), lambda con: (
        con.execute("DELETE FROM fde_governance_approvals"),
        con.execute("DELETE FROM fde_demand_forecast_baselines"),
    ))
    assert len(mutado) >= 1


# --------------------------------- asercion 4: MM contra FI, documento a documento


def a4_sano(con: sqlite3.Connection) -> None:
    movimiento(con, "4900000401", "551", "2026-11-03", matnr="MAT-S", werks="P001",
               menge=10.0, dmbtr=1000.0, shkzg="H")
    asiento(con, "4900000401", 1000.0)


def test_a4_una_diferencia_real_entre_mm_y_fi_se_reporta():
    sano, mutado = dos_corridas(4, a4_sano, sql("UPDATE s4_acdoca SET hsl = 900"))
    assert sano == []
    assert codigos(mutado) == ["LEDGER_DESYNCHRONIZATION"]


def test_a4_la_copia_en_el_libro_paralelo_no_es_una_diferencia():
    """Contraejemplo 2a. ACDOCA repite el asiento en cada libro (0L, 2L...):
    sumados todos, FI daba 2.000 contra 1.000 de MM."""
    sano, mutado = dos_corridas(4, a4_sano, lambda con: asiento(con, "4900000401", 1000.0,
                                                                  rldnr="2L"))
    assert sano == []
    assert mutado == []


def test_a4_un_asiento_de_baja_en_fi_sin_documento_logistico_se_reporta():
    """Contraejemplo 2b. Con el cruce en un solo sentido, una baja cargada a mano
    en FI, sin documento en MSEG, no aparecia nunca."""
    sano, mutado = dos_corridas(4, a4_sano, lambda con: asiento(
        con, "0100000099", 5000.0, racct="00502000", budat="2026-11-04"))
    assert sano == []
    assert codigos(mutado) == ["ORPHAN_FI_WRITE_OFF"]


def test_a4_un_552_que_revierte_cuadra_en_los_dos_libros():
    """Con el cruce en los dos sentidos, la reversion tiene que entrar con su
    signo: S en MSEG, credito (negativo) en FI."""
    def reversion(con: sqlite3.Connection) -> None:
        movimiento(con, "4900000402", "552", "2026-11-04", matnr="MAT-S", werks="P001",
                   menge=10.0, dmbtr=1000.0, shkzg="S")
        asiento(con, "4900000402", -1000.0, budat="2026-11-04")

    sano, mutado = dos_corridas(4, a4_sano, reversion)
    assert sano == []
    assert mutado == []


def test_a4_sin_shkzg_el_signo_sale_del_tipo_de_movimiento():
    """Un extracto sin SHKZG: 551 y 702 sacan stock (H), 552 y 701 lo entran (S)."""
    sano, mutado = dos_corridas(4, a4_sano, sql("UPDATE s4_mseg SET shkzg = NULL"))
    assert sano == []
    assert mutado == []


def test_a4_manda_la_fecha_contable_en_los_dos_lados():
    """Cargado el 2-nov con fecha contable 31-oct: queda antes del corte en los
    dos libros. Comparar fecha de carga en MM con fecha contable en FI lo metia
    de un solo lado y daba una diferencia que no existe."""
    def antes_del_corte(con: sqlite3.Connection) -> None:
        movimiento(con, "4900000403", "551", "2026-11-02", budat="2026-10-31", matnr="MAT-S",
                   werks="P001", menge=7.0, dmbtr=700.0, shkzg="H")
        asiento(con, "4900000403", 700.0, budat="2026-10-31")

    sano, mutado = dos_corridas(4, a4_sano, antes_del_corte)
    assert sano == []
    assert mutado == []


# ----------------------------- asercion 5: recepcion condicional 103 -> 105/124/122


def recepcion(mblnr: str, bwart: str, cantidad: float, cpudt: str, ebelp: str = "00010") -> Carga:
    return lambda con: movimiento(con, mblnr, bwart, cpudt, matnr="MAT-R", werks="P001",
                                  menge=cantidad, ebeln="4500000002", ebelp=ebelp)


def cargas(*partes: Carga) -> Carga:
    def cargar(con: sqlite3.Connection) -> None:
        for parte in partes:
            parte(con)
    return cargar


A5_SANO = cargas(recepcion("5000000001", "103", 50.0, "2026-11-02"),
                 recepcion("5000000002", "105", 50.0, "2026-11-03"))


def test_a5_liberar_mas_de_lo_recibido_se_reporta():
    sano, mutado = dos_corridas(5, A5_SANO, sql(
        "UPDATE s4_mseg SET menge = 60 WHERE bwart = '105'"))
    assert sano == []
    assert codigos(mutado) == ["MASS_CONSERVATION_BREACH"]


def test_a5_devolver_valorado_mas_de_lo_liberado_se_reporta():
    sano, mutado = dos_corridas(5, A5_SANO, recepcion("5000000003", "122", 60.0, "2026-11-04"))
    assert sano == []
    assert codigos(mutado) == ["MOVEMENT_TYPE_ERROR"]


def test_a5_un_103_recibido_antes_del_go_live_cuenta_para_su_105():
    """Contraejemplo 3. El 103 del 30-oct y su 105 del 3-nov son la misma linea
    de OC. Cortar la ventana por fecha dejaba el 105 sin su 103: una violacion
    de masa que no existe, justo en las ordenes en transito del corte."""
    sano, mutado = dos_corridas(5, A5_SANO, sql(
        "UPDATE s4_mkpf SET cpudt = '2026-10-30', budat = '2026-10-30' "
        "WHERE mblnr = '5000000001'"))
    assert sano == []
    assert mutado == []


def test_a5_un_exceso_real_a_traves_del_corte_se_sigue_reportando():
    """La contracara del contraejemplo 3: con el 103 antes del corte, un 105
    mayor que lo recibido sigue siendo una violacion."""
    antes_del_corte = cargas(recepcion("5000000001", "103", 50.0, "2026-10-30"),
                             recepcion("5000000002", "105", 50.0, "2026-11-03"))
    sano, mutado = dos_corridas(5, antes_del_corte, sql(
        "UPDATE s4_mseg SET menge = 60 WHERE bwart = '105'"))
    assert sano == []
    assert codigos(mutado) == ["MASS_CONSERVATION_BREACH"]


def test_a5_una_linea_sin_movimiento_desde_el_go_live_queda_fuera():
    """El corte sigue filtrando lineas: una que termino antes del go-live no es
    materia de esta auditoria, aunque haya cerrado mal."""
    cerrada_antes = cargas(recepcion("5000000011", "103", 50.0, "2026-10-20", ebelp="00020"),
                           recepcion("5000000012", "105", 60.0, "2026-10-25", ebelp="00020"))
    sano, mutado = dos_corridas(5, A5_SANO, cerrada_antes)
    assert sano == []
    assert mutado == []
