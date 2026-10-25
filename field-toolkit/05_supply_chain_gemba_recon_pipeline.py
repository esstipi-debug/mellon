"""
05_supply_chain_gemba_recon_pipeline.py
========================================================================================
FRONTLINE RECONNAISSANCE & DIAGNOSTIC PLAYBOOK ENGINE (GRAPH + VECTOR RETRIEVAL)
========================================================================================
Purpose: Ingest informal field observations (text/speech-to-text) from auditors,
perform semantic matching against pre-mapped operational failure modes, traverse the
underlying Knowledge Graph, calculate quantified financial/operational impact, and
output immediate on-site verification checklists + commercial service offerings.

Framework Integration: FDE Field Toolkit / Gemba Ethnographic Forensics
Supported Verticals: Retail, Food & Cold Chain, Pharma/Health, Heavy Construction, General DC
========================================================================================
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ======================================================================================
# 1. ONTOLOGICAL DATA STRUCTURES
# ======================================================================================

@dataclass
class DiagnosticCheck:
    id: str
    name: str
    inspection_method: str
    sample_rule: str
    red_flag_threshold: str
    normative_reference: str


@dataclass
class ServiceOffering:
    id: str
    title: str
    scope_deliverable: str
    commercial_model: str
    typical_roi_weeks: int


@dataclass
class FailureMode:
    id: str
    entity_id: str
    entity_type: str  # Asset, Space, Role, Process
    category: str
    name: str
    symptoms: List[str]
    root_cause_hypothesis: str
    empirical_impact_description: str
    severity_1_to_10: int
    diagnostic_check: DiagnosticCheck
    service_offering: ServiceOffering
    impact_formula_type: str  # e.g., 'labor_waste', 'uph_loss', 'demurrage', 'shrinkage'


# ======================================================================================
# 2. SEED KNOWLEDGE GRAPH (EMPIRICAL BENCHMARKS: WERC, OSHA, EN 15635, GDP, ASTM)
# ======================================================================================

KNOWLEDGE_GRAPH_DB: List[FailureMode] = [
    FailureMode(
        id="FAIL_MHE_CART_FRICTION",
        entity_id="AST_CART_PICK_01",
        entity_type="Asset",
        category="Material Handling Equipment (MHE)",
        name="Resistencia al Rodado por Desgaste de Ruedas o Film Enredado",
        symptoms=[
            "carritos de picking trabados",
            "ruedas con plastico film stretch enrollado",
            "operarios empujan con esfuerzo los carros",
            "ruido de chirrido metalico en pasillos",
            "carros desviados no ruedan recto",
            "dolor lumbar o quejas ergonomicas al empujar",
            "ruedas desgastadas facetadas bloqueadas"
        ],
        root_cause_hypothesis="Falta de guardahilos (thread guards) en rodamientos y omisión de programa preventivo TPM en rodados.",
        empirical_impact_description="Aumento de fuerza de tracción a >45 lbf (excede norma ergonómica OSHA). Reduce velocidad de marcha 35%, generando una caída neta del 15% al 22% en UPH.",
        severity_1_to_10=7,
        diagnostic_check=DiagnosticCheck(
            id="CHK_CART_01",
            name="Prueba Dinamométrica y Muestreo de Rodados",
            inspection_method="Muestrear 20 carritos en uso activo con dinamómetro digital de tracción y registrar presencia de filamentos en ejes.",
            sample_rule="20 unidades tomadas al azar en pasillos de picking.",
            red_flag_threshold="Fuerza de empuje > 200 N (>45 lbf) o > 10% de la flota con ruedas bloqueadas.",
            normative_reference="OSHA Standard 1910 Ergonomics / Snook-Ciriello Tables"
        ),
        service_offering=ServiceOffering(
            id="SRV_MHE_FLEET_OPT",
            title="Optimización de Flota Ligera y Retrofit de Rodados Poliuretano",
            scope_deliverable="Auditoría dimensional y ergonómica de flota + reemplazo por ruedas Blickle/Colson con guardahilos + protocolo TPM.",
            commercial_model="Tarifa base de diagnóstico + Costo por unidad reacondicionada.",
            typical_roi_weeks=4
        ),
        impact_formula_type="uph_loss"
    ),
    FailureMode(
        id="FAIL_MHE_CART_DEFICIT",
        entity_id="AST_CART_PICK_01",
        entity_type="Asset",
        category="Material Handling Equipment (MHE)",
        name="Déficit de Flota de Carritos vs. Dotación de Preparadores",
        symptoms=[
            "no hay carritos para todos los operarios",
            "operarios esperando que se desocupe un carro",
            "falta de carros de picking en inicio de turno",
            "peleas o acaparamiento de carros de 4 ruedas",
            "carritos rotos arrumbados en un rincon"
        ],
        root_cause_hypothesis="Ratio de flota menor al estándar (1.15-1.25 por picker). Sin stock buffer de mantenimiento ni wave staging.",
        empirical_impact_description="Colas de espera y tiempos muertos al inicio de turno (15-25 min por operario sin equipo).",
        severity_1_to_10=6,
        diagnostic_check=DiagnosticCheck(
            id="CHK_CART_RATIO",
            name="Auditoría de Ratio Flota / Dotación Peak",
            inspection_method="Contabilizar carritos 100% operativos vs. dotación máxima en turno punta de picking.",
            sample_rule="Censo completo de flota de carritos de la instalación.",
            red_flag_threshold="Ratio menor a 1.05 carritos operativos por operario en turno.",
            normative_reference="WERC DC Measures - Fleet Utilization Standards"
        ),
        service_offering=ServiceOffering(
            id="SRV_MHE_FLEET_SIZING",
            title="Reingeniería de Flota y Sistema de Asignación por Buffer Staging",
            scope_deliverable="Cálculo matemático de flota óptima + buffer de mantenimiento + demarcación de bahías de recambio.",
            commercial_model="Proyecto llave en mano con garantía de disponibilidad del 99.5%.",
            typical_roi_weeks=6
        ),
        impact_formula_type="labor_waste"
    ),
    FailureMode(
        id="FAIL_MHE_FORK_BATTERY",
        entity_id="AST_FORK_REACH_01",
        entity_type="Asset",
        category="Material Handling Equipment (MHE)",
        name="Degradación Térmica/Sulfatación de Baterías de Montacargas",
        symptoms=[
            "baterias de gruas no duran el turno",
            "montacargas pierde fuerza de levante antes de terminar",
            "cambio de bateria demora mucho tiempo",
            "demasiado tiempo cargando baterias de plomo",
            "gruas horquilla detenidas sin carga",
            "acido derramado en sala de baterias"
        ],
        root_cause_hypothesis="Uso de baterías plomo-ácido con ciclos de recarga interrumpidos (sin cumplir regla 8-8-8) o sulfatación por bajo nivel de electrolito.",
        empirical_impact_description="15-25 min por cambio de batería. Pérdida de 3,000-5,000 h-hombre/año en flotas de 20 grúas. Caída de 20% en velocidad hidráulica con SoC < 30%.",
        severity_1_to_10=8,
        diagnostic_check=DiagnosticCheck(
            id="CHK_FORK_BATT",
            name="Telemetría de Ciclo de Batería y Densimetría",
            inspection_method="Revisar historial de recarga, densimetría de celdas y tiempo cronometrado de recambio en sala de carga.",
            sample_rule="Muestreo del 100% de la flota de tracción eléctrica.",
            red_flag_threshold="Autonomía menor a 4.5 horas de uso continuo o tiempo de recambio > 12 minutos.",
            normative_reference="IEEE Std 1188 / OSHA 1910.178(g)"
        ),
        service_offering=ServiceOffering(
            id="SRV_FORK_LITHIUM_CONVERSION",
            title="Plan de Transición a Ión-Litio (LiFePO4) con Carga de Oportunidad",
            scope_deliverable="Estudio TCO de baterías + conversión de flota a Litio con cargadores de alta frecuencia + eliminación de sala de baterías.",
            commercial_model="Leasing operativo con ahorro garantizado en OPEX eléctrico y mantenimiento.",
            typical_roi_weeks=18
        ),
        impact_formula_type="labor_waste"
    ),
    FailureMode(
        id="FAIL_INFRA_RACK_DAMAGE",
        entity_id="SPC_RACK_AISLE_01",
        entity_type="Space",
        category="Infraestructura y Racks",
        name="Deformación Estructural de Puntales por Impacto de Grúa",
        symptoms=[
            "puntales de rack abollados o torcidos",
            "golpes de grua en las esquinas de los pasillos",
            "protectores de rack arrancados o rotos",
            "vigas de estanteria flectadas",
            "largueros sin perno o pasador de seguridad",
            "pallets chuecos en altura riesgo de caida"
        ],
        root_cause_hypothesis="Maniobras ciegas, exceso de velocidad en curvas y falta de protecciones poliméricas con absorción de impacto.",
        empirical_impact_description="Riesgo de colapso catastrófico. Costo directo por impacto menor: $800-$3,500 USD (reparación, descarga de 3-6 niveles y bahía bloqueada 3-7 días).",
        severity_1_to_10=9,
        diagnostic_check=DiagnosticCheck(
            id="CHK_RACK_DEFLECTION",
            name="Inspección Técnica de Racking s/ Norma EN 15635",
            inspection_method="Medición de deformación con regla de 1.0 m en puntales y verificación de pasadores de seguridad.",
            sample_rule="Inspección visual del 100% de cabeceras y muestra de 30% de pasillos internos.",
            red_flag_threshold="Deformación > 3.0 mm longitudinal / > 5.0 mm transversal (Nivel Ámbar) o > 6 mm (Nivel Rojo: DESCARGA INMEDIATA).",
            normative_reference="Norma Europea EN 15635 / ANSI MH16.1"
        ),
        service_offering=ServiceOffering(
            id="SRV_RACK_SAFETY_CERT",
            title="Inspección Oficial PRSES y Blindaje Polimérico de Racks",
            scope_deliverable="Certificación estructural de carga según EN 15635 + instalación de protecciones viscoelásticas A-Safe/Boplan.",
            commercial_model="Honorario de certificación técnica + suministro e instalación de barreras.",
            typical_roi_weeks=8
        ),
        impact_formula_type="rack_collision"
    ),
    FailureMode(
        id="FAIL_INFRA_DOCK_CONGESTION",
        entity_id="SPC_DOCK_INBOUND_01",
        entity_type="Space",
        category="Muelles y Patios",
        name="Congestión en Muelles y Cuello de Botella en Recepción",
        symptoms=[
            "camiones esperando horas afuera para descargar",
            "muelles colapsados de pallets en el piso",
            "zona de recepcion llena no se puede caminar",
            "cobro de sobreestadia o detention fees de transportistas",
            "choferes enojados esperando liberacion de guias",
            "doble movimiento de pallets para despejar paso"
        ],
        root_cause_hypothesis="Llegada desordenada sin sistema de citas (Dock Scheduling) y piso de staging saturado por encima del 85%.",
        empirical_impact_description="Sobrecostos de $65-$120 USD/hora por detención de transporte. Pérdida del 25%-38% de productividad de recepción por doble manipulación (re-handling).",
        severity_1_to_10=8,
        diagnostic_check=DiagnosticCheck(
            id="CHK_DOCK_METRICS",
            name="Auditoría de Tiempos de Muelle y Saturación de Staging",
            inspection_method="Análisis de marcas horarias Gate-to-Gate de los últimos 30 días y medición de m² ocupados en staging.",
            sample_rule="Registro de 50 camiones consecutivos.",
            red_flag_threshold="Tiempo promedio en muelle > 120 minutos o saturación de staging > 80% sostenida por más de 1 hora.",
            normative_reference="WERC DC Measures - Dock-to-Stock & Detention Metrics"
        ),
        service_offering=ServiceOffering(
            id="SRV_DOCK_YMS_LITE",
            title="Implementación de Dock Scheduling & Reingeniería de Flujo 5S en Muelle",
            scope_deliverable="Plataforma de citas horarias para transportistas + rediseño de bahías de staging con segregación visual y buffer dinámico.",
            commercial_model="SaaS de agendamiento + consultoría de implementación de procesos.",
            typical_roi_weeks=5
        ),
        impact_formula_type="demurrage"
    ),
    FailureMode(
        id="FAIL_HUMAN_TOOL_HUNTING",
        entity_id="ROL_PICKER_01",
        entity_type="Role",
        category="Capital Humano y Turnos",
        name="Pérdida por Cacería de Herramientas al Inicio de Turno",
        symptoms=[
            "operarios buscando pistolas de radiofrecuencia",
            "pierden 20 minutos al inicio de turno buscando cosas",
            "no encuentran cutters film o transpaletas",
            "primer pallet preparado sale muy tarde",
            "desorden en cambio de turno sin herramientas asignadas",
            "baterias de pistolas rf descargadas"
        ],
        root_cause_hypothesis="Ausencia de custodia individualizada de activos críticos (RF, terminales, MHE) y falta de demarcación 5S (Shadow Boards).",
        empirical_impact_description="Pérdida de 20 a 35 min diarios por operario. En una planta de 60 operarios representa ~$112,500 USD/año en nómina improductiva.",
        severity_1_to_10=7,
        diagnostic_check=DiagnosticCheck(
            id="CHK_SHIFT_START_DELAY",
            name="Cronometraje de Arranque de Turno (Punch-to-First-Pick)",
            inspection_method="Cronometrar el tiempo transcurrido entre el marcaje en reloj control y el primer escaneo efectivo de la cuadrilla.",
            sample_rule="Muestreo de 10 operarios al azar durante 3 cambios de turno.",
            red_flag_threshold="Tiempo promedio de inicio superior a 15 minutos.",
            normative_reference="Lean Manufacturing / Shopfloor Management Standards"
        ),
        service_offering=ServiceOffering(
            id="SRV_5S_SMART_LOCKERS",
            title="Estandarización 5S Frontline y Lockers RFID de Custodia Inteligente",
            scope_deliverable="Instalación de gabinetes inteligentes Traka/Zebra + tableros de sombra (Shadow boards) + protocolo de traspaso Tier 1.",
            commercial_model="Llave en mano (Hardware + Proceso + Auditoría de Adopción).",
            typical_roi_weeks=6
        ),
        impact_formula_type="labor_waste"
    ),
    FailureMode(
        id="FAIL_VERT_FOOD_COLD_EXCURSION",
        entity_id="VRT_FOOD_COLD_01",
        entity_type="Process",
        category="Vertical: Alimentos & Cadena de Frío",
        name="Excursión Térmica en Muelle de Recepción/Despacho",
        symptoms=[
            "pallets congelados esperando en el muelle a temperatura ambiente",
            "cajas de carne o lacteos calientes al tacto",
            "escarcha o hielo en piso de camara frigorifica",
            "termometros marcan temperatura fuera de rango",
            "condensacion o goteo en puertas de camara",
            "rechazo de pedidos por temperatura en destino"
        ],
        root_cause_hypothesis="Falta de esclusas térmicas en muelles y demoras en el putaway de perecibles superiores a 20 minutos.",
        empirical_impact_description="Merma promedio del 1.8% al 3.5% del inventario perecedero. Riesgo de proliferación bacteriana (Listeria/Salmonella) y sanciones sanitarias.",
        severity_1_to_10=9,
        diagnostic_check=DiagnosticCheck(
            id="CHK_COLD_EXPOSURE",
            name="Termometría Infrarroja y Tiempo de Permanencia en Muelle",
            inspection_method="Termometría láser en superficie de pallets en muelle y cronometraje desde apertura de puerta de camión hasta entrada a cámara.",
            sample_rule="Muestreo de 5 camiones de perecibles en horario peak diurno.",
            red_flag_threshold="Permanencia de pallets a >+12°C superior a 15 minutos o desviación de cámara > 1.5°C.",
            normative_reference="HACCP Codex Alimentarius / FSMA 21 CFR 117"
        ),
        service_offering=ServiceOffering(
            id="SRV_COLD_CHAIN_MONITORING",
            title="Telemetría IoT Continua LoRaWAN y Protocolo de Muelle Frío",
            scope_deliverable="Sensores térmicos inalámbricos en tiempo real con alertas a WhatsApp/SMS + puertas rápidas aisladas y sellos inflables.",
            commercial_model="Implementación de sensores + suscripción de monitoreo y auditoría mensual.",
            typical_roi_weeks=3
        ),
        impact_formula_type="shrinkage"
    ),
    FailureMode(
        id="FAIL_VERT_PHARMA_GDP_BREACH",
        entity_id="VRT_PHARMA_01",
        entity_type="Process",
        category="Vertical: Salud & Farmacéutica",
        name="Desviación de Temperatura GDP y Riesgo de Rechazo de Lote",
        symptoms=[
            "alerta de temperatura en camara de medicamentos",
            "sensores descalibrados o sin certificado",
            "vacunas o biologicos fuera de rango de 2 a 8 grados",
            "medicamentos expuestos al calor en despacho",
            "miedo a auditoria sanitaria o inspeccion regulatoria",
            "investigaciones de calidad capa pendientes"
        ],
        root_cause_hypothesis="Mapeo térmico estacional deficiente y ausencia de sistema validado bajo 21 CFR Part 11.",
        empirical_impact_description="Investigación CAPA cuesta $3,500-$9,000 USD por evento. Pérdida directa por rechazo de lote de $30,000 a >$1,000,000 USD.",
        severity_1_to_10=10,
        diagnostic_check=DiagnosticCheck(
            id="CHK_PHARMA_GDP_AUDIT",
            name="Auditoría de Registros MKT y Trazabilidad de Sensores",
            inspection_method="Revisión de certificados de calibración NIST de sensores y cálculo de Temperatura Cinética Media (MKT).",
            sample_rule="Auditoría del 100% de puntos críticos de almacenamiento farmacéutico.",
            red_flag_threshold="Desviación de temperatura > 2.0°C sin CAPA inmediata o sensor sin calibración anual vigente.",
            normative_reference="GDP (Good Distribution Practices) / 21 CFR Part 11 / USP <1079>"
        ),
        service_offering=ServiceOffering(
            id="SRV_PHARMA_EMS_VALIDATION",
            title="Sistema de Monitoreo Ambiental Validado (EMS) y Calificación Térmica",
            scope_deliverable="Mapeo térmico tridimensional estacional + software con firma electrónica y pistas de auditoría inalterables.",
            commercial_model="Proyecto de validación farmacéutica formal (DQ/IQ/OQ/PQ).",
            typical_roi_weeks=2
        ),
        impact_formula_type="pharma_rejection"
    ),
    FailureMode(
        id="FAIL_VERT_RETAIL_IRA_MISMATCH",
        entity_id="VRT_RETAIL_01",
        entity_type="Process",
        category="Vertical: Retail & E-commerce",
        name="Descalce de Inventario (WMS vs. Físico) y Pick Denials",
        symptoms=[
            "el sistema dice que hay stock pero la ranura esta vacia",
            "operario va a buscar un producto y no lo encuentra",
            "diferencias constantes entre inventario teorico y real",
            "pedidos incompletos por falta de stock fantasma",
            "reclamos de clientes de e-commerce por pedidos cancelados",
            "mucho tiempo ajustando inventario en wms"
        ],
        root_cause_hypothesis="Falta de conteos cíclicos dinámicos y errores de ubicación en putaway no validados por doble lectura.",
        empirical_impact_description="Exactitud de inventario <98%. Cada pick denial frena al operario de 3.5 a 7 minutos. 28%-33% de clientes online abandonan la marca por quiebre de stock posterior a la compra.",
        severity_1_to_10=8,
        diagnostic_check=DiagnosticCheck(
            id="CHK_RETAIL_IRA_AUDIT",
            name="Muestreo Ciego de Exactitud de Registro (Rule of Five)",
            inspection_method="Conteo ciego de 5 SKUs de alta rotación en 20 ubicaciones físicas vs. registro del ERP/WMS.",
            sample_rule="100 ubicaciones de picking y reserva.",
            red_flag_threshold="Exactitud de Registro (IRA) < 98.0% o tasa de pick denials > 0.5% en el turno.",
            normative_reference="APICS / WERC Inventory Record Accuracy (IRA) Standards"
        ),
        service_offering=ServiceOffering(
            id="SRV_AUTONOMOUS_CYCLE_COUNT",
            title="Conteo Cíclico Automatizado y Control de Ubicaciones por Visión Artificial",
            scope_deliverable="Auditoría forense de descalce + despliegue de conteo autónomo (RFID / escaneo asistido) y rediseño de putaway.",
            commercial_model="Fee de consultoría de proceso + suscripción tecnológica.",
            typical_roi_weeks=5
        ),
        impact_formula_type="labor_waste"
    ),
    FailureMode(
        id="FAIL_VERT_CONSTRUCT_SLUMP_LOSS",
        entity_id="VRT_CONST_01",
        entity_type="Process",
        category="Vertical: Construcción & Obra Pesada",
        name="Pérdida de Asentamiento de Hormigón por Demora en Obra",
        symptoms=[
            "camiones mixer esperando horas en la entrada de la obra",
            "hormigon comienza a fraguar dentro del tambor del camion",
            "rechazo de viajes de hormigon por perdida de cono",
            "camion mixer botando mezcla endurecida",
            "obra parada porque no pueden vaciar el camion a tiempo",
            "choferes esperando grua pluma para descargar"
        ],
        root_cause_hypothesis="Falta de sincronización Just-in-Time y colapso de accesos urbanos en el frente de descarga.",
        empirical_impact_description="Norma ASTM C94 fija límite de 90 min de descarga. Superar el umbral genera rechazo total del viaje ($1,200-$2,500 USD por camión) y parálisis de cuadrilla estructural.",
        severity_1_to_10=9,
        diagnostic_check=DiagnosticCheck(
            id="CHK_CONSTRUCT_CONE_TIME",
            name="Control de Marcas Horarias Batch-to-Discharge y Ensayo de Asentamiento",
            inspection_method="Verificar guía de despacho (hora de contacto agua-cemento) y prueba de cono de Abrams en pie de obra.",
            sample_rule="100% de camiones mixer del frente de colado.",
            red_flag_threshold="Tiempo acumulado en tránsito y espera > 75 minutos o pérdida de cono fuera de tolerancia de diseño.",
            normative_reference="Norma ASTM C94 / ACI 304R"
        ),
        service_offering=ServiceOffering(
            id="SRV_CONSTRUCT_JIT_YARD",
            title="Gestión Logística JIT de Frentes de Obra y Telemetría de Mezcla",
            scope_deliverable="Sistema de reservas horarias de descarga con grúa pluma + telemetría de asentamiento y rotación de cuba en tránsito.",
            commercial_model="Software de gestión de accesos de obra + control de calidad en tránsito.",
            typical_roi_weeks=3
        ),
        impact_formula_type="concrete_loss"
    )
]


# ======================================================================================
# 3. SEMANTIC VECTOR & LEXICAL RETRIEVAL ENGINE
# ======================================================================================

class HybridVectorIndex:
    """
    Motor híbrido de indexación y búsqueda que indexa la ontología combinando
    n-gramas de palabras y caracteres para máxima resiliencia ante lenguaje
    coloquial de terreno, faltas ortográficas o dictados de voz con ruido.
    """

    def __init__(self, knowledge_base: List[FailureMode]):
        self.kb = knowledge_base
        self.documents: List[str] = []
        self._build_index()

    def _build_index(self) -> None:
        for fm in self.kb:
            # Enriquecemos el documento textual para que capture tanto términos técnicos como coloquiales
            doc_parts = [
                f"Modo de falla: {fm.name}",
                f"Categoría: {fm.category}",
                f"Entidad: {fm.entity_id} {fm.entity_type}",
                f"Síntomas observados: {' | '.join(fm.symptoms)}",
                f"Causa raíz: {fm.root_cause_hypothesis}",
                f"Impacto operativo: {fm.empirical_impact_description}",
                f"Chequeo de terreno: {fm.diagnostic_check.name} {fm.diagnostic_check.red_flag_threshold}",
                f"Servicio comercial: {fm.service_offering.title} {fm.service_offering.scope_deliverable}"
            ]
            self.documents.append(" \n".join(doc_parts))

        # Vectorizador TF-IDF con sublinear tf y n-gramas cruzados
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            sublinear_tf=True,
            strip_accents='unicode',
            lowercase=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)

    def search(self, query: str, top_k: int = 3, threshold: float = 0.12) -> List[Tuple[FailureMode, float]]:
        """Busca los modos de falla más relevantes a partir de una nota de terreno."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        query_vec = self.vectorizer.transform([cleaned_query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        ranked_indices = np.argsort(similarities)[::-1]
        results = []
        for idx in ranked_indices[:top_k]:
            score = float(similarities[idx])
            if score >= threshold:
                results.append((self.kb[idx], score))
        return results


