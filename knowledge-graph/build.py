"""Build every output format from graph.json, research/*.md and scenarios.json.

Outputs (in ./out):
  - index.html      interactive graph (vis-network; nodes, edges, resources, field dossiers)
  - dojo.html       FDE Field Dojo (3 training modes, offline-first, localStorage state)
  - graph.json      validated + predicate-normalized copy of the data
  - neo4j.cypher    import script for Neo4j (strictly the 12 canonical predicates)
  - obsidian/       vault: one note per node, [[wikilinks]], external resources,
                    tactical field dossiers appended to every Book note

Usage:  python build.py

The build is fail-closed: duplicated ids, broken edges, orphan nodes, non-canonical
predicates, missing descriptors or a scenario that references a node that does not
exist in graph.json abort the build with a non-zero exit code.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "graph.json"
OUT = ROOT / "out"
TEMPLATE = ROOT / "template.html"
DOJO_TEMPLATE = ROOT / "dojo_template.html"
SCENARIOS = ROOT / "scenarios.json"
RESEARCH_DIR = ROOT / "research"

BOOK_FOLDERS = {
    "htma": "01 How to Measure Anything",
    "ta": "02 The Trusted Advisor",
    "mom": "03 The Mom Test",
    "pp": "04 The Pyramid Principle",
    "bps": "05 Bulletproof Problem Solving",
    "sw": "06 Switch",
    "fc": "07 Flawless Consulting",
    "cdh": "08 Continuous Discovery Habits",
    "fde": "99 FDE Synthesis",
}

NODE_TYPES = {
    "Book",
    "Author",
    "Concept",
    "Framework",
    "Principle",
    "Technique",
    "Pitfall",
    "CrossInsight",
    "FDEPractice",
}

# The only predicates allowed in the exported graph / Cypher script.
CANONICAL_PREDICATES = {
    "APPLIES",
    "SYNTHESIZES",
    "FEEDS",
    "MITIGATES",
    "CAUSES",
    "HAS_STEP",
    "HAS_COMPONENT",
    "USES",
    "ANALOGOUS_TO",
    "MEASURES",
    "FROM_BOOK",
    "AUTHORED",
}

# Legacy 59-predicate vocabulary (commit daf11ff) -> canonical predicate.
# `inverted=True` means the historical edge direction was semantically backwards
# and the endpoints must be swapped to preserve meaning.
#
# A handful of legacy verbs were ambiguous and were resolved per-edge during the
# normalization commit; the table below documents the dominant mapping used as a
# regression guard if hand-edited data reintroduces old verbs.
PREDICATE_ALIASES: dict[str, tuple[str, bool]] = {
    "PRODUCES": ("FEEDS", False),
    "PRODUCED_BY": ("FEEDS", True),
    "INPUT_TO": ("FEEDS", False),
    "DETERMINES": ("FEEDS", False),
    "LEADS_TO": ("FEEDS", False),
    "PRECEDES": ("FEEDS", False),
    "FOLLOWS": ("FEEDS", True),
    "ENABLES": ("FEEDS", False),
    "SUPPORTS": ("FEEDS", False),
    "MOTIVATES": ("FEEDS", False),
    "DRIVES": ("FEEDS", False),
    "BUILDS": ("FEEDS", False),
    "BUILT_THROUGH": ("FEEDS", True),
    "ESTABLISHES": ("FEEDS", False),
    "SHAPES": ("FEEDS", False),
    "FRAMES": ("FEEDS", False),
    "DISCOVERS": ("FEEDS", False),
    "UNCOVERS": ("FEEDS", False),
    "PRIORITIZES": ("FEEDS", False),
    "SYNTHESIZES_FROM": ("FEEDS", True),
    "OPERATIONALIZES": ("APPLIES", False),
    "EMBODIES": ("APPLIES", False),
    "EXEMPLIFIES": ("APPLIES", False),
    "IMPLEMENTS": ("APPLIES", False),
    "PERFORMED_BY": ("APPLIES", True),
    "REQUIRES": ("USES", False),
    "ROOTED_IN": ("USES", False),
    "INCLUDES": ("HAS_COMPONENT", False),
    "HAS_RULE": ("HAS_COMPONENT", False),
    "SHOULD_INCLUDE": ("HAS_COMPONENT", False),
    "STRUCTURES": ("HAS_COMPONENT", False),
    "COVERS": ("HAS_COMPONENT", False),
    "MANIFESTS_AS": ("HAS_COMPONENT", False),
    "PART_OF": ("HAS_COMPONENT", True),
    "EXTENDS": ("HAS_COMPONENT", True),
    "RESOLVED_BY": ("MITIGATES", True),
    "REPLACED_BY": ("MITIGATES", True),
    "ADDRESSES": ("MITIGATES", False),
    "AVOIDS": ("MITIGATES", False),
    "PRUNES": ("MITIGATES", False),
    "DECREASES": ("MITIGATES", False),
    "RISKS": ("CAUSES", False),
    "TRIGGERS": ("CAUSES", False),
    "CHALLENGES": ("CAUSES", False),
    "INCREASES": ("CAUSES", False),
    "MEASURED_IN": ("MEASURES", True),
    "TESTS": ("MEASURES", False),
    "ALTERNATIVE_TO": ("ANALOGOUS_TO", False),
    "SYNTHESIZES": ("SYNTHESIZES", False),
}

PHASES = {
    "Discovery & Contracting",
    "Diagnosis & Measurement",
    "Resistance & Change",
    "Executive Synthesis",
}
PHASE_SHORT = {
    "Discovery & Contracting": "Discovery",
    "Diagnosis & Measurement": "Diagnosis",
    "Resistance & Change": "Resistance",
    "Executive Synthesis": "Synthesis",
}
METRICS = ("TQ", "SIG", "EVI", "ADP")
BOOTCAMP_THEMES = {
    1: "Contracting & Scoping",
    2: "Gemba & Dirty Data Ontology",
    3: "Prototype & Guardrails (Human-in-the-loop)",
    4: "Rebelión de Operadores en Terreno",
    5: "Executive Go/No-Go ante el CFO/COO",
}
BOOTCAMP_IDS = {"camp_skywise_supply", "camp_retail_nosilo"}
BOOK_KEYS = set(BOOK_FOLDERS)

# Named frameworks/books/techniques that must never appear in pre-answer fields.
# They are allowed (and expected) in explanations and feedback, after the answer.
TELL_TERMS = (
    "How to Measure Anything", "Trusted Advisor", "Mom Test", "Pyramid Principle",
    "Bulletproof Problem Solving", "Flawless Consulting", "Continuous Discovery",
    "Hubbard", "Maister", "Minto", "Torres", "Fitzpatrick", "Peter Block", "Heath",
    "Palantir", "Skywise", "AIP", "Rule of Five", "MECE", "SCQ", "Trust Equation",
    "Opportunity Solution Tree", "Clarification Chain", "Measurement Inversion",
    "Confirmation Bias", "Endless Detail", "Zombie", "Fluff", "Compliment",
    "Feature Request", "Pitching", "Decision Paralysis", "Equivalent Bet",
    "90% CI", "CI del 90", "Monte Carlo", "Bayesian", "EVPI", "EVSI",
    "Pair-of-Hands", "Human-in-the-loop", "Rider", "Elephant", "Bright Spots",
    "Shrink the Change", "50/50", "Answer-First", "Answer First", "Action Title",
    "Issue Tree", "Red Team", "Contracting", "Workplan", "OST", "Playbook",
)
NO_DOSSIER_LAYERS = {"fde"}


# --------------------------------------------------------------------------- #
# Loading & validation
# --------------------------------------------------------------------------- #
def _fail(title: str, items: list[str] | set[str]) -> None:
    lines = "\n  - ".join(sorted(str(i) for i in items))
    raise SystemExit(f"BUILD FAILED — {title}:\n  - {lines}")


def normalize_predicates(data: dict) -> tuple[dict, list[str]]:
    """Rewrite legacy predicates to the canonical vocabulary (in place-safe)."""
    rewritten: list[str] = []
    edges = []
    for edge in data["edges"]:
        rel = edge["relation"]
        source, target, props = edge["source"], edge["target"], edge
        if rel in CANONICAL_PREDICATES:
            edges.append(props)
            continue
        if rel not in PREDICATE_ALIASES:
            _fail("unknown edge predicate (not canonical, not in alias table)", [rel])
        canonical, inverted = PREDICATE_ALIASES[rel]
        if inverted:
            source, target = target, source
        edges.append({"source": source, "target": target, "relation": canonical})
        rewritten.append(f"{rel} -> {canonical}" + (" (inverted)" if inverted else ""))
    data["edges"] = edges
    return data, rewritten


def load_graph() -> tuple[dict, list[str]]:
    if not SRC.exists():
        raise SystemExit(f"BUILD FAILED — graph source not found: {SRC}")
    try:
        data = json.loads(SRC.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"BUILD FAILED — graph.json is not valid JSON: {exc}") from exc

    for key in ("meta", "nodes", "edges", "resources"):
        if key not in data:
            raise SystemExit(f"BUILD FAILED — graph.json is missing top-level key '{key}'")

    meta = data["meta"]
    if not isinstance(meta.get("books"), dict):
        raise SystemExit("BUILD FAILED — meta.books must be a mapping of layer -> label")
    missing_layers = BOOK_KEYS - set(meta["books"])
    if missing_layers:
        _fail("meta.books does not describe every layer", missing_layers)

    ids = [n.get("id") for n in data["nodes"]]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        _fail("duplicate node ids", duplicates)
    idset = set(ids)

    bad_nodes = []
    for n in data["nodes"]:
        for key in ("id", "label", "type", "book", "description"):
            if not isinstance(n.get(key), str) or not n[key].strip():
                bad_nodes.append(f"{n.get('id')!r} missing/blank '{key}'")
        if n.get("type") not in NODE_TYPES:
            bad_nodes.append(f"{n.get('id')!r} has unknown type {n.get('type')!r}")
        if n.get("book") not in BOOK_KEYS:
            bad_nodes.append(f"{n.get('id')!r} has unknown book {n.get('book')!r}")
    if bad_nodes:
        _fail("malformed nodes", bad_nodes)

    data, rewritten = normalize_predicates(data)
    if rewritten:
        print(f"NOTE: normalized {len(rewritten)} legacy predicate edge(s) -> canonical vocabulary")

    unknown = {e["relation"] for e in data["edges"]} - CANONICAL_PREDICATES
    if unknown:
        _fail("non-canonical edge predicates", unknown)

    bad_edges = [
        f"{e.get('source')} -[{e.get('relation')}]-> {e.get('target')}"
        for e in data["edges"]
        if e.get("source") not in idset or e.get("target") not in idset
    ]
    if bad_edges:
        _fail("edges referencing unknown nodes", bad_edges)

    self_loops = [f"{e['source']} -[{e['relation']}]-> itself" for e in data["edges"] if e["source"] == e["target"]]
    if self_loops:
        _fail("self-referencing edges", self_loops)

    seen_edges = Counter((e["source"], e["relation"], e["target"]) for e in data["edges"])
    duplicate_edges = {f"{s} -[{r}]-> {t} (x{c})" for (s, r, t), c in seen_edges.items() if c > 1}
    if duplicate_edges:
        _fail("duplicate edges", duplicate_edges)

    linked = {e["source"] for e in data["edges"]} | {e["target"] for e in data["edges"]}
    orphans = idset - linked
    if orphans:
        _fail("orphan nodes (no incoming or outgoing edge)", orphans)

    by_id = {n["id"]: n for n in data["nodes"]}
    bad_resources = []
    for r in data["resources"]:
        nid = r.get("node_id")
        url = r.get("url", "")
        if nid not in idset:
            bad_resources.append(f"resource {r.get('title')!r} points at unknown node {nid!r}")
        if not re.match(r"^https?://", url):
            bad_resources.append(f"resource {r.get('title')!r} has a non-http url {url!r}")
        if not r.get("title") or not r.get("kind"):
            bad_resources.append(f"resource for {nid!r} is missing title/kind")
    if bad_resources:
        _fail("invalid external resources", bad_resources)

    # Obsidian note filenames must be unique per folder.
    collisions = Counter((n["book"], safe_name(n["label"])) for n in data["nodes"])
    dup_labels = {f"{book}/{name}" for (book, name), count in collisions.items() if count > 1}
    if dup_labels:
        _fail("node labels collide inside a book folder", dup_labels)

    # Books / authors consistency: every Book node referenced by FROM_BOOK should
    # exist, and every Author should have an AUTHORED edge to a real Book.
    book_nodes = {n["book"]: n["id"] for n in data["nodes"] if n["type"] == "Book"}
    missing_books = BOOK_KEYS - NO_DOSSIER_LAYERS - set(book_nodes)
    if missing_books:
        _fail("missing Book node for layer", missing_books)
    empty_books = []
    for layer, node_id in book_nodes.items():
        incoming_book = [e for e in data["edges"] if e["target"] == node_id and e["relation"] == "FROM_BOOK"]
        incoming_author = [e for e in data["edges"] if e["target"] == node_id and e["relation"] == "AUTHORED"]
        if len(incoming_book) < 5:
            empty_books.append(f"{node_id}: only {len(incoming_book)} FROM_BOOK edges point at it")
        if not incoming_author:
            empty_books.append(f"{node_id}: no AUTHORED edge from an Author node")
    if empty_books:
        _fail("Book node wiring incomplete", empty_books)

    print(
        f"OK graph: {len(data['nodes'])} nodes, {len(data['edges'])} edges, "
        f"{len(data['resources'])} resources, {len({n['book'] for n in data['nodes']})} layers"
    )
    return data, rewritten


def safe_name(label: str) -> str:
    name = label.replace("/", "-")
    name = re.sub(r'[\\:*?"<>|#^\[\]]', "", name)
    return re.sub(r"\s+", " ", name).strip()


def load_dossiers() -> dict[str, dict[str, str]]:
    """Load research/<book>.md: full markdown, tactical section, title and headings."""
    dossiers: dict[str, dict[str, str]] = {}
    if not RESEARCH_DIR.exists():
        print("WARNING: research/ folder not found — no field dossiers embedded")
        return dossiers
    for layer in BOOK_KEYS - NO_DOSSIER_LAYERS:
        md_file = RESEARCH_DIR / f"{layer}.md"
        if not md_file.exists():
            print(f"WARNING: missing dossier research/{layer}.md")
            continue
        text = md_file.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        section = re.search(r"^##\s+3\.", text, flags=re.MULTILINE)
        tactical = text[section.start():].strip() if section else text
        sections = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)
        dossiers[layer] = {
            "title": title_match.group(1).strip() if title_match else layer.upper(),
            "full": text,
            "tactical": tactical,
            "sections": sections,
        }
    if len(dossiers) != len(BOOK_KEYS - NO_DOSSIER_LAYERS):
        print(f"WARNING: only {len(dossiers)} of 8 book dossiers found")
    return dossiers


# --------------------------------------------------------------------------- #
# Scenario / calibration bank validation (the Dojo cannot reference ghosts)
# --------------------------------------------------------------------------- #
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"BUILD FAILED — scenarios.json: {message}")


def _check_node_ref(by_id: dict[str, dict], node_id: str, allowed_types: set[str] | None, where: str) -> None:
    if node_id not in by_id:
        raise SystemExit(f"BUILD FAILED — scenarios.json: {where} references unknown node id '{node_id}'")
    if allowed_types and by_id[node_id]["type"] not in allowed_types:
        raise SystemExit(
            f"BUILD FAILED — scenarios.json: {where} node '{node_id}' is a "
            f"{by_id[node_id]['type']}, expected one of {sorted(allowed_types)}"
        )


def load_scenarios(by_id: dict[str, dict], books: dict[str, str]) -> dict:
    if not SCENARIOS.exists():
        raise SystemExit(f"BUILD FAILED — scenario bank not found: {SCENARIOS}")
    try:
        bank = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"BUILD FAILED — scenarios.json is not valid JSON: {exc}") from exc

    for key in ("meta", "scenarios", "calibration_questions", "sparring", "bootcamps", "forge_missions"):
        _require(key in bank, f"missing top-level key '{key}'")

    scenarios = bank["scenarios"]
    _require(isinstance(scenarios, list) and len(scenarios) >= 33,
             f"needs at least 33 scenarios (including 6 Palantir cases), found {len(scenarios) if isinstance(scenarios, list) else 0}")
    ids = [s.get("id") for s in scenarios]
    _require(len(ids) == len(set(ids)), f"duplicate scenario ids: {sorted({i for i in ids if ids.count(i) > 1})}")

    per_book = Counter()
    for idx, s in enumerate(scenarios, 1):
        where = f"scenario #{idx} ({s.get('id', '?')})"
        for key in ("id", "title", "book", "phase", "context", "stakeholder_role",
                    "stakeholder_quote", "diagnosis_question", "action_question"):
            _require(isinstance(s.get(key), str) and s[key].strip(), f"{where} missing/blank '{key}'")
        _require(s["book"] in books, f"{where} has unknown book '{s['book']}'")
        _require(s["phase"] in PHASES, f"{where} has unknown phase '{s['phase']}'")
        _require(s.get("difficulty", "core") in {"core", "advanced", "boss"}, f"{where} invalid difficulty")
        if s.get("case_study"):
            _require(s["case_study"] == "palantir", f"{where} unknown case_study '{s['case_study']}'")
            _require(s.get("case_org"), f"{where} Palantir case needs case_org")
            _require(s.get("difficulty") == "boss", f"{where} Palantir case must be difficulty='boss'")
        per_book[s["book"]] += 1

        pitfalls = s.get("active_pitfalls")
        _require(isinstance(pitfalls, list) and 1 <= len(pitfalls) <= 3, f"{where} needs 1-3 active_pitfalls")
        for pid in pitfalls:
            _check_node_ref(by_id, pid, {"Pitfall"}, where)

        techniques = s.get("target_techniques")
        _require(isinstance(techniques, list) and 1 <= len(techniques) <= 5, f"{where} needs 1-5 target_techniques")
        for tid in techniques:
            _check_node_ref(by_id, tid, {"Technique"}, where)

        for sid in s.get("supporting_nodes", []):
            _check_node_ref(by_id, sid, None, where)
        _check_node_ref(by_id, s.get("target_practice", ""), {"FDEPractice"}, where)

        diag = s.get("diagnosis_options")
        _require(isinstance(diag, list) and len(diag) >= 3, f"{where} needs at least 3 diagnosis_options")
        _require(sum(1 for o in diag if o.get("is_correct") is True) == 1,
                 f"{where} needs exactly one correct diagnosis option")
        _require(len({o.get("id") for o in diag}) == len(diag), f"{where} has duplicate diagnosis option ids")
        for o in diag:
            _require(o.get("text") and o.get("explanation"), f"{where} diagnosis option needs text + explanation")

        actions = s.get("action_options")
        _require(isinstance(actions, list) and len(actions) >= 3, f"{where} needs at least 3 action_options")
        _require(sum(1 for o in actions if o.get("is_best") is True) == 1,
                 f"{where} needs exactly one best action option")
        _require(len({o.get("id") for o in actions}) == len(actions), f"{where} has duplicate action option ids")
        for o in actions:
            _require(o.get("label") and o.get("script") and o.get("feedback"),
                     f"{where} action option needs label + script + feedback")
            deltas = o.get("deltas")
            _require(isinstance(deltas, dict) and set(deltas) == set(METRICS),
                     f"{where} action '{o.get('id')}' deltas must define exactly {list(METRICS)}")
            for metric, value in deltas.items():
                _require(isinstance(value, int) and not isinstance(value, bool) and -50 <= value <= 50,
                         f"{where} action '{o.get('id')}' delta {metric}={value!r} out of range (-50..50)")

    missing_books = [b for b in BOOK_KEYS - {"fde"} if per_book[b] < 3]
    _require(not missing_books, f"every book needs at least 3 scenarios; missing: {missing_books}")
    _require(per_book["fde"] >= 3, f"FDE synthesis layer needs at least 3 scenarios, found {per_book['fde']}")
    palantir_cases = [s for s in scenarios if s.get("case_study") == "palantir"]
    _require(len(palantir_cases) == 6,
             f"exactly 6 Palantir cases are required, found {len(palantir_cases)}")
    palantir_ids = {"scen_28_palantir_airbus", "scen_29_palantir_tyson", "scen_30_palantir_nhs",
                    "scen_31_palantir_pge", "scen_32_palantir_jacobs", "scen_33_palantir_cleveland"}
    _require(palantir_ids <= {s["id"] for s in palantir_cases},
             f"missing Palantir case ids: {sorted(palantir_ids - {s['id'] for s in palantir_cases})}")
    _validate_anti_gaming(scenarios)

    questions = bank["calibration_questions"]
    _require(isinstance(questions, list) and len(questions) >= 15,
             f"needs at least 15 calibration questions, found {len(questions) if isinstance(questions, list) else 0}")
    qids = [q.get("id") for q in questions]
    _require(len(qids) == len(set(qids)), f"duplicate calibration question ids: {[q for q in qids if qids.count(q) > 1]}")
    for idx, q in enumerate(questions, 1):
        where = f"calibration question #{idx} ({q.get('id', '?')})"
        for key in ("id", "prompt", "unit", "category", "source", "why"):
            _require(isinstance(q.get(key), str) and q[key].strip(), f"{where} missing/blank '{key}'")
        _require(isinstance(q.get("answer"), (int, float)) and not isinstance(q.get("answer"), bool),
                 f"{where} needs a numeric answer")
        _require(isinstance(q.get("plausible_ratio"), (int, float)) and q["plausible_ratio"] > 1,
                 f"{where} needs plausible_ratio > 1")

    sparring = bank["sparring"]
    for key in ("contexts", "objections", "rubric", "turns"):
        _require(key in sparring, f"sparring missing '{key}'")
    _require(len(sparring["contexts"]) >= 4, "sparring needs at least 4 operational contexts")
    _require(len(sparring["objections"]) >= 4, "sparring needs at least 4 emotional objections")
    _require(sparring["turns"] == 8, "sparring turns must be 8")
    rubric = sparring["rubric"]
    _require(isinstance(rubric, list) and len(rubric) == 5, "sparring rubric must have exactly 5 dimensions")
    _require(sum(d.get("weight", 0) for d in rubric) == 100, "sparring rubric weights must sum to 100")
    for dimension in rubric:
        for key in ("id", "label", "weight", "prompt", "anchor_low", "anchor_high"):
            _require(dimension.get(key), f"sparring rubric dimension missing '{key}'")
        for node_id in dimension.get("nodes", []):
            _check_node_ref(by_id, node_id, None, f"sparring rubric '{dimension['id']}'")
    for context in sparring["contexts"]:
        for key in ("id", "label", "brief", "stakeholder_role", "pressure"):
            _require(context.get(key), f"sparring context missing '{key}'")
        for pitfall_id in context.get("suggested_pitfalls", []):
            _check_node_ref(by_id, pitfall_id, {"Pitfall"}, f"sparring context '{context['id']}'")

    bootcamps = bank["bootcamps"]
    _validate_bootcamps(bootcamps, by_id)

    forge_missions = bank["forge_missions"]
    _require(isinstance(forge_missions, list) and len(forge_missions) >= 6,
             f"needs at least 6 forge_missions, found {len(forge_missions) if isinstance(forge_missions, list) else 0}")
    fids = [m.get("id") for m in forge_missions]
    _require(len(fids) == len(set(fids)), f"duplicate forge mission ids: {fids}")
    for idx, m in enumerate(forge_missions, 1):
        where = f"forge_mission #{idx} ({m.get('id', '?')})"
        for key in ("id", "archetype", "archetypeLabel", "title", "phase", "practice", "trapWarning"):
            _require(isinstance(m.get(key), str) and m[key].strip(), f"{where} missing/blank '{key}'")
        _require(m["archetype"] in {"scqa", "mom", "bps"}, f"{where} invalid archetype '{m['archetype']}'")
        _require(m["phase"] in PHASES, f"{where} invalid phase '{m['phase']}'")
        _check_node_ref(by_id, m["practice"], {"FDEPractice"}, where)
        _require(isinstance(m.get("nodes"), list) and len(m["nodes"]) >= 3, f"{where} needs at least 3 nodes")
        for nid in m["nodes"]:
            _check_node_ref(by_id, nid, None, where)
        _require(isinstance(m.get("rawFacts"), list) and len(m["rawFacts"]) >= 3, f"{where} needs rawFacts")
        fields = m.get("fields")
        gold = m.get("gold")
        _require(isinstance(fields, list) and len(fields) >= 3, f"{where} needs at least 3 fields")
        _require(isinstance(gold, dict), f"{where} needs gold dict")
        for f in fields:
            fid = f.get("id")
            _require(fid and f.get("label") and f.get("placeholder"), f"{where} field missing id/label/placeholder")
            _require(isinstance(gold.get(fid), str) and gold[fid].strip(), f"{where} missing gold standard for '{fid}'")

    # Enforce 100% node coverage across all non-Book / non-Author nodes
    covered_nodes: set[str] = set()
    for s in scenarios:
        covered_nodes.update(s.get("active_pitfalls", []))
        covered_nodes.update(s.get("target_techniques", []))
        covered_nodes.update(s.get("supporting_nodes", []))
        if s.get("target_practice"):
            covered_nodes.add(s["target_practice"])
    for c in bootcamps["campaigns"]:
        for st in c["stages"]:
            covered_nodes.update(st.get("active_pitfalls", []))
            covered_nodes.update(st.get("target_techniques", []))
            covered_nodes.update(st.get("supporting_nodes", []))
            if st.get("target_practice"):
                covered_nodes.add(st["target_practice"])
    for m in forge_missions:
        covered_nodes.update(m.get("nodes", []))
        if m.get("practice"):
            covered_nodes.add(m["practice"])

    trainable_nodes = {nid for nid, n in by_id.items() if n["type"] not in {"Book", "Author"}}
    uncovered = sorted(trainable_nodes - covered_nodes)
    _require(not uncovered, f"trainable graph nodes missing from Dojo scenarios/bootcamps/forge: {uncovered}")

    print(
        f"OK dojo bank: {len(scenarios)} scenarios ({len(palantir_cases)} Palantir), "
        f"{len(questions)} calibration questions, {len(sparring['contexts'])} contexts, "
        f"{len(bootcamps['campaigns'])} bootcamps / "
        f"{sum(len(c['stages']) for c in bootcamps['campaigns'])} stages, "
        f"{len(forge_missions)} forge missions, "
        f"{len(trainable_nodes)}/{len(trainable_nodes)} trainable nodes covered (100%)"
    )
    return bank


def _validate_anti_gaming(scenarios: list[dict]) -> None:
    """Fail-closed anti-gaming checks for pre-answer option text.

    - No named framework/book/technique may leak before the user answers.
    - Diagnosis texts and action labels must be length-balanced (max/min <= 1.25)
      so the correct option cannot be spotted just because it is the longest.
    Scripts are intentionally hidden by the UI until the user selects an option;
    they may name frameworks in their post-answer explanation.
    """
    def check_terms(text: str, where: str) -> None:
        for term in TELL_TERMS:
            if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE):
                raise SystemExit(
                    f"BUILD FAILED — scenarios.json: anti-gaming leak in {where}: "
                    f"pre-answer text mentions '{term}' (move it to explanation/feedback)."
                )

    for s in scenarios:
        where = f"scenario {s['id']}"
        diag = s["diagnosis_options"]
        for option in diag:
            check_terms(option["text"], f"{where} diagnosis {option['id']} text")
        labels = s["action_options"]
        for option in labels:
            check_terms(option["label"], f"{where} action {option['id']} label")
            check_terms(option["script"], f"{where} action {option['id']} script")
        for field, values, label in (
            ("diagnosis text", [len(o["text"].strip()) for o in diag], "diagnosis options"),
            ("action label", [len(o["label"].strip()) for o in labels], "action options"),
        ):
            ratio = max(values) / min(values) if min(values) else 99
            _require(
                ratio <= 1.25,
                f"{where} {label} are not length-balanced (max/min={ratio:.2f}); "
                f"lengths={values}. Keep distractors within ±20-25% of each other.",
            )


def _validate_bootcamps(bootcamps: dict, by_id: dict[str, dict]) -> None:
    _require(isinstance(bootcamps, dict), "bootcamps must be an object")
    rules = bootcamps.get("rules")
    _require(isinstance(rules, dict), "bootcamps.rules is required")
    _require(rules.get("days") == 5, "bootcamps.rules.days must be 5")
    start = rules.get("start_metrics")
    _require(isinstance(start, dict) and set(start) == set(METRICS),
             f"bootcamps.rules.start_metrics must define exactly {list(METRICS)}")
    _require(all(v == 55 for v in start.values()), "bootcamp must start every metric at 55")
    _require(rules.get("loss_threshold") == 30, "bootcamp loss_threshold must be 30")
    _require(rules.get("win_threshold") == 65, "bootcamp win_threshold must be 65")
    _require(rules.get("win_average") == 75, "bootcamp win_average must be 75")
    _require(bootcamps.get("day_themes") == {str(k): v for k, v in BOOTCAMP_THEMES.items()},
             "bootcamps.day_themes must match the five canonical Bootcamp days")

    campaigns = bootcamps.get("campaigns")
    _require(isinstance(campaigns, list) and len(campaigns) == 2,
             f"bootcamps needs exactly 2 campaigns, found {len(campaigns) if isinstance(campaigns, list) else 0}")
    _require({c.get("id") for c in campaigns} == BOOTCAMP_IDS,
             f"bootcamp ids must be {sorted(BOOTCAMP_IDS)}")
    stage_ids: set[str] = set()
    for campaign in campaigns:
        where = f"bootcamp {campaign.get('id', '?')}"
        for key in ("id", "title", "sector", "brief"):
            _require(isinstance(campaign.get(key), str) and campaign[key].strip(), f"{where} missing '{key}'")
        stages = campaign.get("stages")
        _require(isinstance(stages, list) and len(stages) == 5, f"{where} needs exactly 5 stages")
        _require([st.get("day") for st in stages] == [1, 2, 3, 4, 5], f"{where} stages must be ordered days 1..5")
        for stage in stages:
            sw = f"{where} stage {stage.get('id', '?')}"
            _require(stage.get("id") not in stage_ids, f"{sw} duplicate stage id")
            stage_ids.add(stage["id"])
            _require(stage.get("theme") == BOOTCAMP_THEMES[stage.get("day")],
                     f"{sw} theme must be '{BOOTCAMP_THEMES.get(stage.get('day'), '?')}'")
            for key in ("title", "context", "stakeholder_role", "stakeholder_quote", "objective", "decision_question"):
                _require(isinstance(stage.get(key), str) and stage[key].strip(), f"{sw} missing '{key}'")
            pitfalls = stage.get("active_pitfalls")
            _require(isinstance(pitfalls, list) and 1 <= len(pitfalls) <= 3, f"{sw} needs 1-3 active_pitfalls")
            for pid in pitfalls:
                _check_node_ref(by_id, pid, {"Pitfall"}, sw)
            techniques = stage.get("target_techniques")
            _require(isinstance(techniques, list) and 1 <= len(techniques) <= 5, f"{sw} needs 1-5 target_techniques")
            for tid in techniques:
                _check_node_ref(by_id, tid, {"Technique"}, sw)
            for sid in stage.get("supporting_nodes", []):
                _check_node_ref(by_id, sid, None, sw)
            _check_node_ref(by_id, stage.get("target_practice", ""), {"FDEPractice"}, sw)
            options = stage.get("options")
            _require(isinstance(options, list) and len(options) >= 3, f"{sw} needs at least 3 options")
            _require(sum(1 for o in options if o.get("is_best") is True) == 1, f"{sw} needs exactly one best option")
            _require(len({o.get("id") for o in options}) == len(options), f"{sw} has duplicate option ids")
            for option in options:
                _require(option.get("label") and option.get("script") and option.get("feedback"),
                         f"{sw} option '{option.get('id')}' needs label + script + feedback")
                for term in TELL_TERMS:
                    if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", option["label"], re.IGNORECASE):
                        raise SystemExit(
                            f"BUILD FAILED — scenarios.json: anti-gaming leak in {sw} option "
                            f"'{option.get('id')}' label: mentions '{term}'."
                        )
                    if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", option["script"], re.IGNORECASE):
                        raise SystemExit(
                            f"BUILD FAILED — scenarios.json: anti-gaming leak in {sw} option "
                            f"'{option.get('id')}' script: mentions '{term}'."
                        )
                deltas = option.get("deltas")
                _require(isinstance(deltas, dict) and set(deltas) == set(METRICS),
                         f"{sw} option '{option.get('id')}' deltas must define exactly {list(METRICS)}")
                for metric, value in deltas.items():
                    _require(isinstance(value, int) and not isinstance(value, bool) and -50 <= value <= 50,
                             f"{sw} option '{option.get('id')}' delta {metric}={value!r} out of range (-50..50)")
            label_lengths = [len(o["label"].strip()) for o in options]
            label_ratio = max(label_lengths) / min(label_lengths) if min(label_lengths) else 99
            _require(label_ratio <= 1.25,
                     f"{sw} option labels are not length-balanced (max/min={label_ratio:.2f}); lengths={label_lengths}")


# --------------------------------------------------------------------------- #
# HTML surfaces
# --------------------------------------------------------------------------- #
def _json_for_script(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def build_html(data: dict, dossiers: dict[str, dict[str, str]]) -> None:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in ("__GRAPH_DATA__", "__VIS_SRC__"):
        if placeholder not in tpl:
            raise SystemExit(f"BUILD FAILED — template.html has no {placeholder} placeholder")

    # Prefer the vendored vis-network build (offline-first); fall back to the CDN.
    vendor = ROOT / "vendor" / "vis-network.min.js"
    if vendor.exists():
        (OUT / "vendor").mkdir(exist_ok=True)
        shutil.copy2(vendor, OUT / "vendor" / "vis-network.min.js")
        vis_src = "vendor/vis-network.min.js"
        print(f"OK vendor: vendor/vis-network.min.js ({vendor.stat().st_size:,} bytes, offline viewer)")
    else:
        vis_src = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
        print("WARNING: vendor/vis-network.min.js missing — index.html will load vis-network from the CDN")

    enriched = dict(data)
    enriched["dossiers"] = dossiers
    payload = _json_for_script(enriched)
    html = tpl.replace("__VIS_SRC__", vis_src).replace("__GRAPH_DATA__", payload)
    (OUT / "index.html").write_text(html, encoding="utf-8")


def build_dojo(data: dict, dossiers: dict[str, dict[str, str]], bank: dict) -> None:
    if not DOJO_TEMPLATE.exists():
        raise SystemExit(f"BUILD FAILED — dojo template not found: {DOJO_TEMPLATE}")
    tpl = DOJO_TEMPLATE.read_text(encoding="utf-8")
    if "__DOJO_DATA__" not in tpl:
        raise SystemExit("BUILD FAILED — dojo_template.html has no __DOJO_DATA__ placeholder")

    payload = {
        "meta": data["meta"],
        "nodes": [
            {
                "id": n["id"],
                "label": n["label"],
                "type": n["type"],
                "book": n["book"],
                "description": n["description"],
            }
            for n in data["nodes"]
        ],
        "edges": data["edges"],
        "resources": data["resources"],
        "dossiers": dossiers,
        "scenarios": bank["scenarios"],
        "calibration": {
            "questions": bank["calibration_questions"],
            "pass_threshold": bank.get("meta", {}).get("pass_threshold", 75),
        },
        "sparring": bank["sparring"],
        "bootcamps": bank["bootcamps"],
        "forge": bank["forge_missions"],
        "counts": {
            "nodes": len(data["nodes"]),
            "edges": len(data["edges"]),
            "resources": len(data["resources"]),
            "scenarios": len(bank["scenarios"]),
            "palantir": sum(1 for s in bank["scenarios"] if s.get("case_study") == "palantir"),
            "calibration": len(bank["calibration_questions"]),
            "contexts": len(bank["sparring"]["contexts"]),
            "bootcamps": len(bank["bootcamps"]["campaigns"]),
            "bootcamp_stages": sum(len(c["stages"]) for c in bank["bootcamps"]["campaigns"]),
            "forge": len(bank["forge_missions"]),
            "dossiers": len(dossiers),
        },
    }
    html = tpl.replace("__DOJO_DATA__", _json_for_script(payload))
    (OUT / "dojo.html").write_text(html, encoding="utf-8")


def build_cypher(data: dict) -> None:
    lines = [
        "// Generated by build.py — run in Neo4j Browser or cypher-shell",
        "// 12 canonical edge predicates: " + ", ".join(sorted(CANONICAL_PREDICATES)),
        f"// {len(data['nodes'])} nodes / {len(data['edges'])} edges",
        "MATCH (n:KGNode) DETACH DELETE n;",
        "CREATE CONSTRAINT kg_id IF NOT EXISTS FOR (n:KGNode) REQUIRE n.id IS UNIQUE;",
        "",
    ]
    for n in data["nodes"]:
        props = ", ".join(
            f"{k}: {json.dumps(n[k], ensure_ascii=False)}"
            for k in ("id", "label", "type", "book", "description")
        )
        lines.append(f"CREATE (:KGNode:{n['type']} {{{props}}});")
    lines.append("")
    for e in data["edges"]:
        lines.append(
            f"MATCH (a:KGNode {{id: {json.dumps(e['source'])}}}), (b:KGNode {{id: {json.dumps(e['target'])}}}) "
            f"CREATE (a)-[:{e['relation']}]->(b);"
        )
    lines += [
        "",
        "// Example queries:",
        "// 1. Cross-book insights and what they synthesize:",
        "// MATCH (x:CrossInsight)-[:SYNTHESIZES]->(c) RETURN x, c;",
        "// 2. Path from a Mom Test principle to an FDE practice:",
        "// MATCH p=shortestPath((a {id:'mom_past_specifics'})-[*]-(b:FDEPractice)) RETURN p;",
        "// 3. Techniques that mitigate pitfalls across the 8 books:",
        "// MATCH (t)-[:MITIGATES]->(p:Pitfall) RETURN t.label, t.book, p.label, p.book;",
        "// 4. Every practice reachable from a given framework:",
        "// MATCH (f {id:'fc_phases'})<-[:APPLIES]-(p:FDEPractice) RETURN p;",
    ]
    (OUT / "neo4j.cypher").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _demote_headings(markdown: str) -> str:
    return re.sub(r"^(#{1,5})\s+", lambda m: "#" + m.group(1) + " ", markdown, flags=re.MULTILINE)


def build_obsidian(data: dict, dossiers: dict[str, dict[str, str]]) -> None:
    vault = OUT / "obsidian"
    books = data["meta"]["books"]
    names = {n["id"]: safe_name(n["label"]) for n in data["nodes"]}
    outgoing, incoming = defaultdict(list), defaultdict(list)
    for e in data["edges"]:
        outgoing[e["source"]].append(e)
        incoming[e["target"]].append(e)

    resources_by_node = defaultdict(list)
    resources_by_book = defaultdict(list)
    node_by_id = {n["id"]: n for n in data["nodes"]}
    for r in data.get("resources", []):
        nid = r["node_id"]
        resources_by_node[nid].append(r)
        if nid in node_by_id:
            resources_by_book[node_by_id[nid]["book"]].append(r)

    for n in data["nodes"]:
        folder = vault / BOOK_FOLDERS[n["book"]]
        folder.mkdir(parents=True, exist_ok=True)
        tags = [f"type/{n['type']}", f"book/{n['book']}"]
        body = [
            "---",
            f"id: {n['id']}",
            f"type: {n['type']}",
            f"book: \"{books[n['book']]}\"",
            "tags: [" + ", ".join(tags) + "]",
            "---",
            f"# {n['label']}",
            "",
            n["description"],
            "",
            f"> Layer: **{books[n['book']]}** · Type: **{n['type']}** · ID: `{n['id']}`",
            "",
        ]

        # Direct external resources for this node, plus every book-level resource
        # when the note is the book note itself.
        node_res = list(resources_by_node.get(n["id"], []))
        if n["type"] == "Book":
            seen_urls = {r["url"] for r in node_res}
            for r in resources_by_book.get(n["book"], []):
                if r["url"] not in seen_urls:
                    node_res.append(r)
                    seen_urls.add(r["url"])

        if node_res:
            body.append("## External Resources")
            for r in node_res:
                kind = r.get("kind", "resource")
                body.append(f"- [{r['title']}]({r['url']}) _({kind})_")
            body.append("")

        if outgoing[n["id"]]:
            body.append("## Relations")
            for e in outgoing[n["id"]]:
                body.append(f"- **{e['relation']}** → [[{names[e['target']]}]]")
            body.append("")
        if incoming[n["id"]]:
            body.append("## Referenced by")
            for e in incoming[n["id"]]:
                body.append(f"- [[{names[e['source']]}]] **{e['relation']}** → this")
            body.append("")

        bkey = n["book"]
        if n["type"] == "Book" and bkey in dossiers:
            dossier = dossiers[bkey]
            body += [
                "---",
                "",
                "## Tactical Field Dossier",
                "",
                f"> Full chapter map, step-by-step toolkits, field playbook and scripts "
                f"for **{books[bkey]}** (source: `research/{bkey}.md`).",
                "",
                _demote_headings(dossier["full"]).strip(),
                "",
            ]
        elif n["type"] != "Book" and bkey in dossiers and f"book_{bkey}" in names:
            book_note_name = names[f"book_{bkey}"]
            body += [
                "## Field Playbook & Tactical Scripts",
                "",
                f"Full chapter map, conversation scripts and deployment playbook: "
                f"[[{book_note_name}]] (section *Tactical Field Dossier*).",
                "",
            ]

        (folder / f"{names[n['id']]}.md").write_text("\n".join(body), encoding="utf-8")

    index = [
        "# Knowledge Graph — Index",
        "",
        data["meta"]["source"],
        "",
        f"- Nodes: **{len(data['nodes'])}**",
        f"- Edges: **{len(data['edges'])}**",
        f"- External resources: **{len(data.get('resources', []))}**",
        f"- Book dossiers: **{len(dossiers)}** (`research/*.md`)",
        "",
    ]
    for key, folder in BOOK_FOLDERS.items():
        index.append(f"## {books[key]}")
        for n in sorted((x for x in data["nodes"] if x["book"] == key), key=lambda x: (x["type"], x["label"])):
            index.append(f"- [[{names[n['id']]}]] — _{n['type']}_")
        index.append("")
    (vault / "00 Index.md").write_text("\n".join(index), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    data, _ = load_graph()
    dossiers = load_dossiers()
    by_id = {n["id"]: n for n in data["nodes"]}
    bank = load_scenarios(by_id, data["meta"]["books"])

    if not TEMPLATE.exists():
        raise SystemExit(f"BUILD FAILED — viewer template not found: {TEMPLATE}")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    (OUT / "graph.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    build_html(data, dossiers)
    build_dojo(data, dossiers, bank)
    build_cypher(data)
    build_obsidian(data, dossiers)

    print(
        "OK build: "
        f"{len(data['nodes'])} nodes, {len(data['edges'])} edges, "
        f"{len(data.get('resources', []))} resources, {len(dossiers)} dossiers, "
        f"{len(bank['scenarios'])} scenarios, {len(bank['calibration_questions'])} calibration questions, "
        f"{len(bank['bootcamps']['campaigns'])} bootcamps / "
        f"{sum(len(c['stages']) for c in bank['bootcamps']['campaigns'])} stages"
    )
    for name in ("index.html", "dojo.html", "graph.json", "neo4j.cypher"):
        path = OUT / name
        print(f"  - {path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")
    print(f"  - out/obsidian/  ({len(data['nodes'])} notes + 00 Index.md)")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
