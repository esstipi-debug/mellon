# Directrices de Desarrollo: La Filosofía Mellon & Ithildin 🗝️🌌

> **Doctrina de Arquitectura, Criterios de Aceptación y Protocolos Operativos para Agentes de IA y Productos de Despliegue en Terreno.**  
> *Versión 1.0 · Octubre 2026 · Mellon Playbook*

---

## 1. La Filosofía Dual: Mellon + Ithildin

El desarrollo de software e inteligencia artificial en este ecosistema no responde a la lógica del *SaaS de escritorio* ni al desarrollo de demos de laboratorio. Opera bajo la restricción implacable del **Gemba** (el lugar físico donde ocurren las operaciones: bodegas, centros de distribución, patios logísticos y líneas de producción).

Para que un producto o agente sobreviva en este entorno, debe gobernar dos fuerzas complementarias:

$$\textbf{Adopción Sostenible} = \underbrace{\text{Mellon (Alianza Humana)}}_{\text{El 95\% del fracaso se evita aquí}} \times \underbrace{\text{Ithildin (Rigor Determinista)}}_{\text{El riesgo de TI se anula aquí}}$$

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 MELLON 🗝️                                    │
│                    Protocolo de Alianza y Adopción Humana                    │
│   • Diálogo en lenguaje Gemba (términos de piso, no de LLMs)               │
│   • Human-in-the-Loop: el agente asiste, el operario valida                 │
│   • Canales nativos sin fricción (WhatsApp, Terminales RF, CLI)             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                ITHILDIN 🌌                                   │
│                  Capa de Infraestructura Pasiva y Guardarraíles              │
│   • Arquitectura de Doble Riel: IA redacta -> Motor determinista valida     │
│   • Safe-Staging criptográfico: HMAC-SHA256 e Idempotencia obligatoria       │
│   • Telemetría silenciosa: Sondas de solo-lectura sobre 5 columnas           │
│   • Triggers condicionales dormidos: reactivos a estímulos, cero polling    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Directrices Mellon (Diseño de Agentes para la Operación)

### Directriz M1: El Agente es un Aliado, Nunca un Inspector Encubierto
* **Regla:** Ningún agente se diseña para vigilar, puntuar punitivemente o reemplazar al operario. Se diseña para absorber la fatiga cognitiva, evitar retrabajos y eliminar tareas burocráticas ingratas.
* **Mecanismo:** Si el agente detecta una desviación en el piso, no emite un reporte acusatorio a gerencia; le presenta primero al operario una sugerencia de corrección con contexto claro en su propio flujo de trabajo.

### Directriz M2: Hablar el Dialecto del Gemba
* **Regla:** Queda terminantemente prohibido exponer conceptos como *embeddings, tokens, prompts, temperature* o *hallucination* al usuario final.
* **Mecanismo:** El agente traduce sus estados internos a terminología operativa estándar:
  * ❌ *"El modelo tiene 85% de confianza en el prompt."*
  * ✔️ *"Detecté 3 pallets en muelle sin tarja de recepción asignada en SAP."*

### Directriz M3: Interfaces Nativas y Cero Fricción
* **Regla:** No se obliga al personal de operaciones a abrir una pestaña web adicional o loguearse en un nuevo dashboard.
* **Mecanismo:** El agente vive donde la operación ya trabaja:
  * Mensajería asíncrona rápida (WhatsApp corporativo, Telegram, Slack).
  * Salidas en texto plano compatibles con pantallas de terminales de radiofrecuencia (RF) o emuladores VT220.
  * APIs webhook y comandos CLI de una sola línea (`fdekit`).

---

## 3. Directrices Ithildin (Arquitectura Técnica y Guardarraíles)

### Directriz I1: Arquitectura del Doble Riel (Safe-Staging Writeback)
* **Regla:** La IA generativa es probabilística; la base de datos transaccional (ERP/WMS) es determinista. **Ningún LLM o agente tiene credenciales de escritura directa sobre tablas productivas.**
* **Mecanismo:**
  1. El agente procesa la información y emite una propuesta de acción (`StagingAction`).
  2. La acción se clasifica por su nivel de riesgo:
     * `READ`: Solo consulta de datos.
     * `REVERSIBLE`: Creación de borradores, reservas temporales o logs secundarios.
     * `IRREVERSIBLE`: Cancelaciones, transferencias contables, ajustes de stock físico.
  3. Toda acción clasificada como `IRREVERSIBLE` debe incluir un `rollback_plan` JSON ejecutable. Sin este plan, el motor rechaza el writeback inmediatamente.