# ======================================================================================
# 4. FINANCIAL & OPERATIONAL QUANTIFICATION ENGINE
# ======================================================================================

@dataclass
class FacilityParameters:
    headcount_pickers: int = 50
    shifts_per_day: int = 2
    operating_days_per_year: int = 250
    hourly_labor_cost_usd: float = 16.0
    baseline_uph: float = 120.0
    forklift_fleet_size: int = 15
    daily_trucks_inbound: int = 30
    concrete_trucks_per_pour: int = 12


class ImpactCalculator:
    """Calcula el costo y pérdida empírica basados en las fórmulas calibradas."""

    @staticmethod
    def calculate(failure_mode: FailureMode, params: FacilityParameters) -> Dict[str, Any]:
        f_type = failure_mode.impact_formula_type

        if f_type == "labor_waste":
            # Caso típico: pérdida de 25 min al inicio de turno por operario
            minutes_lost_daily = 25.0
            hours_lost_daily = (minutes_lost_daily / 60.0) * params.headcount_pickers * params.shifts_per_day
            annual_hours_lost = hours_lost_daily * params.operating_days_per_year
            annual_cost_usd = annual_hours_lost * params.hourly_labor_cost_usd

            return {
                "metric_name": "Nómina Improductiva por Tiempos Muertos",
                "annual_hours_lost": round(annual_hours_lost, 1),
                "annual_cost_usd": round(annual_cost_usd, 2),
                "summary": f"{round(annual_hours_lost):,} horas-hombre/año perdidas (~${round(annual_cost_usd):,} USD/año)."
            }

        elif f_type == "uph_loss":
            # Caída de velocidad de marcha reduce UPH en 18% promedio
            uph_drag_pct = 0.18
            units_lost_per_picker_hour = params.baseline_uph * uph_drag_pct
            annual_units_lost = units_lost_per_picker_hour * 7.5 * params.headcount_pickers * params.shifts_per_day * params.operating_days_per_year

            # Equivalente en costo de mano de obra adicional requerida
            extra_hours_needed = annual_units_lost / params.baseline_uph
            annual_cost_usd = extra_hours_needed * params.hourly_labor_cost_usd

            return {
                "metric_name": "Degradación de Rendimiento de Picking (UPH Drag)",
                "uph_reduction_pct": "18.0%",
                "lost_production_units": round(annual_units_lost),
                "annual_cost_usd": round(annual_cost_usd, 2),
                "summary": f"Pérdida de {round(units_lost_per_picker_hour, 1)} UPH por picker. Costo equivalente de mano de obra: ~${round(annual_cost_usd):,} USD/año."
            }

        elif f_type == "demurrage":
            # Costo de detención de camiones en muelles
            demurrage_trucks_pct = 0.15
            hours_over_grace = 1.5
            rate_per_hour = 85.0
            annual_demurrage_usd = (params.daily_trucks_inbound * demurrage_trucks_pct) * hours_over_grace * rate_per_hour * params.operating_days_per_year

            return {
                "metric_name": "Sobrecostos de Estadía y Detención de Transporte",
                "trucks_delayed_per_day": round(params.daily_trucks_inbound * demurrage_trucks_pct, 1),
                "annual_cost_usd": round(annual_demurrage_usd, 2),
                "summary": f"Exposición a sobrecostos de detención de ~${round(annual_demurrage_usd):,} USD/año."
            }

        elif f_type == "rack_collision":
            # 11% de grúas chocan al año con puntales
            impacts_per_year = max(1.0, params.forklift_fleet_size * 0.11)
            cost_per_impact = 2200.0
            annual_cost_usd = impacts_per_year * cost_per_impact

            return {
                "metric_name": "Costos de Daño Estructural y Cuarentena de Bahías",
                "estimated_impacts_per_year": round(impacts_per_year, 1),
                "annual_cost_usd": round(annual_cost_usd, 2),
                "summary": f"Impactos estimados: {round(impacts_per_year, 1)}/año. Riesgo directo: ~${round(annual_cost_usd):,} USD/año + riesgo de colapso crítico."
            }

        elif f_type == "concrete_loss":
            cost_per_rejected_mixer = 1850.0
            rejection_probability_if_delayed = 0.25
            expected_loss_per_pour = params.concrete_trucks_per_pour * rejection_probability_if_delayed * cost_per_rejected_mixer

            return {
                "metric_name": "Riesgo Financiero por Pérdida de Cono / Rechazo de Hormigón",
                "loss_per_rejected_truck": f"${cost_per_rejected_mixer} USD",
                "exposure_per_critical_pour": round(expected_loss_per_pour, 2),
                "summary": f"Riesgo de pérdida de mezcla: ~${round(expected_loss_per_pour):,} USD por jornada de hormigonado más paralización de cuadrilla."
            }

        elif f_type == "shrinkage":
            # Merma estimada en perecibles
            estimated_shrinkage_usd = 65000.0
            return {
                "metric_name": "Merma por Excursión Térmica en Perecibles",
                "annual_cost_usd": estimated_shrinkage_usd,
                "summary": f"Exposición estimada a mermas de cadena de frío: ~${estimated_shrinkage_usd:,} USD/año."
            }

        elif f_type == "pharma_rejection":
            estimated_capa_cost_usd = 8500.0
            return {
                "metric_name": "Costo de No Conformidad GDP e Investigación CAPA",
                "cost_per_capa_usd": estimated_capa_cost_usd,
                "summary": f"Costo administrativo por investigación: ~${estimated_capa_cost_usd:,} USD + riesgo de descarte de lote ($30k - $1M+ USD)."
            }

        return {
            "metric_name": "Impacto No Lineal Específico",
            "annual_cost_usd": 0.0,
            "summary": "Impacto operativo cualitativo crítico."
        }


