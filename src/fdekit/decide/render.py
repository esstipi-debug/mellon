"""H10 — la superficie de lectura para el cliente. Un archivo, no una aplicacion.

El jefe de operaciones del CD es el consumidor mas importante del canal
DECIDIDA y **no tiene acceso al repo, no sabe que es un diff, y su herramienta
es Teams o SharePoint**. Un registro que solo el FDE puede leer es una libreta
personal con mas ceremonia.

Por eso esto es una pagina HTML sola, sin red, sin autenticacion y sin
herramienta nueva: se adjunta a un correo, se sube al SharePoint del proyecto o
se imprime. Cualquier cosa que pida un servidor, un login o una conexion
saliente muere contra el proxy del cliente, que es exactamente donde tiene que
funcionar.

**Stdlib pura**, igual que `fdekit.guard` y por la misma razon estructural
(regla 2): esto corre en el notebook prestado de un CD.

Dos reglas heredadas que aca son mas duras, porque este archivo SALE del equipo
y sobrevive al proyecto:

  - **agrupado por decision, nunca por persona** (H15). Una pagina que rankea
    vencidos por dueno es un tablero de desempeno individual, y el dia que el
    registro se lee asi la gente deja de declarar compromisos y el sistema muere
    en dos semanas sin ninguna senal tecnica. La norma va escrita EN la pagina:
    una norma que vive en otro documento no la lee nadie.
  - **solo se nombra al dueno** (H14). El tercero mencionado en un rationale es
    un dato personal de alguien que no consintio, y esta pagina termina fuera de
    nuestro control.
"""

from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from .schema import DEAD_DECISION_STATUS, LIVE_COMMITMENT_STATUS
from .store import DecideStore

# El color NUNCA es la unica senal (H16, y WCAG 1.4.1). La mitad de las veces
# esta pagina se imprime en blanco y negro, y alrededor del 8% de los hombres no
# distingue rojo de verde: para los dos casos, un borde de color es exactamente
# cero informacion. Cada estado que importa lleva ademas su etiqueta en texto.
_CSS = """
:root { color-scheme: light dark }
body { font: 16px/1.6 system-ui, sans-serif; max-width: 46rem; margin: 2rem auto;
       padding: 0 1rem; color: #1a1a1a; background: #fff }
@media (prefers-color-scheme: dark) {
  body { color: #e8e8e8; background: #16181c }
  .nota { background: #22262c; border-left-color: #777; color: #cfcfcf }
  .id, .meta { color: #a8b0ba }
  .marca { background: #4a2530; color: #ffc9d4 }
  h2, footer { border-color: #39404a }
  li.vencido { color: #ff9b9b }
}
h1 { font-size: 1.5rem; margin-bottom: .2rem }
h2 { font-size: 1.1rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd;
     padding-bottom: .3rem }
.nota { background: #f6f6f4; border-left: 3px solid #999; padding: .8rem 1rem;
        font-size: .9rem; color: #444 }
.decision { margin: 1.6rem 0; padding-left: .9rem; border-left: 3px solid #2a6 }
.decision.riesgo { border-left-color: #c62 }
.id { font-family: ui-monospace, monospace; font-size: .85rem; color: #666 }
.meta { font-size: .88rem; color: #555; margin: .2rem 0 }
.marca { font-size: .75rem; background: #fde; color: #833; padding: .1rem .4rem;
         border-radius: 3px; text-transform: uppercase; letter-spacing: .03em }
ul.cuelga { margin: .5rem 0 0; padding-left: 1.2rem; font-size: .92rem }
li.vencido { color: #a33 }
footer { margin-top: 3rem; font-size: .8rem; color: #777; border-top: 1px solid #ddd;
         padding-top: .8rem }
"""

# La norma de H15, escrita donde se lee y no en un anexo. Es la unica
# contramedida posible contra el uso punitivo: no hay control tecnico que impida
# que alguien lea una tabla como un ranking, solo que diga que no lo es y que la
# forma de la tabla no lo invite.
_NORMA = (
    "Este registro no se usa para evaluacion individual de desempeno. Los "
    "compromisos vencidos se leen agrupados por decision, no por persona: un "
    "compromiso vencido casi siempre dice algo de la decision que lo genero — "
    "que estaba mal dimensionada, que dependia de algo que no llego — y muy "
    "poco de quien lo tomo."
)


def _en_scope(obj, scope: str) -> bool:
    s = getattr(obj, "scope", "") or ""
    if not scope:
        return True
    return s == scope or s.startswith(scope + "/")


def _redactor(store: DecideStore, dueno: str):
    """Tapa a todo el que no sea el dueno de la fila.

    Contra el directorio completo de la cuenta y no contra el roster de la
    sesion: el tercero mencionado suele ser justo el que no estuvo.
    """
    nombres = sorted(
        {p for m in store.meetings() for p in m.roster} - {dueno},
        key=len, reverse=True,
    )

    def redactar(texto: str) -> str:
        for n in nombres:
            texto = texto.replace(n, "[NOMBRE]")
        return texto

    return redactar


def _enunciado(d, idioma: str) -> tuple[str, bool]:
    """El enunciado y si hubo que caer al original.

    Sin traduccion se muestra el espanol y **se dice**. Callarlo dejaria una
    pagina en ingles con filas en espanol y ninguna explicacion; inventar la
    traduccion seria peor, porque una traduccion automatica de un enunciado de
    decision cambia justo el matiz que hace que el enunciado sirva.
    """
    if idioma == "en" and d.enunciado_en:
        return d.enunciado_en, False
    return d.statement, idioma == "en"


