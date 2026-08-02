"""Persistencia del canal DECIDIDA: markdown versionable, IDs monotonos, indice.

Por que git y no una base de datos: git da gratis historial por decision,
`git blame` para saber quien cambio el alcance y cuando, y un diff que es
exactamente el entregable que se distribuye despues de la reunion. Una base de
datos daria consultas mas rapidas sobre un volumen que aca no existe — cientos
de archivos, no millones.

El indice (`index.json`) es derivado y regenerable, como un `.tsbuildinfo`.
Ninguna lectura depende de el: `load_all()` escanea el directorio y siempre esta
en lo correcto. El indice existe para que un humano o una herramienta externa
vea el estado sin parsear 300 archivos.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import fields as dc_fields
from datetime import date
from pathlib import Path

from .frontmatter import dumps, loads
from .schema import (
    Anchor,
    Assumption,
    Commitment,
    Consent,
    Decision,
    Meeting,
    OpenQuestion,
    parse_date,
)

# Presupuesto duro de promociones por reunion. Treinta decisiones vuelven el
# registro ilegible: es la minuta hibrida otra vez, ahora en git y con mas
# ceremonia. Misma doctrina que `A3.validate` rechazando mas de 5 contramedidas
# y `JobBreakdown` mas de 12 pasos.
#
# Va a haber presion permanente para levantarlo. No levantarlo.
MAX_PROMOTIONS_PER_MEETING = 7

_KINDS = {
    "D": ("decisions", Decision),
    "C": ("commitments", Commitment),
    "A": ("assumptions", Assumption),
    "Q": ("questions", OpenQuestion),
}
_DATE_FIELDS = {
    Decision: ("date_decided",),
    Commitment: ("due",),
    Assumption: ("check_by",),
    OpenQuestion: ("resolve_by",),
    Meeting: ("date",),
}


class ValidationError(ValueError):
    """El registro se niega a persistir algo invalido. Es el punto entero: un
    registro con huecos es peor que ninguno, porque genera falsa confianza."""

    def __init__(self, kind: str, issues: list[str]):
        self.issues = issues
        super().__init__(f"{kind} invalido:\n  - " + "\n  - ".join(issues))


class PromotionBudgetExceeded(ValueError):
    pass


# ------------------------------------------------------------ serializacion


def _to_fm(obj) -> dict:
    """Entidad -> front-matter.

    `Anchor` y `Consent` se aplanan derivando sus campos del dataclass, no con
    una tupla escrita a mano. La tupla estaba completa, pero era una lista de
    nombres que hay que acordarse de actualizar: un campo nuevo en cualquiera de
    las dos se perdia al escribir y volvia a su default al leer, **sin error**.
    El registro seguia cargando y el campo simplemente no existia — la clase de
    bug que este repo colecciona.
    """
    data = {}
    dates = _DATE_FIELDS.get(type(obj), ())
    for f in dc_fields(obj):
        v = getattr(obj, f.name)
        if f.name in dates:
            v = v.isoformat()
        elif isinstance(v, (Anchor, Consent)):
            v = {sub.name: getattr(v, sub.name) for sub in dc_fields(v)}
        elif isinstance(v, tuple):
            v = list(v)
        data[f.name] = v
    return data


def _from_fm(cls, data: dict):
    kwargs = {}
    dates = _DATE_FIELDS.get(cls, ())
    known = {f.name for f in dc_fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValidationError(
            cls.__name__, [f"campos desconocidos en el archivo: {sorted(unknown)}"]
        )
    for f in dc_fields(cls):
        if f.name not in data:
            continue
        v = data[f.name]
        if f.name in dates:
            v = parse_date(v)
        elif f.name == "anchor" and isinstance(v, dict):
            v = Anchor(**v)
        elif f.name == "consent" and isinstance(v, dict):
            v = Consent(**v)
        elif f.name == "roster" and isinstance(v, list):
            v = tuple(v)
        kwargs[f.name] = v
    return cls(**kwargs)


def _body(obj) -> str:
    """Vista humana. Se regenera completa en cada guardado."""
    if isinstance(obj, Decision):
        return (
            f"# {obj.id} — {obj.statement}\n\n"
            f"**Dueno:** {obj.owner}  |  **Estado:** {obj.status}  |  "
            f"**Decidida:** {obj.date_decided.isoformat()}\n\n"
            f"## Criterio\n{obj.criteria}\n\n## Por que\n{obj.rationale}\n"
        )
    if isinstance(obj, Commitment):
        return (
            f"# {obj.id} — {obj.what}\n\n"
            f"**Dueno:** {obj.owner}  |  **Para:** {obj.due.isoformat()}  |  "
            f"**Estado:** {obj.status}  |  **Implementa:** {obj.decision_id}\n\n"
            f"**Evidencia de cumplimiento:** {obj.evidence_of_done}\n"
        )
    if isinstance(obj, Assumption):
        return (
            f"# {obj.id} — {obj.statement}\n\n"
            f"**Sostiene:** {obj.decision_id}  |  **Verificar antes de:** "
            f"{obj.check_by.isoformat()}  |  **Estado:** {obj.status}  |  "
            f"**Fuente:** {obj.source}\n"
        )
    if isinstance(obj, OpenQuestion):
        extra = f"  |  **Reapertura de:** {obj.reopen_of}" if obj.reopen_of else ""
        return (
            f"# {obj.id} — {obj.question}\n\n"
            f"**La resuelve:** {obj.resolver}  |  **Antes de:** "
            f"{obj.resolve_by.isoformat()}  |  **Estado:** {obj.status}{extra}\n"
        )
    if isinstance(obj, Meeting):
        return (
            f"# {obj.id}\n\n**Fecha:** {obj.date.isoformat()}  |  "
            f"**Facilitador:** {obj.facilitator}\n\n"
            f"**Roster:** {', '.join(obj.roster)}\n"
        )
    return ""


# ------------------------------------------------------------------- store


class DecideStore:
    """Registro en disco. Todas las lecturas escanean; nada depende del indice."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        for sub in ("decisions", "commitments", "assumptions", "questions", "meetings"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ lecturas

    def _dir(self, prefix: str) -> Path:
        return self.root / _KINDS[prefix][0]

    def _read_one(self, cls, path: Path):
        """Lee un archivo diciendo CUAL fallo si falla.

        `_from_fm` levanta por campo desconocido —a proposito: un .md escrito
        por una version mas nueva no se puede leer a medias— pero el mensaje no
        nombraba el archivo, y como no hay try por archivo, uno solo tumba
        `decisions()` entero y con el `agenda()`, `tick()`, `volume_gate()` y
        `rebuild_index()`. Con trescientos archivos en el registro, "campos
        desconocidos: ['clase']" no alcanza para encontrar cual.

        Sigue fallando: un registro que se lee a medias es peor que uno que no
        se lee, porque el que se lee a medias imprime un numero.
        """
        data, _ = loads(path.read_text(encoding="utf-8"))
        try:
            return _from_fm(cls, data)
        except ValidationError as exc:
            raise ValidationError(
                cls.__name__,
                [f"{path.name}: " + i for i in exc.issues]
                + [
                    "si el archivo lo escribio una version mas nueva del kit, actualizar; "
                    "el registro no se lee a medias a proposito"
                ],
            ) from exc
        except TypeError as exc:
            # `cls(**kwargs)` con un campo obligatorio ausente. Llega como
            # TypeError, que `cli._guarded` no atrapa: el usuario veria un
            # traceback de Python en vez de una linea que dice que hacer.
            raise ValidationError(
                cls.__name__, [f"{path.name}: falta un campo obligatorio ({exc})"]
            ) from exc

    def _load_kind(self, prefix: str) -> list:
        cls = _KINDS[prefix][1]
        return [
            self._read_one(cls, p)
            for p in sorted(self._dir(prefix).glob(f"{prefix}-*.md"))
        ]

    def decisions(self) -> list[Decision]:
        return self._load_kind("D")

    def commitments(self) -> list[Commitment]:
        return self._load_kind("C")

    def assumptions(self) -> list[Assumption]:
        return self._load_kind("A")

    def questions(self) -> list[OpenQuestion]:
        return self._load_kind("Q")

    def meetings(self) -> list[Meeting]:
        return [
            self._read_one(Meeting, p)
            for p in sorted((self.root / "meetings").glob("*.md"))
        ]

    def get(self, entity_id: str):
        prefix = entity_id.split("-")[0]
        if prefix not in _KINDS:
            raise KeyError(f"id desconocido: {entity_id}")
        path = self._dir(prefix) / f"{entity_id}.md"
        if not path.exists():
            raise KeyError(f"no existe: {entity_id}")
        return self._read_one(_KINDS[prefix][1], path)

    def get_meeting(self, meeting_id: str) -> Meeting:
        path = self.root / "meetings" / f"{meeting_id}.md"
        if not path.exists():
            raise KeyError(f"no existe la reunion: {meeting_id}")
        return self._read_one(Meeting, path)

    def roster_of(self, meeting_id: str) -> tuple[str, ...] | None:
        """Roster de la reunion, o `None` si la entidad no declara ninguna.

        Distingue tres casos que antes se confundian en uno:

          - sin `meeting_id`  -> None, y la validacion de roster no aplica. Es
            legitimo: `decide add` sin `--meeting` registra una decision de
            pasillo.
          - `meeting_id` que existe -> el roster, y se valida contra el.
          - `meeting_id` que NO existe -> **error**.

        El tercer caso devolvia `None` en silencio, con lo cual un `--meeting`
        mal tipeado desactivaba la validacion de dueno sin decir nada. El roster
        es el scope lexico del sistema: es la unica pieza de determinismo que el
        diseno fabrica, y un typo no puede apagarla calladamente.
        """
        if not meeting_id:
            return None
        return self.get_meeting(meeting_id).roster  # KeyError si no existe

    # ---------------------------------------------------------- escrituras

    def _next_id(self, prefix: str) -> str:
        nums = [
            int(p.stem.split("-")[1])
            for p in self._dir(prefix).glob(f"{prefix}-*.md")
            if p.stem.split("-")[1].isdigit()
        ]
        return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"

    def _write_new(self, prefix: str, obj) -> None:
        """Crea el archivo en modo exclusivo. `open(..., 'x')` es atomico en
        todas las plataformas, asi que dos procesos que pidan el mismo ID no se
        pisan: el segundo falla y reintenta con el siguiente numero. Un archivo
        de lock seria mas codigo y menos garantia."""
        for _ in range(50):
            path = self._dir(prefix) / f"{obj.id}.md"
            try:
                with open(path, "x", encoding="utf-8") as fh:
                    fh.write(dumps(_to_fm(obj), _body(obj)))
                return
            except FileExistsError:
                obj.id = self._next_id(prefix)
        raise RuntimeError(f"no se pudo asignar un id libre para {prefix}")

    def _path_of(self, obj) -> Path:
        if isinstance(obj, Meeting):
            return self.root / "meetings" / f"{obj.id}.md"
        return self._dir(obj.id.split("-")[0]) / f"{obj.id}.md"

    def _issues(self, obj) -> list[str]:
        """Los issues de una entidad. Despacho por TIPO, no por string.

        Reemplaza a `_check_roster`, que decidia con
        `obj.validate(roster) if kind != "Assumption" else obj.validate()`: un
        typo en ese string mandaba un roster a `Assumption.validate()` y salia
        un TypeError en vez de una validacion.

        Si el roster no se puede leer —la reunion no existe, o su .md lo
        escribio una version mas nueva— eso es un ISSUE, no una excepcion.
        Propagarla mataba `tick()` entero: un solo archivo de reunion ilegible
        y no se puede vencer ni un compromiso.
        """
        if isinstance(obj, (Assumption, Meeting)):
            return list(obj.validate())
        try:
            roster = self.roster_of(obj.meeting_id)
        except (KeyError, ValidationError) as exc:
            return list(obj.validate(None)) + [
                f"no se pudo leer el roster de '{obj.meeting_id}': "
                f"{exc.__class__.__name__}. El dueno quedo sin validar contra nadie."
            ]
        return list(obj.validate(roster))

    def save(self, obj, force: bool = False) -> list[str]:
        """Sobreescribe una entidad existente. No asigna IDs. **Valida.**

        Era un `write_text` desnudo, y es lo que usan `supersede`, `safe_close`
        y `tick`: toda regla escrita en un `validate()` era codigo muerto en los
        caminos que mas la necesitan.

        Valida contra el DISCO, no contra el vacio. La regla es **una escritura
        no puede empeorar el registro**: se comparan los issues del objeto que
        entra contra los que el archivo ya tenia, y solo se rechaza la
        diferencia. Los heredados se toleran y se DEVUELVEN para que el llamador
        los muestre.

        Sin esa semantica, escribir sobre una entidad ya invalida seria
        imposible — y las entidades invalidas son justamente sobre las que hay
        que poder anotar que algo fallo. Validar contra el vacio convierte cada
        arreglo en un bloqueo.
        """
        path = self._path_of(obj)
        nuevos = self._issues(obj)
        if nuevos and not force:
            heredados: set[str] = set()
            if path.exists():
                try:
                    heredados = set(self._issues(self._read_one(type(obj), path)))
                except (ValidationError, TypeError, ValueError):
                    # Ilegible: no hay contra que comparar. Todo issue cuenta
                    # como nuevo, que es el lado seguro.
                    heredados = set()
            peores = [i for i in nuevos if i not in heredados]
            if peores:
                raise ValidationError(type(obj).__name__, peores)
        path.write_text(dumps(_to_fm(obj), _body(obj)), encoding="utf-8")
        return nuevos

    def add_meeting(self, meeting: Meeting, force: bool = False, overwrite: bool = False) -> Meeting:
        """Registra una reunion. Se niega a pisar una existente.

        `save()` es `write_text` sin modo exclusivo, asi que registrar dos veces
        el mismo `id` reemplazaba la reunion entera —incluido el **roster**— sin
        una linea de aviso. El roster es el scope lexico del sistema: es la
        unica pieza de determinismo que el diseno fabrica, y pisarlo invalida
        retroactivamente la validacion de dueno de cada decision ya colgada de
        esa reunion. Nada falla; el registro simplemente pasa a estar validado
        contra una lista de gente que ya no es la que estuvo.

        `overwrite=True` existe para corregir un roster mal tipeado, que es un
        caso real. Es explicito a proposito: la correccion es una decision, no
        un efecto de lado de volver a correr un comando.
        """
        issues = meeting.validate()
        if issues and not force:
            raise ValidationError("Meeting", issues)
        path = self.root / "meetings" / f"{meeting.id}.md"
        if path.exists() and not overwrite:
            raise ValidationError(
                "Meeting",
                [
                    f"la reunion '{meeting.id}' ya esta registrada. Volver a registrarla "
                    "reemplazaria su roster, y con el se cae la validacion de dueno de "
                    "todo lo que ya cuelga de ella. Usar overwrite=True (CLI: --overwrite) "
                    "si de verdad se quiere corregir."
                ],
            )
        self.save(meeting)
        return meeting

    def _check_roster(self, obj, meeting_id: str, force: bool, kind: str):
        """Alta: aca no hay nada heredado que tolerar, asi que cualquier issue
        bloquea. Es lo contrario de `save()`, y a proposito: una entidad NUEVA
        entra sana o no entra.

        Ojo: un `--meeting` que no existe sigue siendo un error de alta. Ahora
        llega como issue (via `_issues`) en vez de como `KeyError` suelto, pero
        bloquea igual. Lo que NO puede hacer es matar una lectura o un `tick`.
        """
        issues = self._issues(obj)
        if issues and not force:
            raise ValidationError(kind, issues)
        return issues

    def add_decision(self, decision: Decision, force: bool = False) -> Decision:
        if not decision.id:
            decision.id = self._next_id("D")
        self._check_roster(decision, decision.meeting_id, force, "Decision")

        if decision.meeting_id:
            used = sum(1 for d in self.decisions() if d.meeting_id == decision.meeting_id)
            if used >= MAX_PROMOTIONS_PER_MEETING and not force:
                raise PromotionBudgetExceeded(
                    f"la reunion {decision.meeting_id} ya tiene "
                    f"{MAX_PROMOTIONS_PER_MEETING} decisiones. Treinta decisiones vuelven "
                    "el registro ilegible: es la minuta hibrida otra vez. Si de verdad "
                    "hacen falta mas, la reunion tenia que ser dos."
                )
        self._write_new("D", decision)
        return decision

    def add_commitment(self, c: Commitment, force: bool = False) -> Commitment:
        if not c.id:
            c.id = self._next_id("C")
        if c.decision_id:
            self.get(c.decision_id)  # levanta KeyError si la decision no existe
        self._check_roster(c, c.meeting_id, force, "Commitment")
        self._write_new("C", c)
        return c

    def add_assumption(self, a: Assumption, force: bool = False) -> Assumption:
        if not a.id:
            a.id = self._next_id("A")
        if a.decision_id:
            self.get(a.decision_id)
        issues = a.validate()
        if issues and not force:
            raise ValidationError("Assumption", issues)
        self._write_new("A", a)
        return a

    def add_question(self, q: OpenQuestion, force: bool = False) -> OpenQuestion:
        if not q.id:
            q.id = self._next_id("Q")
        if q.reopen_of:
            self.get(q.reopen_of)
        self._check_roster(q, q.meeting_id, force, "OpenQuestion")
        self._write_new("Q", q)
        return q

    # ------------------------------------------------------------- indice

    def rebuild_index(self) -> dict:
        """Vista agregada para humanos y herramientas externas. Derivada: se
        puede borrar y regenerar sin perder nada."""
        idx = {
            "decisions": [
                {"id": d.id, "statement": d.statement, "owner": d.owner, "status": d.status}
                for d in self.decisions()
            ],
            "commitments": [
                {"id": c.id, "decision_id": c.decision_id, "owner": c.owner,
                 "due": c.due.isoformat(), "status": c.status}
                for c in self.commitments()
            ],
            "assumptions": [
                {"id": a.id, "decision_id": a.decision_id, "check_by": a.check_by.isoformat(),
                 "status": a.status}
                for a in self.assumptions()
            ],
            "questions": [
                {"id": q.id, "resolver": q.resolver, "resolve_by": q.resolve_by.isoformat(),
                 "status": q.status, "reopen_of": q.reopen_of}
                for q in self.questions()
            ],
        }
        (self.root / "index.json").write_text(
            json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return idx

    # ---------------------------------------------------------------- git

    def git_commit(self, message: str) -> str:
        """Commitea el registro si estamos en un repo. Nunca levanta: si no hay
        git, el registro sigue siendo archivos en disco y todo lo demas funciona."""
        try:
            r = subprocess.run(
                ["git", "-C", str(self.root), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                return "sin repo git: registro guardado en disco, sin versionar"
            subprocess.run(["git", "-C", str(self.root), "add", "."], capture_output=True, timeout=20)
            c = subprocess.run(
                ["git", "-C", str(self.root), "commit", "-m", message],
                capture_output=True, text=True, timeout=20,
            )
            return "sin cambios que commitear" if c.returncode != 0 else f"commit: {message}"
        except (OSError, subprocess.SubprocessError) as exc:
            return f"git no disponible ({exc.__class__.__name__}): registro guardado igual"
