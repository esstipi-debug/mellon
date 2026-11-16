# probes: Chapter 3 oracles (master copy)

This directory is the **single master** of the two Chapter 3 probes of *The Deployment Chasm* and of their tests. A copy of these files anywhere else (a dossier's evidence folder, a mirror, a zip) is a snapshot: cite this path and a commit of this repository, never the copy.

| Probe | What it computes | Test file |
|---|---|---|
| `cap3_delta_projection.py` | The decoupled inbound state machine as three coordinates: physical lot state `s`, accounting state `a`, carrier truck state `d`. A total, deterministic transition function `delta` over their product, with a bounded quarantine buffer that never drops a lot. | `test_cap3_delta_projection.py`: totality, determinism, exhaustive reachability of the `(s, a, d)` space, negative controls, buffer accounting. |
| `quarantine_capacity.py` | The two ceilings of a receiving yard under conditional blocked receipt: dock doors (M/M/c, Erlang C) and quarantine floor positions (Little's Law, `L = lambda * r * R`), and the retention rate `r*` where they cross. | `test_quarantine_capacity.py`: the Little's Law identity, parity with `fdekit.sim.littles_law.mm_c_wait`, monotonicity, classification. |

## Run

```bash
python -m pytest probes -q
```

At the commit that introduced this file the run is **35 passed**. The count is a fact about that commit, not a promise: after any change, re-run and re-anchor the number wherever it is quoted.

## What this proves and what it does not

- It proves properties of **a model**: the transition function is total and deterministic, every configuration in the product is reachable or explicitly rejected, the buffer arithmetic balances, the queueing formulas agree with the repository's own implementation.
- It does **not** measure a real yard, and it says nothing about the signing guards of this kit. The known limits of those guards are pinned, as strict `xfail` tests, in [`../tests/test_limites_conocidos_kit.py`](../tests/test_limites_conocidos_kit.py).