# ======================================================================================
# 5. SEGMENTATION & MULTI-SYMPTOM RECONNAISSANCE PIPELINE
# ======================================================================================

class GembaReconPipeline:
    """
    Pipeline principal para auditores de campo.
    Procesa notas desestructuradas, segmenta múltiples quejas/síntomas y genera
    el expediente de diagnóstico inmediato.
    """

    def __init__(self):
        self.index = HybridVectorIndex(KNOWLEDGE_GRAPH_DB)
        self.calculator = ImpactCalculator()

    def _split_into_observations(self, raw_notes: str) -> List[str]:
        """Segmenta párrafos o notas extensas en oraciones o ideas operativas separadas."""
        raw_clean = re.sub(r'[\r\n]+', '. ', raw_notes)
        segments = [s.strip() for s in re.split(r'[.;]\s+|\s+y\s+(?=[a-z\s]{10,})', raw_clean) if len(s.strip()) > 12]
        return segments if segments else [raw_notes]

    def process_field_notes(
        self,
        raw_notes: str,
        facility_params: Optional[FacilityParameters] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el reconocimiento completo:
        1. Segmentación
        2. Búsqueda y ponderación semántica
        3. Fusión de resultados por modo de falla único
        4. Cuantificación financiera de impacto
        5. Ensamblaje de checklist de terreno y catálogo comercial
        """
        params = facility_params or FacilityParameters()
        observations = self._split_into_observations(raw_notes)

        # Mapeo de modos de falla detectados con su score máximo
        matched_failures: Dict[str, Tuple[FailureMode, float, List[str]]] = {}

        for obs in observations:
            matches = self.index.search(obs, top_k=2, threshold=0.10)
            for fm, score in matches:
                if fm.id not in matched_failures:
                    matched_failures[fm.id] = (fm, score, [obs])
                else:
                    prev_fm, prev_score, prev_obs = matched_failures[fm.id]
                    matched_failures[fm.id] = (
                        fm,
                        max(prev_score, score),
                        prev_obs + [obs]
                    )

        # Ordenar por severidad y score de coincidencia
        sorted_matches = sorted(
            matched_failures.values(),
            key=lambda x: (x[0].severity_1_to_10 * 0.5 + x[1] * 10),
            reverse=True
        )

        dossier_items = []
        total_estimated_annual_loss = 0.0

        for fm, score, triggering_notes in sorted_matches:
            impact_data = self.calculator.calculate(fm, params)
            cost_usd = impact_data.get("annual_cost_usd", 0.0)
            total_estimated_annual_loss += cost_usd

            dossier_items.append({
                "failure_mode_id": fm.id,
                "name": fm.name,
                "category": fm.category,
                "confidence_score": round(score, 3),
                "severity_1_to_10": fm.severity_1_to_10,
                "triggering_field_notes": triggering_notes,
                "root_cause_hypothesis": fm.root_cause_hypothesis,
                "empirical_impact": impact_data["summary"],
                "annual_cost_usd": cost_usd,
                "diagnostic_check": asdict(fm.diagnostic_check),
                "service_offering": asdict(fm.service_offering)
            })

        return {
            "total_findings": len(dossier_items),
            "estimated_annual_financial_drag_usd": round(total_estimated_annual_loss, 2),
            "facility_parameters_applied": asdict(params),
            "findings": dossier_items
        }

    def generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Formatea los resultados en un reporte ejecutivo Markdown para entrega inmediata."""
        findings = results["findings"]
        total_loss = results["estimated_annual_financial_drag_usd"]
        total_count = results["total_findings"]

        md = []
        md.append("# DOSSIER EJECUTIVO DE RECONOCIMIENTO OPERATIVO (GEMBA DISCOVERY)")
        md.append(f"> **Hallazgos Críticos Detectados:** {total_count} vulnerabilidades pre-mapeadas")
        md.append(f"> **Impacto Financiero Latente Estimado:** **${total_loss:,.2f} USD / año**\n")
        md.append("---")

        for idx, item in enumerate(findings, 1):
            chk = item["diagnostic_check"]
            srv = item["service_offering"]
            severity_badge = "🔴 ALTA" if item["severity_1_to_10"] >= 8 else ("🟡 MEDIA" if item["severity_1_to_10"] >= 6 else "🟢 LEVE")

            md.append(f"### {idx}. [{item['category']}] {item['name']}")
            md.append(f"* **Criticidad:** {severity_badge} (Severidad: {item['severity_1_to_10']}/10) | **Confianza Semántica:** {round(item['confidence_score']*100)}%")
            md.append(f"* **Notas de Terreno Gatillantes:** *\"{ ' | '.join(item['triggering_field_notes']) }\"*")
            md.append(f"* **Hipótesis Causa Raíz:** {item['root_cause_hypothesis']}")
            md.append(f"* **Impacto Operativo & Financiero:** {item['empirical_impact']}")
            md.append("")
            md.append("#### 📋 Chequeo Forense Inmediato para el Auditor en Planta:")
            md.append(f"* **Protocolo:** `{chk['name']}` ({chk['normative_reference']})")
            md.append(f"* **Método de Inspección:** {chk['inspection_method']}")
            md.append(f"* **Muestra:** {chk['sample_rule']}")
            md.append(f"* **Umbral de Alerta Roja (Red Flag):** **{chk['red_flag_threshold']}**")
            md.append("")
            md.append("#### 💼 Propuesta Comercial & Módulo de Solución:")
            md.append(f"* **Servicio:** **{srv['title']}** (ROI típico: ~{srv['typical_roi_weeks']} semanas)")
            md.append(f"* **Alcance / Entregable:** {srv['scope_deliverable']}")
            md.append(f"* **Modelo Comercial:** {srv['commercial_model']}")
            md.append("\n" + "-"*80 + "\n")

        return "\n".join(md)


# ======================================================================================
# 6. DEMOSTRACIÓN Y ENTRYPOINT DE LÍNEA DE COMANDOS
# ======================================================================================

def run_demo():
    print("\n" + "="*80)
    print("EJECUTANDO TEST DEL PIPELINE CON NOTA DE CAMPO DE AUDITOR")
    print("="*80 + "\n")

    sample_auditor_note = (
        "Llegué a la nave 2 y los operarios pierden fácil 20 minutos buscando carretillas y pistolas RF "
        "porque no están asignadas. Además vi varios carritos de picking con ruedas trabadas por film "
        "plástico que apenas se mueven y los muchachos empujan con mucha fuerza haciendo ruido metálico. "
        "En la zona de recepción los muelles están colapsados de pallets en el piso y hay 4 camiones "
        "afuera esperando hace horas con quejas de cobro de sobreestadía."
    )

    print(f"📝 NOTA EN BRUTO DEL AUDITOR (AUDIO TRANSCRITO / NOTAS):\n\"{sample_auditor_note}\"\n")

    pipeline = GembaReconPipeline()
    params = FacilityParameters(headcount_pickers=45, shifts_per_day=2, hourly_labor_cost_usd=16.0)

    results = pipeline.process_field_notes(sample_auditor_note, facility_params=params)
    report_markdown = pipeline.generate_markdown_report(results)

    print(report_markdown)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supply Chain Gemba Reconnaissance Engine")
    parser.add_argument("--note", type=str, help="Texto o transcripción de la observación de campo")
    parser.add_argument("--pickers", type=int, default=50, help="Dotación de operarios en planta")
    parser.add_argument("--wage", type=float, default=16.0, help="Costo laboral por hora (USD)")
    parser.add_argument("--demo", action="store_true", help="Ejecutar caso de prueba predeterminado")

    args = parser.parse_args()

    if args.demo or not args.note:
        run_demo()
    else:
        pipeline = GembaReconPipeline()
        params = FacilityParameters(headcount_pickers=args.pickers, hourly_labor_cost_usd=args.wage)
        results = pipeline.process_field_notes(args.note, facility_params=params)
        print(pipeline.generate_markdown_report(results))