### Directriz I2: La Firma Criptográfica y la Idempotencia
* **Regla:** Ninguna mutación se ejecuta sin un token firmado por HMAC-SHA256 y una clave de idempotencia única.
* **Mecanismo:**
  * Implementado en `fdekit.ithildin.IthildinGuard`.
  * Si un webhook o agente reintenta enviar la misma propuesta por inestabilidad de red, el ledger inmutable detecta el duplicado y previene la doble ejecución de la transacción en el ERP.

### Directriz I3: Inspección Pasiva sin Overhead (Protocolo de 5 Columnas)
* **Regla:** Para diagnosticar procesos o alimentar agentes, no se satura la base de datos transaccional con consultas analíticas complejas (GROUP BY sobre millones de registros).
* **Mecanismo:**
  * Uso de `fdekit.ithildin.PassiveEventProbe`.
  * La ingestión se acota al contrato canónico de 5 columnas:
    $$\{\texttt{case\_id, activity, timestamp, resource, location}\}$$
  * Se auditan anomalías críticas: timestamps huérfanos de huso horario (*tz-naive*), fechas invertidas o nulos en identificadores de caso.

### Directriz I4: Detonadores Reactivos Pasivos (Event-Driven vs. Polling)
* **Regla:** Los agentes deben permanecer en consumo computacional cero (dormidos en la sombra) hasta que un estímulo calificado cruce el umbral de activación.
* **Mecanismo:**
  * Uso de `fdekit.ithildin.ConditionalTrigger`.
  * Los triggers definen predicados booleanos puros con tiempos de enfriamiento (*cooldown*) obligatorios para evitar tormentas de eventos (*event storms*) y loops infinitos de ejecución.

---

## 4. Rúbrica de Aprobación para Nuevos Agentes o Módulos

Antes de desplegar cualquier nuevo agente o herramienta en este repositorio o en un cliente, debe superar este checklist de cinco compuertas:

| Compuerta | Pregunta Crítica | Condición Bloqueante |
|---|---|---|
| **1. Guardarraíl Criptográfico** | ¿El agente escribe en staging firmado con HMAC y cuenta con clave de idempotencia? | **SÍ O NO.** Si escribe directo a producción sin HMAC, no se aprueba. |
| **2. Plan de Rollback** | ¿Toda mutación irreversible cuenta con un plan de reversión determinista? | Si `risk_level == IRREVERSIBLE` y no hay rollback, el guardarraíl lo rechaza. |
| **3. Dialecto de Terreno** | ¿La interfaz utiliza exclusivamente términos del negocio y del Gemba? | Si expone parámetros internos de modelos o métricas vacías, se rechaza. |
| **4. Contrato de Datos Mínimo** | ¿La telemetría respeta el estándar de 5 columnas y timestamps con zona horaria? | Si introduce esquemas pesados no estándar o timestamps ambiguos, se rechaza. |
| **5. Medición Contrafactual** | ¿El impacto del agente se medirá con Diferencias en Diferencias (Diff-in-Diff)? | Debe existir un grupo de control o una línea base pre/post contrafactual. |

---

## 5. Implementación de Referencia en Código

Todo nuevo desarrollo en Python debe apoyarse en el módulo nativo [`fdekit.ithildin`](fde-field-kit/src/fdekit/ithildin/):

```python
from fdekit.ithildin import (
    ConditionalTrigger,
    IthildinGuard,
    PassiveEventProbe,
    RiskLevel,
    StagingAction,
)

# 1. Definir guardarrail determinista
guard = IthildinGuard(secret_key=b"secreto-de-alta-entropia-16bytes-min")

# 2. Generar accion desde el agente
action = StagingAction(
    action_id="act-picking-reassign-001",
    risk_level=RiskLevel.REVERSIBLE,
    target_system="WMS_MANHATTAN",
    payload={"task_id": "T-892", "new_picker": "OP-14"},
    idempotency_key="idemp-wms-20261020-001",
    timestamp_utc="2026-10-20T12:35:00+00:00",
    rollback_plan={"task_id": "T-892", "restore_picker": "OP-03"},
)

# 3. Firmar y someter a evaluacion determinista
token = guard.sign_action(action)
veredicto = guard.evaluate_and_commit(action, token)

if veredicto.approved:
    # Safe to execute writeback
    print(f"Writeback autorizado con hash de auditoria: {veredicto.audit_hash}")
else:
    print(f"Accion bloqueada por Ithildin: {veredicto.reason} ({veredicto.code})")
```
