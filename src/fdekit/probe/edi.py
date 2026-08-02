"""Parser y validador X12 para los cuatro mensajes que aparecen siempre.

    940  Warehouse Shipping Order      (cliente -> CD)
    945  Warehouse Shipping Advice     (CD -> cliente)
    214  Transportation Carrier Status (transportista -> cliente)
    856  Advance Ship Notice           (proveedor -> cliente)

Detalle que separa a quien hizo EDI de quien lo leyo: los separadores NO son
constantes. El sobre ISA es de largo fijo 106 y define el separador de elementos
en la posicion 3, el de subelementos en la 104 y el terminador de segmento en la
105. Asumir `*` y `~` funciona hasta el primer socio comercial que no los usa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

SEVERITY = ("ERROR", "WARN", "INFO")

REQUIRED_SEGMENTS: dict[str, list[str]] = {
    "940": ["W05", "N1", "W01", "W76"],
    "945": ["W06", "N1", "W12", "W03"],
    "214": ["B10", "LX", "AT7"],
    "856": ["BSN", "HL", "CTT"],
}

TRANSACTION_NAMES = {
    "940": "Warehouse Shipping Order",
    "945": "Warehouse Shipping Advice",
    "214": "Carrier Shipment Status",
    "856": "Advance Ship Notice",
}


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    segment: str | None = None


@dataclass
class X12Message:
    segments: list[list[str]]
    element_sep: str
    sub_sep: str
    seg_term: str
    raw: str = field(repr=False, default="")

    def by_id(self, seg_id: str) -> list[list[str]]:
        return [s for s in self.segments if s and s[0] == seg_id]

    def transaction_sets(self) -> list[str]:
        return [s[1] for s in self.by_id("ST") if len(s) > 1]

    def count(self, seg_id: str) -> int:
        return len(self.by_id(seg_id))


def parse_x12(text: str) -> X12Message:
    """Parsea respetando los separadores declarados en el sobre ISA."""
    text = text.strip()
    if text.startswith("ISA") and len(text) >= 106:
        element_sep = text[3]
        sub_sep = text[104]
        seg_term = text[105]
    else:
        element_sep, sub_sep, seg_term = "*", ":", "~"

    raw_segments = [s.strip() for s in text.split(seg_term)]
    segments = [s.split(element_sep) for s in raw_segments if s]
    return X12Message(segments, element_sep, sub_sep, seg_term, text)


def validate_transaction(msg: X12Message) -> list[Finding]:
    """Valida sobre, contadores y segmentos obligatorios."""
    f: list[Finding] = []

    isa, iea = msg.by_id("ISA"), msg.by_id("IEA")
    gs, ge = msg.by_id("GS"), msg.by_id("GE")
    st, se = msg.by_id("ST"), msg.by_id("SE")

    if not isa:
        f.append(Finding("ERROR", "ENV001", "falta el sobre ISA"))
    if not st:
        f.append(Finding("ERROR", "ENV002", "no hay ningun set de transaccion (ST)"))
        return f

    # Control numbers
    if isa and iea and len(isa[0]) > 13 and len(iea[0]) > 2:
        if isa[0][13].strip() != iea[0][2].strip():
            f.append(Finding("ERROR", "ENV003", f"ISA13 ({isa[0][13]}) != IEA02 ({iea[0][2]})"))
    if gs and ge and len(gs[0]) > 6 and len(ge[0]) > 2:
        if gs[0][6].strip() != ge[0][2].strip():
            f.append(Finding("ERROR", "ENV004", f"GS06 ({gs[0][6]}) != GE02 ({ge[0][2]})"))
    if iea and len(iea[0]) > 1 and int(iea[0][1] or 0) != len(gs):
        f.append(Finding("ERROR", "ENV005", f"IEA01 dice {iea[0][1]} grupos, hay {len(gs)}"))
    if ge and len(ge[0]) > 1 and int(ge[0][1] or 0) != len(st):
        f.append(Finding("ERROR", "ENV006", f"GE01 dice {ge[0][1]} transacciones, hay {len(st)}"))

    for s, e in zip(st, se):
        if len(s) > 2 and len(e) > 2 and s[2].strip() != e[2].strip():
            f.append(Finding("ERROR", "TRX001", f"ST02 ({s[2]}) != SE02 ({e[2]})"))

    # SE01 = cantidad de segmentos incluyendo ST y SE
    if st and se:
        try:
            i_st = msg.segments.index(st[0])
            i_se = msg.segments.index(se[0])
            actual = i_se - i_st + 1
            declared = int(se[0][1])
            if actual != declared:
                f.append(
                    Finding(
                        "ERROR",
                        "TRX002",
                        f"SE01 declara {declared} segmentos, el mensaje trae {actual}",
                        "SE",
                    )
                )
        except (ValueError, IndexError):
            f.append(Finding("WARN", "TRX003", "no se pudo verificar el conteo de SE01"))

    # Segmentos obligatorios por tipo
    for code in msg.transaction_sets():
        req = REQUIRED_SEGMENTS.get(code)
        if req is None:
            f.append(Finding("INFO", "TRX004", f"set {code} sin regla de validacion cargada"))
            continue
        for seg in req:
            if msg.count(seg) == 0:
                f.append(
                    Finding(
                        "ERROR",
                        "SEG001",
                        f"{code} ({TRANSACTION_NAMES.get(code, '?')}): falta el segmento {seg}",
                        seg,
                    )
                )

    # CTT del 856: el contador que rompe el ASN en produccion
    for ctt in msg.by_id("CTT"):
        if len(ctt) > 1:
            declared = int(ctt[1] or 0)
            actual = msg.count("HL")
            if declared != actual:
                f.append(
                    Finding("ERROR", "SEG002", f"CTT01 declara {declared} HL, hay {actual}", "CTT")
                )

    # Fechas: el clasico que nadie chequea hasta que rompe
    for seg in msg.segments:
        for i, el in enumerate(seg[1:], start=1):
            if len(el) == 6 and el.isdigit() and seg[0] in ("W05", "W06", "B10", "BSN", "DTM"):
                f.append(
                    Finding(
                        "WARN",
                        "FMT001",
                        f"{seg[0]}{i:02d} usa fecha YYMMDD ({el}): ambigua, exigir CCYYMMDD",
                        seg[0],
                    )
                )
    return f


def smoke_report(messages: dict[str, str]) -> pd.DataFrame:
    """Corre la validacion sobre un lote de mensajes. Una fila por hallazgo.

    Esto es lo que va en CI: si el socio comercial cambia algo, el build se cae
    antes de que el cambio llegue a un despacho real.
    """
    rows = []
    for name, text in messages.items():
        try:
            msg = parse_x12(text)
            sets = ",".join(msg.transaction_sets()) or "?"
            findings = validate_transaction(msg)
        except Exception as exc:  # el parseo tambien es un test
            rows.append(
                {
                    "message": name,
                    "transaction": "?",
                    "severity": "ERROR",
                    "code": "PARSE",
                    "detail": str(exc),
                }
            )
            continue

        if not findings:
            rows.append(
                {"message": name, "transaction": sets, "severity": "OK", "code": "-", "detail": "sin hallazgos"}
            )
        for x in findings:
            rows.append(
                {
                    "message": name,
                    "transaction": sets,
                    "severity": x.severity,
                    "code": x.code,
                    "detail": x.message,
                }
            )

    df = pd.DataFrame(rows)
    order = {"ERROR": 0, "WARN": 1, "INFO": 2, "OK": 3}
    return df.sort_values(
        ["severity", "message"], key=lambda s: s.map(order) if s.name == "severity" else s
    ).reset_index(drop=True)
