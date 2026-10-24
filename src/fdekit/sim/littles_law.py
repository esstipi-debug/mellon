"""Ley de Little y chequeo de capacidad de servilleta.

    WIP = throughput x tiempo de ciclo

Resuelve el 80% de las discusiones de capacidad sin abrir un simulador. Usalo en
la reunion; el simulador es para el documento.
"""

from __future__ import annotations

import math

_RATE_UNIT_SECONDS = {
    "per_hour": 3600.0,
    "per_minute": 60.0,
    "per_second": 1.0,
}


def little(wip: float | None = None, throughput: float | None = None, cycle_time: float | None = None) -> dict:
    """Resuelve la variable faltante. Unidades consistentes (p.ej. pedidos, pedidos/h, h)."""
    known = [x is not None for x in (wip, throughput, cycle_time)]
    if sum(known) != 2:
        raise ValueError("hay que dar exactamente dos de las tres variables")

    if wip is None:
        wip = throughput * cycle_time  # type: ignore[operator]
    elif throughput is None:
        throughput = wip / cycle_time  # type: ignore[operator]
    else:
        cycle_time = wip / throughput  # type: ignore[operator]

    return {"wip": round(wip, 3), "throughput": round(throughput, 3), "cycle_time": round(cycle_time, 3)}


def capacity_check(demand_per_hour: float, service_time_s: float, servers: int, availability: float = 0.85) -> dict:
    """¿Da la capacidad instalada? Incluye disponibilidad real (colacion,
    briefing, fallas), que es lo que casi siempre falta en la cuenta del vendor.
    """
    effective_servers = servers * availability
    capacity_per_hour = effective_servers * 3600 / service_time_s
    utilization = demand_per_hour / capacity_per_hour if capacity_per_hour else float("inf")

    return {
        "demand_per_hour": demand_per_hour,
        "capacity_per_hour": round(capacity_per_hour, 1),
        "utilization": round(utilization, 3),
        "servers_required_at_85pct": math.ceil(
            demand_per_hour * service_time_s / 3600 / availability / 0.85
        ),
        # Sobre 0.85 de utilizacion la cola explota de forma no lineal. Ese es
        # el numero que hay que decirle al cliente que quiere correr al 95%.
        "verdict": (
            "holgado" if utilization < 0.7
            else "ajustado" if utilization < 0.85
            else "cola explosiva" if utilization < 1.0
            else "no da: la demanda supera la capacidad"
        ),
    }


def mm_c_wait(
    arrival_rate: float,
    service_rate: float,
    servers: int,
    rate_unit: str = "per_hour",
) -> dict:
    """Espera media en cola M/M/c (formula de Erlang C).

    Aproximacion util para la conversacion rapida. El DES existe justamente
    porque la operacion real no es markoviana, pero esto acota el orden de
    magnitud en diez segundos.

    `arrival_rate` y `service_rate` comparten `rate_unit` (por defecto
    `per_hour`, igual que `capacity_check`). `wq_s` y `w_total_s` se devuelven
    siempre convertidos a segundos reales.
    """
    if rate_unit not in _RATE_UNIT_SECONDS:
        raise ValueError(f"rate_unit desconocida: {rate_unit!r}")
    scale_s = _RATE_UNIT_SECONDS[rate_unit]

    lam, mu, c = arrival_rate, service_rate, servers
    rho = lam / (c * mu)
    if rho >= 1:
        return {
            "rho": round(rho, 3),
            "stable": False,
            "rate_unit": rate_unit,
            "wq_native": float("inf"),
            "wq_s": float("inf"),
            "lq": float("inf"),
            "w_total_s": float("inf"),
        }

    a = lam / mu
    s = sum(a**k / math.factorial(k) for k in range(c))
    last = a**c / (math.factorial(c) * (1 - rho))
    p0 = 1 / (s + last)
    pw = last * p0  # probabilidad de esperar (Erlang C)
    wq = pw / (c * mu - lam)
    w_total = wq + 1 / mu

    return {
        "rho": round(rho, 3),
        "stable": True,
        "rate_unit": rate_unit,
        "prob_wait": round(pw, 3),
        "wq_native": round(wq, 4),
        "wq_s": round(wq * scale_s, 1),
        "lq": round(lam * wq, 2),
        "w_total_s": round(w_total * scale_s, 1),
    }
