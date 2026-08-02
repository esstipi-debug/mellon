"""Hoja de desglose TWI Job Instruction y runbook de traspaso.

Lo que dejas instalado en la cabeza del cliente, no en su servidor. Formato TWI:
paso importante / punto clave / razon. Es el antidoto contra la degradacion por
rotacion de personal, que es la causa numero uno de que un sistema "deje de
funcionar" sin que nadie haya tocado el codigo.

Las cuatro etapas de TWI JI, que es como se entrega (no se manda por correo):

    1. preparar al operador
    2. presentar la operacion
    3. hacer que la pruebe
    4. seguimiento — quien le responde dudas y hasta cuando
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JobStep:
    """Un paso importante.

    step        que se hace (avanza la tarea)
    key_points  como se hace: lo que hace o rompe la tarea, lo seguro, lo facil
    reasons     por que ese punto clave importa — sin esto no se retiene
    """

    step: str
    key_points: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    target_time_s: float | None = None


@dataclass
class JobBreakdown:
    task: str
    role: str
    site: str = ""
    author: str = ""
    steps: list[JobStep] = field(default_factory=list)
    tools_required: list[str] = field(default_factory=list)
    safety_notes: list[str] = field(default_factory=list)
    escalation: str = ""

    def add(self, step: str, key_points: list[str], reasons: list[str], target_time_s: float | None = None):
        self.steps.append(JobStep(step, key_points, reasons, target_time_s))
        return self

    @property
    def total_target_time_s(self) -> float:
        return sum(s.target_time_s or 0 for s in self.steps)

    def validate(self) -> list[str]:
        """TWI tiene reglas duras. Romperlas produce un documento que nadie usa."""
        issues = []
        if len(self.steps) > 12:
            issues.append(
                f"{len(self.steps)} pasos: sobre 12 la hoja no se retiene, partir la tarea en dos"
            )
        for i, s in enumerate(self.steps, 1):
            if not s.key_points:
                issues.append(f"paso {i} sin puntos clave: es una lista de tareas, no una hoja TWI")
            if len(s.key_points) != len(s.reasons):
                issues.append(f"paso {i}: cada punto clave necesita su razon ({len(s.key_points)} vs {len(s.reasons)})")
        if not self.escalation:
            issues.append("sin ruta de escalamiento: el operador no sabe a quien llamar a las 23:00")
        return issues

    def to_markdown(self) -> str:
        lines = [
            f"# Hoja de desglose — {self.task}",
            "",
            f"**Rol:** {self.role}  |  **Sitio:** {self.site}  |  **Autor:** {self.author}",
            f"**Tiempo objetivo:** {self.total_target_time_s:.0f}s",
            "",
        ]
        if self.tools_required:
            lines += ["**Herramientas / accesos:** " + ", ".join(self.tools_required), ""]
        if self.safety_notes:
            lines += ["**Seguridad:**"] + [f"- {n}" for n in self.safety_notes] + [""]

        lines += ["| # | Paso importante | Punto clave | Razon | Obj. |", "|---|---|---|---|---|"]
        for i, s in enumerate(self.steps, 1):
            kp = "<br>".join(f"- {k}" for k in s.key_points) or "-"
            rs = "<br>".join(f"- {r}" for r in s.reasons) or "-"
            t = f"{s.target_time_s:.0f}s" if s.target_time_s else "-"
            lines.append(f"| {i} | {s.step} | {kp} | {rs} | {t} |")

        lines += [
            "",
            f"**Escalamiento:** {self.escalation}",
            "",
            "## Entrega (TWI Job Instruction)",
            "1. Preparar al operador — contexto y por que importa.",
            "2. Presentar la operacion — hacerla, explicando puntos clave y razones.",
            "3. Que la pruebe — el operador la hace y explica en voz alta lo que hace.",
            "4. Seguimiento — quien responde dudas, y cuando se revisa que siga estable.",
            "",
            "Firma operador: ____________  Firma supervisor: ____________  Fecha: ________",
        ]
        return "\n".join(lines)


def runbook_template(system: str, client: str = "") -> str:
    """Runbook de traspaso. Lo que el cliente necesita para operar sin vos.

    Si no podes irte dos semanas sin que se caiga, el despliegue no termino.
    """
    return f"""# Runbook — {system}{f' @ {client}' if client else ''}

## 1. Que hace este sistema
Una frase. Si necesita un parrafo, el alcance quedo mal definido.

## 2. Metrica que hay que mirar
| metrica | fuente | frecuencia | limite inferior | limite superior | dueno |
|---|---|---|---|---|---|
|  |  | diaria |  |  |  |

Los limites salen del grafico XmR de la linea base (herramienta 9), no de una
conversacion. Congelados: si se recalculan cada semana, la degradacion pasa
inadvertida.

## 3. Arranque diario
1.
2.

## 4. Que hacer cuando (los cinco escenarios reales)
| sintoma | causa probable | accion inmediata | a quien escalar |
|---|---|---|---|
| el sistema no responde |  | |  |
| los numeros se ven raros |  | |  |
| entro un pedido que no procesa |  | |  |
| el socio EDI cambio algo |  | |  |
| el operador dice que "ya no sirve" |  | |  |

## 5. Lo que NO hay que hacer
- No reprocesar sin verificar idempotencia (duplica despachos).
- No cambiar parametros sin registrar quien y por que.
- No recalcular los limites de control para "que deje de alarmar".

## 6. Contactos
| rol | nombre | canal | horario |
|---|---|---|---|

## 7. Revision
Proxima revision de este runbook: ____________
Dueno del documento del lado del cliente: ____________
"""
