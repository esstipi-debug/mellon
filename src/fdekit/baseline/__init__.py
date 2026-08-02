"""Herramienta 6 — arnes de linea base y contrafactual.

La fase que todos se saltan por presion comercial. Peleala: es la que define si
a los 90 dias tenes caso de renovacion o una discusion de opinion contra opinion.
"""

from .design import BaselineSpec, mde, required_days, sd_from_log
from .analysis import pre_post, diff_in_diff, bootstrap_ci, parallel_trends_check

# `parallel_trends_check` faltaba aca, y esa omision es la razon practica por la
# que el supuesto que sostiene TODO el estimador DiD nunca se verificaba en una
# corrida: la funcion existia, estaba bien escrita, y no habia forma comoda de
# importarla. Un chequeo que no corre es un chequeo que no existe.
__all__ = [
    "mde",
    "required_days",
    "BaselineSpec",
    "pre_post",
    "diff_in_diff",
    "bootstrap_ci",
    "parallel_trends_check",
    "sd_from_log",
]
