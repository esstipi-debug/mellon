"""Front-matter minimo: `clave: <valor JSON>`, una clave por linea.

Por que no PyYAML: el nucleo del kit declara numpy, pandas, matplotlib, scipy y
simpy, y nada mas. La restriccion es explicita — el kit tiene que correr en el
notebook prestado de un CD, sin GPU y sin permisos de instalacion. Agregar una
dependencia para leer siete campos por archivo no lo vale.

Por que tampoco un parser a mano: parsear YAML a mano es un error clasico.
Aca no se parsea YAML — se parsea `clave: <valor JSON>`, y el valor lo lee
`json.loads`, que es un parser de verdad. Eso da strings, numeros, booleanos,
null, listas y diccionarios sin escribir un solo caracter de parsing, y evita
de paso las trampas de YAML (el pais `NO` que se vuelve `False`, las fechas que
se auto-convierten, las comillas opcionales).

JSON es un subconjunto de YAML, asi que el bloque sigue renderizando bien en
GitHub y en Obsidian.

Contrato: el front-matter es el dato. El cuerpo del archivo es una vista
generada y se reescribe completa en cada guardado.
"""

from __future__ import annotations

import json

DELIM = "---"
_BODY_WARNING = "<!-- cuerpo generado desde el front-matter; editar arriba, no aqui -->"


class FrontMatterError(ValueError):
    """El archivo no cumple la gramatica. Se falla fuerte y con numero de linea:
    estos archivos se editan a mano a proposito, y un parseo silencioso que
    devuelve datos equivocados es peor que un error."""


def dumps(data: dict, body: str = "") -> str:
    """Serializa. Las claves salen ordenadas para que los diffs de git sean
    estables — un diff ruidoso es un diff que nadie lee."""
    lines = [DELIM]
    for key in sorted(data):
        if not isinstance(key, str) or not key or any(c in key for c in ":\n"):
            raise FrontMatterError(f"clave invalida: {key!r}")
        lines.append(f"{key}: {json.dumps(data[key], ensure_ascii=False)}")
    lines.append(DELIM)
    lines.append("")
    if body:
        lines.append(body.rstrip())
        lines.append("")
    lines.append(_BODY_WARNING)
    lines.append("")
    return "\n".join(lines)


def loads(text: str) -> tuple[dict, str]:
    """Devuelve (front_matter, cuerpo)."""
    raw = text.lstrip("﻿")
    lines = raw.splitlines()
    if not lines or lines[0].strip() != DELIM:
        raise FrontMatterError("el archivo no empieza con '---'")

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == DELIM:
            end = i
            break
    if end is None:
        raise FrontMatterError("front-matter sin cierre '---'")

    data: dict = {}
    for lineno in range(1, end):
        line = lines[lineno]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            raise FrontMatterError(
                f"linea {lineno + 1}: la gramatica es plana, no admite indentacion. "
                "Un valor compuesto se escribe como JSON en una sola linea."
            )
        key, sep, value = line.partition(":")
        if not sep:
            raise FrontMatterError(f"linea {lineno + 1}: falta ':' en {line!r}")
        key = key.strip()
        value = value.strip()
        if key in data:
            raise FrontMatterError(f"linea {lineno + 1}: clave repetida {key!r}")
        try:
            data[key] = json.loads(value) if value else None
        except json.JSONDecodeError as exc:
            raise FrontMatterError(
                f"linea {lineno + 1}: el valor de {key!r} no es JSON valido ({value!r}). "
                'Los textos van entre comillas dobles: nombre: "Marcela".'
            ) from exc

    body = "\n".join(lines[end + 1 :]).strip()
    if body.endswith(_BODY_WARNING):
        body = body[: -len(_BODY_WARNING)].strip()
    return data, body
