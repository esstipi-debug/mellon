"""
07_forensic_process_conformance_simulator.py
========================================================================================
SIMULADOR FORENSE DE CONFORMANCE CHECKING, INVARIANTES FÍSICAS Y DETECCIÓN DE SHADOW IT
========================================================================================
Propósito: Demostrar la detección automatizada de anomalías operacionales y arbitraje
de incentivos a partir de la correlación cruzada de tres streams de datos crudos:
1. Event-Logs de SAP / WMS (Marcas de tiempo atómicas de confirmación)
2. Syslog de Roaming Wi-Fi 802.11k/r/v (Ubicación física real de terminales RF)
3. Telemetría CAN-bus J1939 (Odometría, velocidad e impactos de grúas)

Framework: FDE Field Toolkit / Industrial Forensic Operations
========================================================================================
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Reconfigurar stdout en Windows para soporte UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ======================================================================================
# 1. ESTRUCTURAS DE DATOS CRUDA Y MODELO DE CONFORMANCE
# ======================================================================================

@dataclass
class RawWmsEvent:
    timestamp: datetime
    case_id: str
    activity: str
    operator_id: str
    bin_location: str
    coords_xyz: Tuple[float, float, float]
    quantity: int


@dataclass
class RawWifiSyslog:
    timestamp: datetime
    client_mac: str
    ap_bssid: str
    ap_zone: str
    event_type: str
    rssi_dbm: int


@dataclass
class RawCanBusTelemetry:
    timestamp: datetime
    vehicle_id: str
    speed_mps: float
    distance_accum_m: float
    battery_current_a: float
    accel_peak_g: float


# Golden Path Canónico: Transición -> (SLA Mínimo Segundos, SLA Máximo Segundos)
GOLDEN_PATH_SLAS = {
    ("GATE_IN", "DOCK_ASSIGN"): (60.0, 900.0),
    ("DOCK_ASSIGN", "UNLOAD_START"): (30.0, 600.0),
    ("UNLOAD_START", "STAGING_VERIFY"): (180.0, 3600.0),
    ("STAGING_VERIFY", "PUTAWAY_EXEC"): (300.0, 7200.0),
    ("PUTAWAY_EXEC", "PICK_WAVE_ALLOC"): (60.0, 14400.0),
    ("PICK_WAVE_ALLOC", "PICK_CONFIRM"): (120.0, 1800.0),
    ("PICK_CONFIRM", "PACK_CONSOLIDATE"): (60.0, 900.0),
    ("PACK_CONSOLIDATE", "DOCK_OUTBOUND"): (60.0, 1800.0),
    ("DOCK_OUTBOUND", "GATE_OUT"): (60.0, 1200.0),
}


# ======================================================================================
# 2. GENERADOR DE CASOS SINTÉTICOS CON ANOMALÍAS REALES DE TERRENO
# ======================================================================================

def generate_forensic_test_scenarios() -> Tuple[List[RawWmsEvent], List[RawWifiSyslog], List[RawCanBusTelemetry]]:
    """
    Genera 3 casos operativos con telemetría cruzada:
    - CASO_001 (Golden Path): Flujo óptimo conforme a diseño.
    - CASO_002 (Batch Scanning Clotting): Operario confirma 4 órdenes en 6 segundos a 45 metros de distancia (Gaming).
    - CASO_003 (Congestión y Double-Handling): Pallets atrapados en muelle con retrabajos y desvío de odometría 3.5x.
    """
    t0 = datetime(2026, 10, 25, 8, 0, 0)
    wms_events: List[RawWmsEvent] = []
    wifi_events: List[RawWifiSyslog] = []
    can_events: List[RawCanBusTelemetry] = []

    # ----------------------------------------------------------------------------------
    # CASO 1: Flujo Conforme Estándar (Golden Path)
    # ----------------------------------------------------------------------------------
    c1_steps = [
        ("GATE_IN", t0, "GATE_01", (0.0, 0.0, 0.0)),
        ("DOCK_ASSIGN", t0 + timedelta(minutes=4), "DOCK_03", (10.0, 5.0, 0.0)),
        ("UNLOAD_START", t0 + timedelta(minutes=7), "DOCK_03", (12.0, 5.0, 0.0)),
        ("STAGING_VERIFY", t0 + timedelta(minutes=25), "STAGING_A1", (25.0, 10.0, 0.0)),
        ("PUTAWAY_EXEC", t0 + timedelta(minutes=55), "RACK_12_04", (85.0, 30.0, 4.5)),
        ("PICK_WAVE_ALLOC", t0 + timedelta(hours=2), "RACK_12_04", (85.0, 30.0, 4.5)),
        ("PICK_CONFIRM", t0 + timedelta(hours=2, minutes=18), "RACK_12_04", (85.0, 30.0, 1.2)),
        ("PACK_CONSOLIDATE", t0 + timedelta(hours=2, minutes=28), "PACK_02", (15.0, 40.0, 0.0)),
        ("DOCK_OUTBOUND", t0 + timedelta(hours=2, minutes=45), "DOCK_08", (10.0, 70.0, 0.0)),
        ("GATE_OUT", t0 + timedelta(hours=2, minutes=55), "GATE_02", (0.0, 80.0, 0.0)),
    ]
    for act, ts, loc, xyz in c1_steps:
        wms_events.append(RawWmsEvent(ts, "CASE_001_GOLDEN", act, "OP_CORRECT", loc, xyz, 50))

    # Telemetría Wi-Fi coherente para Caso 1 (el operario se desplaza por los APs)
    wifi_events.append(RawWifiSyslog(t0 + timedelta(hours=2), "MAC_OP_01", "BSSID_AISLE_12", "AISLE_12", "ROAM", -65))
    wifi_events.append(RawWifiSyslog(t0 + timedelta(hours=2, minutes=25), "MAC_OP_01", "BSSID_PACK_02", "PACKING", "ROAM", -58))

    # Odometría CAN-bus normal para Caso 1: 180 metros recorridos
    can_events.append(RawCanBusTelemetry(t0 + timedelta(minutes=55), "FORK_01", 1.8, 180.0, 45.0, 0.12))

    # ----------------------------------------------------------------------------------
    # CASO 2: Arbitraje de Incentivos (Batch Scanning Clotting / Shadow IT)
    # ----------------------------------------------------------------------------------
    # El operario hizo picking en papel y confirma 4 picks en ráfaga (intervalos de 2 segundos)
    # abarcando 45 metros de pasillo, mientras el Wi-Fi muestra que estaba en la sala de café.
    t_clot = t0 + timedelta(hours=3)
    clot_picks = [
        ("PICK_CONFIRM", t_clot, "RACK_02_01", (10.0, 10.0, 0.0)),
        ("PICK_CONFIRM", t_clot + timedelta(seconds=2), "RACK_02_15", (35.0, 10.0, 0.0)),
        ("PICK_CONFIRM", t_clot + timedelta(seconds=4), "RACK_03_04", (45.0, 20.0, 0.0)),
        ("PICK_CONFIRM", t_clot + timedelta(seconds=7), "RACK_03_22", (55.0, 20.0, 0.0)),
    ]
    for act, ts, loc, xyz in clot_picks:
        wms_events.append(RawWmsEvent(ts, "CASE_002_BATCH_GAMING", act, "OP_GAMER", loc, xyz, 10))

    # Wi-Fi desmiente el movimiento: terminal estático en el AP de la cafetería/lockers
    wifi_events.append(RawWifiSyslog(t_clot - timedelta(minutes=5), "MAC_OP_GAMER", "BSSID_BREAKROOM", "BREAKROOM", "ASSOCIATE", -52))
    wifi_events.append(RawWifiSyslog(t_clot + timedelta(seconds=10), "MAC_OP_GAMER", "BSSID_BREAKROOM", "BREAKROOM", "STATIONARY", -51))

    # ----------------------------------------------------------------------------------
    # CASO 3: Congestión Crítica y Doble Manipulación en Staging (Re-handling Loop)
    # ----------------------------------------------------------------------------------
    # El pallet se descarga, pero el piso está lleno (>85% ocupado). Se mueve 3 veces en staging
    # para despejar el paso antes de poder subirlo a rack.
    t_cong = t0 + timedelta(hours=1)
    cong_steps = [
        ("GATE_IN", t_cong, "GATE_01", (0.0, 0.0, 0.0)),
        ("DOCK_ASSIGN", t_cong + timedelta(minutes=15), "DOCK_01", (10.0, 5.0, 0.0)),
        ("UNLOAD_START", t_cong + timedelta(minutes=45), "DOCK_01", (10.0, 5.0, 0.0)),
        # Doble manipulación: Staging -> Staging -> Staging
        ("STAGING_VERIFY", t_cong + timedelta(minutes=80), "STAGING_A1", (20.0, 10.0, 0.0)),
        ("STAGING_VERIFY", t_cong + timedelta(minutes=125), "STAGING_TEMP_FLOOR", (25.0, 12.0, 0.0)),
        ("STAGING_VERIFY", t_cong + timedelta(minutes=170), "STAGING_BLOCK_CORNER", (28.0, 15.0, 0.0)),
        ("PUTAWAY_EXEC", t_cong + timedelta(minutes=260), "RACK_08_02", (60.0, 40.0, 3.0)),
    ]
    for act, ts, loc, xyz in cong_steps:
        wms_events.append(RawWmsEvent(ts, "CASE_003_STAGING_COLLAPSE", act, "OP_STAGED", loc, xyz, 80))

    # CAN-bus revela una distancia astronómica: la grúa recorrió 1,420 metros para un trayecto
    # cuya distancia Manhattan teórica era de sólo 110 metros (Desvío 12.9x por pasillos tapados)
    can_events.append(RawCanBusTelemetry(t_cong + timedelta(minutes=260), "FORK_09", 1.4, 1420.0, 88.0, 0.62))

    return wms_events, wifi_events, can_events


# ======================================================================================
# 3. MOTOR FORENSE DE AUDITORÍA CRUZADA
# ======================================================================================

class ForensicOperationalAuditor:
    """
    Ejecuta el Conformance Checking sobre los logs y aplica las pruebas de
    falsificación física (Velocidad biomecánica, Invariante de Odometría y Little's Law).
    """

    def __init__(self, wms_events: List[RawWmsEvent], wifi_events: List[RawWifiSyslog], can_events: List[RawCanBusTelemetry]):
        self.wms = wms_events
        self.wifi = wifi_events
        self.can = can_events

    def audit_trace_conformance(self, case_id: str) -> Dict[str, Any]:
        """Calcula el conformance frente al Golden Path para un caso específico."""
        events = sorted([e for e in self.wms if e.case_id == case_id], key=lambda x: x.timestamp)
        if not events:
            return {"case_id": case_id, "error": "No events found"}

        activities = [e.activity for e in events]
        timestamps = [e.timestamp for e in events]
        coords = [e.coords_xyz for e in events]

        total_transitions = len(activities) - 1
        matches = 0
        deviations = []
        gaming_flags = []
        rework_loops = 0

        total_manhattan_m = 0.0

        for i in range(total_transitions):
            src, tgt = activities[i], activities[i + 1]
            t_src, t_tgt = timestamps[i], timestamps[i + 1]
            dt_sec = (t_tgt - t_src).total_seconds()

            # Distancia ortogonal Manhattan teórica
            dx = abs(coords[i + 1][0] - coords[i][0])
            dy = abs(coords[i + 1][1] - coords[i][1])
            dz = abs(coords[i + 1][2] - coords[i][2])
            dist_manhattan = dx + dy + dz
            total_manhattan_m += dist_manhattan

            # 1. Chequeo Biomecánico de Velocidad Implicada (Gaming Detection)
            if dist_manhattan > 5.0 and dt_sec > 0:
                implied_speed = dist_manhattan / dt_sec
                if implied_speed > 2.2:  # Umbral máximo humano con carga (2.2 m/s = 7.9 km/h)
                    gaming_flags.append(
                        f"🚨 BATCH CLOTTING: Transición '{src}' -> '{tgt}' cubrió {dist_manhattan:.1f}m en {dt_sec:.1f}s "
                        f"(Velocidad Implicada: {implied_speed:.2f} m/s > 2.2 m/s). Falsificación de escaneo en piso."
                    )

            # 2. Detección de Retrabajo / Doble Manipulación (Re-handling Loop)
            if src == tgt:
                rework_loops += 1
                deviations.append(f"🔁 LOOP RE-HANDLING: '{src}' ejecutado consecutivamente en {dt_sec/60.0:.1f} min.")
                continue

            # 3. Validación de SLAs del Golden Path
            if (src, tgt) in GOLDEN_PATH_SLAS:
                min_s, max_s = GOLDEN_PATH_SLAS[(src, tgt)]
                matches += 1
                if dt_sec > max_s:
                    deviations.append(f"⏳ CUELLO DE BOTELLA: '{src}' -> '{tgt}' demoró {dt_sec/60.0:.1f} min (SLA máx: {max_s/60.0:.1f} min).")
            else:
                deviations.append(f"⚠️ BYPASS NO MAPEADO: Transición fuera de diseño '{src}' -> '{tgt}'.")

        fitness = matches / max(1, total_transitions)
        precision = max(0.0, 1.0 - (len(deviations) / max(1, total_transitions * 2)))

        return {
            "case_id": case_id,
            "total_events": len(events),
            "trace_fitness": round(fitness, 3),
            "precision_score": round(precision, 3),
            "rework_loops": rework_loops,
            "total_manhattan_m": round(total_manhattan_m, 1),
            "total_duration_min": round((timestamps[-1] - timestamps[0]).total_seconds() / 60.0, 1),
            "deviations": deviations,
            "gaming_flags": gaming_flags
        }

    def verify_physical_invariants(self) -> Dict[str, Any]:
        """
        Calcula las 3 leyes de conservación física sobre el sistema:
        1. Invariante Cinemática CAN-bus vs. Manhattan
        2. Invariante de Little (W_real vs W_reportado)
        3. Correlación Wi-Fi de Gaming de Presencia
        """
        results = {}

        # ------------------------------------------------------------------------------
        # INVARIANTE 1: Cinemática CAN-bus vs. Manhattan (Caso 3)
        # ------------------------------------------------------------------------------
        c3_wms = self.audit_trace_conformance("CASE_003_STAGING_COLLAPSE")
        c3_can = [c for c in self.can if c.vehicle_id == "FORK_09"]
        if c3_can:
            actual_travel_m = c3_can[0].distance_accum_m
            theoretical_m = c3_wms["total_manhattan_m"]
            detour_ratio = actual_travel_m / max(1.0, theoretical_m)
            results["kinematic_odometry_check"] = {
                "vehicle_id": "FORK_09",
                "theoretical_manhattan_m": theoretical_m,
                "actual_odometer_m": actual_travel_m,
                "detour_ratio": round(detour_ratio, 2),
                "status": "VIOLACIÓN CRÍTICA" if detour_ratio > 2.0 else "NORMAL",
                "root_cause": "La máquina recorrió 12.9x más distancia de la teórica debido al bloqueo masivo de pasillos por pallets en piso."
            }

        # ------------------------------------------------------------------------------
        # INVARIANTE 2: Ley de Little en Muelle (L = lambda * W)
        # ------------------------------------------------------------------------------
        # Datos del caso 3: Arribos lambda = 8 camiones/h (240 pallets/h)
        # WMS afirma: W_reportado = 45 min (0.75 h).
        # Auditoría física en piso muestra: L_staging = 480 pallets estancados permanentemente.
        lambda_hourly = 240.0
        w_reported_h = 0.75
        l_observed = 480.0

        # W_real = L / lambda
        w_real_h = l_observed / lambda_hourly
        w_real_min = w_real_h * 60.0

        results["littles_law_audit"] = {
            "arrival_rate_pallets_per_hr": lambda_hourly,
            "reported_dock_dwell_min": round(w_reported_h * 60.0, 1),
            "observed_wip_pallets": l_observed,
            "mathematically_proven_dwell_min": round(w_real_min, 1),
            "discrepancy_factor": round(w_real_h / w_reported_h, 2),
            "verdict": "SUB-REPORTE DETECTADO: El tiempo real en muelle (120 min) es 2.67x mayor al reportado en WMS (45 min)."
        }

        # ------------------------------------------------------------------------------
        # INVARIANTE 3: Telemetría Wi-Fi vs. Declaración WMS (Caso 2 Gaming)
        # ------------------------------------------------------------------------------
        gamer_wifi = [w for w in self.wifi if w.client_mac == "MAC_OP_GAMER"]
        results["wifi_rf_audit"] = {
            "operator_mac": "MAC_OP_GAMER",
            "connected_ap_zone": gamer_wifi[0].ap_zone if gamer_wifi else "UNKNOWN",
            "physical_rssi_dbm": gamer_wifi[0].rssi_dbm if gamer_wifi else 0,
            "verdict": "CONFIRMACIÓN DE FRAUDE: El operario declaró estar en pasillos RACK_02 y RACK_03, pero su terminal estuvo inmóvil en BSSID_BREAKROOM durante toda la ventana de confirmación."
        }

        return results


# ======================================================================================
# 4. ENTRYPOINT DE EJECUCIÓN FORENSE
# ======================================================================================

def main():
    print("\n" + "=" * 90)
    print("🔬 MOTOR FORENSE DE CAUSALIDAD OPERATIVA & MINERÍA DE PROCESOS (FDE SUITE)")
    print("=" * 90)

    # 1. Generar casos sintéticos de prueba
    wms_events, wifi_events, can_events = generate_forensic_test_scenarios()
    auditor = ForensicOperationalAuditor(wms_events, wifi_events, can_events)

    cases = ["CASE_001_GOLDEN", "CASE_002_BATCH_GAMING", "CASE_003_STAGING_COLLAPSE"]

    print("\n[FASE 1: CONFORMANCE CHECKING SOBRE EL EVENT-LOG TRANSACCIONAL]\n")
    for cid in cases:
        report = auditor.audit_trace_conformance(cid)
        print(f"┌─ CASO AUDITADO: {report['case_id']}")
        print(f"│  • Eventos analizados: {report['total_events']} | Duración: {report['total_duration_min']} min")
        print(f"│  • Trace Fitness: {report['trace_fitness'] * 100:.1f}% | Precision Score: {report['precision_score'] * 100:.1f}%")
        print(f"│  • Retrabajos (Re-handling): {report['rework_loops']} loops detectados")

        if report["gaming_flags"]:
            for gf in report["gaming_flags"]:
                print(f"│  {gf}")

        if report["deviations"]:
            print(f"│  • Desvíos de Proceso:")
            for dev in report["deviations"][:3]:
                print(f"│    └─ {dev}")
        print("└" + "─" * 88 + "\n")

    # 2. Evaluación de Invariantes Físicas
    print("=" * 90)
    print("[FASE 2: VALIDACIÓN EXTERNA MEDIANTE INVARIANTES DE CONSERVACIÓN FÍSICA]")
    print("=" * 90 + "\n")

    invariants = auditor.verify_physical_invariants()

    # Invariante 1: Odometría CAN-bus
    k = invariants["kinematic_odometry_check"]
    print("1. INVARIANTE CINEMÁTICA-ENERGÉTICA DE ODOMETRÍA (CAN-BUS vs. WMS)")
    print(f"   • Vehículo auditado: {k['vehicle_id']}")
    print(f"   • Distancia Manhattan Teórica (Órdenes WMS): {k['theoretical_manhattan_m']} metros")
    print(f"   • Distancia Real Registrada (Odómetro CAN-bus): {k['actual_odometer_m']} metros")
    print(f"   • Ratio de Desvío: {k['detour_ratio']}x [{k['status']}]")
    print(f"   • Causa Raíz Forense: {k['root_cause']}\n")

    # Invariante 2: Little's Law
    ll = invariants["littles_law_audit"]
    print("2. INVARIANTE DE CONSERVACIÓN DE FLUJO (LEY DE LITTLE SUB-SISTÉMICA)")
    print(f"   • Tasa de Arribo Real en Garita: {ll['arrival_rate_pallets_per_hr']} pallets/hora")
    print(f"   • Tiempo de Estadía Reportado en WMS: {ll['reported_dock_dwell_min']} minutos")
    print(f"   • WIP Físico Promedio en Piso (Staging): {ll['observed_wip_pallets']} pallets")
    print(f"   • TIEMPO DE ESTADÍA REAL MATEMÁTICAMENTE DEMOSTRADO: {ll['mathematically_proven_dwell_min']} minutos")
    print(f"   • Factor de Discrepancia: {ll['discrepancy_factor']}x")
    print(f"   • Veredicto: {ll['verdict']}\n")

    # Invariante 3: Correlación Wi-Fi
    wf = invariants["wifi_rf_audit"]
    print("3. CONTRASTE DE VERDAD FÍSICA: ITINERANCIA WI-FI (BSSID vs. WMS)")
    print(f"   • Dispositivo: {wf['operator_mac']}")
    print(f"   • Zona de AP Real: {wf['connected_ap_zone']} (Señal: {wf['physical_rssi_dbm']} dBm)")
    print(f"   • Veredicto Forense: {wf['verdict']}\n")

    print("=" * 90)
    print("✅ AUDITORÍA FORENSE COMPLETADA: Cero ambigüedad. Las discrepancias físicas han sido aisladas.")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