def render_html(
    store: DecideStore,
    scope: str,
    today: date,
    idioma: str = "es",
) -> str:
    """La pagina. `today` es argumento (regla 4): una pagina sin fecha miente
    sola apenas alguien la reenvia una semana despues."""
    todas = store.decisions()
    vivas = [
        d for d in todas
        if d.status not in DEAD_DECISION_STATUS and _en_scope(d, scope)
    ]
    vivas.sort(key=lambda d: (d.date_decided, d.id))
    ids = {d.id for d in vivas}

    por_decision: dict[str, list] = {}
    for c in store.commitments():
        if c.decision_id in ids and c.status in LIVE_COMMITMENT_STATUS:
            por_decision.setdefault(c.decision_id, []).append(c)
    supuestos: dict[str, list] = {}
    for a in store.assumptions():
        if a.decision_id in ids and a.status != "VERIFICADO":
            supuestos.setdefault(a.decision_id, []).append(a)

    sin_traducir = 0
    L = [
        "<!doctype html>",
        '<html lang="' + escape(idioma) + '"><head><meta charset="utf-8">',
        f"<title>Registro de decisiones — {escape(scope or 'todo')}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>Que esta decidido — {escape(scope or 'todo el proyecto')}</h1>",
        f'<p class="meta">Generado el {today.isoformat()}. '
        f"{len(vivas)} decision(es) vigentes.</p>",
        f'<p class="nota">{escape(_NORMA)}</p>',
        "<h2>Decisiones vigentes</h2>",
    ]
    if not vivas:
        L.append("<p>No hay ninguna decision vigente en este scope todavia.</p>")

    for d in vivas:
        redactar = _redactor(store, d.owner)
        texto, cayo = _enunciado(d, idioma)
        sin_traducir += 1 if cayo else 0
        en_riesgo = d.status == "EN_RIESGO" or any(
            a.pone_en_riesgo for a in supuestos.get(d.id, [])
        )
        marca = (
            f' <span class="marca">{escape(d.origen)} — declarada, no auditada</span>'
            if not d.auditable else ""
        )
        aviso = ' <span class="marca">sin traducir</span>' if cayo else ""

        # La etiqueta en TEXTO, no solo el borde de color.
        riesgo = (
            ' <span class="marca">EN RIESGO — un supuesto se cayo</span>'
            if en_riesgo else ""
        )
        L += [
            f'<div class="decision{" riesgo" if en_riesgo else ""}">',
            f'<span class="id">{escape(d.id)}</span>{marca}{aviso}{riesgo}',
            f"<p><strong>{escape(redactar(texto))}</strong></p>",
            f'<p class="meta">Responsable: {escape(d.owner)} · desde '
            f"{d.date_decided.isoformat()} · estado {escape(d.status)}</p>",
            f'<p class="meta">Listo cuando: {escape(redactar(d.criteria))}</p>',
            f'<p class="meta">Por que: {escape(redactar(d.rationale))}</p>',
        ]
        for a in supuestos.get(d.id, []):
            L.append(
                f'<p class="meta">Supuesto [{escape(a.status)}] '
                f"{escape(redactar(a.statement))} — se revisa el "
                f"{a.check_by.isoformat()}, fuente: {escape(redactar(a.source))}</p>"
            )
        cuelgan = por_decision.get(d.id, [])
        if cuelgan:
            L.append('<ul class="cuelga">')
            for c in sorted(cuelgan, key=lambda x: x.due):
                clase = ' class="vencido"' if c.status == "VENCIDO" else ""
                # "VENCIDO" escrito, no solo el rojo: ver el comentario de _CSS.
                estado = " [VENCIDO]" if c.status == "VENCIDO" else ""
                corridas = (
                    f" — la fecha se corrio {c.slips_hacia_adelante} vez/veces"
                    if c.slips_hacia_adelante else ""
                )
                L.append(
                    f"<li{clase}><span class='id'>{escape(c.id)}</span>{estado} "
                    f"{escape(_redactor(store, c.owner)(c.what))} — {escape(c.owner)}, "
                    f"para el {c.due.isoformat()}{corridas}</li>"
                )
            L.append("</ul>")
        L.append("</div>")

    fuera = sum(1 for d in todas if not _en_scope(d, scope))
    L += [
        "<footer>",
        f"<p>Esto <strong>no es</strong> todo lo que se hablo ni todo lo que se "
        f"decidio: son las {len(vivas)} decisiones vigentes de este scope, de "
        f"{len(todas)} en el registro ({fuera} fuera de scope). Lo revertido y lo "
        f"superado se conserva, pero no se muestra aca.</p>",
        "<p>Las filas marcadas <em>declarada, no auditada</em> no salieron de una "
        "reunion registrada: se declararon de memoria o se rescataron de un acta "
        "anterior al sistema.</p>",
    ]
    if sin_traducir:
        L.append(
            f"<p>{sin_traducir} enunciado(s) se muestran en espanol porque no tienen "
            "traduccion cargada. No se traducen automaticamente: una traduccion "
            "automatica de un enunciado de decision cambia justo el matiz que lo "
            "hace util.</p>"
        )
    L += ["</footer></body></html>"]
    return "\n".join(L)


def write_html(
    store: DecideStore,
    scope: str,
    path: str | Path,
    today: date,
    idioma: str = "es",
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_html(store, scope, today, idioma), encoding="utf-8")
    return p


__all__ = ["render_html", "write_html"]
