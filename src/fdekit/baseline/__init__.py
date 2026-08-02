"""Herramienta 6 — arnes de linea base y contrafactual.

La fase que todos se saltan por presion comercial. Peleala: es la que define si
a los 90 dias tenes caso de renovacion o una discusion de opinion contra opinion.
"""

from .design import mde, required_days, BaselineSpec
from .analysis import pre_post, diff_in_diff, bootstrap_ci

__all__ = ["mde", "required_days", "BaselineSpec", "pre_post", "diff_in_diff", "bootstrap_ci"]
