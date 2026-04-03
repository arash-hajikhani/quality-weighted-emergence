"""
Quality-Weighted Emergence Analysis
====================================
Detects genuine technological emergence in bibliometric data by controlling
for venue quality, content inflation, and domain trajectory.

Accompanies Chapter 15 of "Applied Quantitative Methods in Technology Foresight"
(Springer Nature, 2026).

Author: Arash Hajikhani
        VTT Technical Research Centre of Finland / LUT University
        arash.hajikhani@vtt.fi

Usage:
    python emergence_analysis.py

Input files (place in data/ directory):
    - openalex_works.csv: Publications exported from OpenAlex
    - journal_ranking_data.csv: Journal rankings from Scopus/SJR

Output:
    - Console tables with all metrics
    - results.json with structured output
"""

import csv
import json
import os
from collections import defaultdict

# ============================================================
# CONFIGURATION
# ============================================================

# File paths (adjust as needed)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WORKS_CSV = os.path.join(DATA_DIR, "openalex_quantum_algorithms_2020_2026.csv")
RANKINGS_CSV = os.path.join(DATA_DIR, "scopus_journal_rankings.csv")
OUTPUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")

# Venue quality weights by CiteScore quartile
QUARTILE_WEIGHTS = {
    "Q1": 1.0,
    "Q2": 0.70,
    "Q3": 0.40,
    "Q4": 0.20,
    "unranked": 0.15
}

# Default weights by source type (when no quartile match is found)
TYPE_DEFAULT_WEIGHTS = {
    "journal": 0.70,
    "conference": 0.50,
    "repository": 0.15,
    "book series": 0.60,
    "ebook platform": 0.40,
    "other": 0.15,
    "unknown": 0.15
}

# Sub-topic keyword patterns
SUBTOPIC_DEFINITIONS = {
    "quantum_error_correction": [
        "error correct", "error-correct", "surface code", "stabilizer code",
        "topological code", "quantum error", "code distance", "decoder",
        "syndrome", "logical error"
    ],
    "fault_tolerant_qc": [
        "fault-tolerant", "fault tolerant", "ftqc", "threshold theorem",
        "magic state", "logical qubit", "t-gate", "early fault",
        "resource estimation", "quantum advantage"
    ]
}

# Emergence indicator comparison window
DELTA = 2


# ============================================================
# 1. LOAD JOURNAL RANKINGS
# ============================================================
def load_journal_rankings(filepath):
    """Load journal ranking data from Scopus/SJR CSV export."""
    rankings = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("Title", "").strip()
            if not title:
                continue
            quartile = row.get("Best Quartile", "").strip()
            citescore = row.get("CiteScore", "").strip()
            sjr = row.get("SJR-index", "").strip()
            hindex = row.get("H-index", "").strip()
            rankings[title.lower()] = {
                "quartile": quartile if quartile else "unranked",
                "citescore": float(citescore) if citescore else 0,
                "sjr": float(sjr) if sjr else 0,
                "hindex": int(hindex) if hindex else 0
            }
    return rankings


# ============================================================
# 2. LOAD OPENALEX WORKS
# ============================================================
def load_works(filepath):
    """Load and parse OpenAlex publications CSV export."""
    works = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            work = {
                "title": row.get("display_name", ""),
                "year": int(row["publication_year"]) if row.get("publication_year") else None,
                "venue": row.get("primary_location.source.display_name", ""),
                "venue_type": row.get("primary_location.source.type", ""),
                "issn": row.get("primary_location.source.issn_l", ""),
                "cited_by": int(row["cited_by_count"]) if row.get("cited_by_count") else 0,
                "fwci": float(row["fwci"]) if row.get("fwci") and row["fwci"] else None,
                "topic": row.get("primary_topic.display_name", ""),
                "is_retracted": row.get("is_retracted", "False") == "True",
                "oa_status": row.get("open_access.oa_status", ""),
            }
            works.append(work)

    # Remove retracted papers
    works = [w for w in works if not w["is_retracted"]]
    return works


# ============================================================
# 3. MATCH VENUES TO RANKINGS
# ============================================================
def match_venues_to_rankings(works, journal_rankings):
    """Match each venue to its journal ranking via title matching."""
    venue_quartile_map = {}
    venue_names = set(w["venue"] for w in works if w["venue"])

    for venue_name in venue_names:
        vname_lower = venue_name.lower().strip()
        quartile = "unranked"
        citescore = 0

        # Direct match
        if vname_lower in journal_rankings:
            quartile = journal_rankings[vname_lower]["quartile"]
            citescore = journal_rankings[vname_lower]["citescore"]
        else:
            # Fuzzy match via substring and keyword overlap
            for jname, jdata in journal_rankings.items():
                if vname_lower in jname or jname in vname_lower:
                    quartile = jdata["quartile"]
                    citescore = jdata["citescore"]
                    break
                vwords = set(vname_lower.split()) - {"the", "of", "and", "in", "for", "a", "an"}
                jwords = set(jname.split()) - {"the", "of", "and", "in", "for", "a", "an"}
                if (len(vwords) >= 2
                        and len(vwords & jwords) >= 2
                        and len(vwords & jwords) / max(len(vwords), 1) > 0.5):
                    quartile = jdata["quartile"]
                    citescore = jdata["citescore"]
                    break

        venue_quartile_map[venue_name] = {"quartile": quartile, "citescore": citescore}

    return venue_quartile_map


# ============================================================
# 4. QUALITY WEIGHT ASSIGNMENT
# ============================================================
def get_quality_weight(work, venue_quartile_map):
    """Get quality weight for a single work based on venue ranking."""
    venue = work["venue"]
    vtype = work["venue_type"] if work["venue_type"] else "unknown"

    if venue and venue in venue_quartile_map:
        q = venue_quartile_map[venue]["quartile"]
        if q in QUARTILE_WEIGHTS:
            return QUARTILE_WEIGHTS[q]

    return TYPE_DEFAULT_WEIGHTS.get(vtype, 0.15)


# ============================================================
# 5. SUB-TOPIC CLASSIFICATION
# ============================================================
def matches_subtopic(work, patterns):
    """Check if work title or topic matches any keyword pattern."""
    text = (work["title"] + " " + work["topic"]).lower()
    return any(p in text for p in patterns)


# ============================================================
# 6. NORMALIZED EMERGENCE INDICATOR
# ============================================================
def compute_emergence(term_vw, baseline_vw, years, delta):
    """
    Compute normalized emergence indicator E(t,y).

    E(t,y) = [Cvw(t,y) / Cvw(t,y-delta)] / [B(y) / B(y-delta)]

    Where:
        Cvw = venue-weighted count for sub-topic
        B   = venue-weighted count for domain baseline
        E > 1.0 = sub-topic growing faster than domain
        E ~ 1.0 = tracking domain growth
        E < 1.0 = relative decline
    """
    results = {}
    for y in years:
        y_prev = y - delta
        if (y_prev in term_vw and term_vw[y_prev] > 0
                and baseline_vw.get(y_prev, 0) > 0):
            term_growth = term_vw[y] / term_vw[y_prev]
            base_growth = baseline_vw[y] / baseline_vw[y_prev]
            E = term_growth / base_growth if base_growth > 0 else None
            results[y] = round(E, 3) if E else None
        else:
            results[y] = None
    return results


# ============================================================
# MAIN ANALYSIS PIPELINE
# ============================================================
def main():
    print("=" * 80)
    print("QUALITY-WEIGHTED EMERGENCE ANALYSIS")
    print("=" * 80)

    # --- Load data ---
    print("\n[1/6] Loading journal ranking data...")
    journal_rankings = load_journal_rankings(RANKINGS_CSV)
    print(f"       Loaded {len(journal_rankings)} journal rankings")

    print("[2/6] Loading OpenAlex works data...")
    works = load_works(WORKS_CSV)
    print(f"       Loaded {len(works)} works (retracted removed)")

    # Determine year range from data
    valid_years = sorted(set(w["year"] for w in works if w["year"]))
    years = [y for y in valid_years if y >= min(valid_years)]
    print(f"       Year range: {min(years)}-{max(years)}")

    # --- Match venues ---
    print("[3/6] Matching venues to journal rankings...")
    venue_quartile_map = match_venues_to_rankings(works, journal_rankings)
    matched = sum(1 for v in venue_quartile_map.values() if v["quartile"] != "unranked")
    print(f"       Matched {matched}/{len(venue_quartile_map)} venues to rankings")

    # --- Classify and count ---
    print("[4/6] Classifying works and computing counts...")

    baseline_raw = defaultdict(int)
    baseline_vw = defaultdict(float)
    weight_sum = defaultdict(float)
    weight_count = defaultdict(int)
    subtopic_raw = {name: defaultdict(int) for name in SUBTOPIC_DEFINITIONS}
    subtopic_vw = {name: defaultdict(float) for name in SUBTOPIC_DEFINITIONS}
    venue_type_counts = defaultdict(int)
    quartile_by_year = defaultdict(lambda: defaultdict(int))

    for w in works:
        y = w["year"]
        if y not in years:
            continue

        wt = get_quality_weight(w, venue_quartile_map)
        baseline_raw[y] += 1
        baseline_vw[y] += wt
        weight_sum[y] += wt
        weight_count[y] += 1

        vtype = w["venue_type"] if w["venue_type"] else "unknown"
        venue_type_counts[vtype] += 1

        venue = w["venue"]
        q = venue_quartile_map[venue]["quartile"] if venue and venue in venue_quartile_map else "unranked"
        quartile_by_year[y][q] += 1

        for subtopic_name, patterns in SUBTOPIC_DEFINITIONS.items():
            if matches_subtopic(w, patterns):
                subtopic_raw[subtopic_name][y] += 1
                subtopic_vw[subtopic_name][y] += wt

    # --- Compute emergence ---
    print("[5/6] Computing normalized emergence indicators...")

    emergence_vw = {}
    emergence_raw = {}
    for name in SUBTOPIC_DEFINITIONS:
        emergence_vw[name] = compute_emergence(dict(subtopic_vw[name]), dict(baseline_vw), years, DELTA)
        emergence_raw[name] = compute_emergence(
            {y: float(subtopic_raw[name][y]) for y in years},
            {y: float(baseline_raw[y]) for y in years},
            years, DELTA
        )

    # --- Print results ---
    print("[6/6] Generating report...\n")

    # Table 1: Raw counts
    print("=" * 80)
    print("TABLE 1: RAW PUBLICATION COUNTS")
    print("=" * 80)
    header = f"{'Year':>6} {'Baseline':>10}"
    for name in SUBTOPIC_DEFINITIONS:
        header += f" {name[:20]:>22}"
    print(header)
    for y in years:
        line = f"{y:>6} {baseline_raw[y]:>10}"
        for name in SUBTOPIC_DEFINITIONS:
            line += f" {subtopic_raw[name][y]:>22}"
        print(line)
    total_base = sum(baseline_raw[y] for y in years)
    totals = f"{'TOTAL':>6} {total_base:>10}"
    for name in SUBTOPIC_DEFINITIONS:
        totals += f" {sum(subtopic_raw[name][y] for y in years):>22}"
    print(totals)

    # Table 2: Venue-weighted counts
    print(f"\n{'=' * 80}")
    print("TABLE 2: VENUE-WEIGHTED COUNTS")
    print("=" * 80)
    print(f"{'Year':>6} {'Raw':>8} {'Weighted':>10} {'Avg wt':>8}", end="")
    for name in SUBTOPIC_DEFINITIONS:
        short = name[:12]
        print(f" {short+' raw':>14} {short+' vw':>14}", end="")
    print()
    for y in years:
        avg_wt = weight_sum[y] / weight_count[y] if weight_count[y] > 0 else 0
        print(f"{y:>6} {baseline_raw[y]:>8} {baseline_vw[y]:>10.1f} {avg_wt:>8.3f}", end="")
        for name in SUBTOPIC_DEFINITIONS:
            print(f" {subtopic_raw[name][y]:>14} {subtopic_vw[name][y]:>14.1f}", end="")
        print()

    # Table 3: Emergence indicators
    print(f"\n{'=' * 80}")
    print(f"TABLE 3: NORMALIZED EMERGENCE INDICATORS E(t,y), delta={DELTA}")
    print("=" * 80)
    print("E > 1.0 -> sub-topic growing faster than domain (genuine emergence)")
    print("E ~ 1.0 -> tracking domain growth (maturation)")
    print("E < 1.0 -> relative decline\n")
    header = f"{'Year':>6}"
    for name in SUBTOPIC_DEFINITIONS:
        short = name[:15]
        header += f" {short+' E(vw)':>18} {short+' E(raw)':>18}"
    print(header)
    for y in years:
        line = f"{y:>6}"
        for name in SUBTOPIC_DEFINITIONS:
            e_vw = f"{emergence_vw[name][y]:.3f}" if emergence_vw[name].get(y) else "-"
            e_raw = f"{emergence_raw[name][y]:.3f}" if emergence_raw[name].get(y) else "-"
            line += f" {e_vw:>18} {e_raw:>18}"
        print(line)

    # Table 4: Venue quality drift
    print(f"\n{'=' * 80}")
    print("TABLE 4: VENUE QUALITY DRIFT")
    print("=" * 80)
    print(f"{'Year':>6} {'Avg weight':>11} {'Q1 share':>10}")
    for y in years:
        avg_wt = weight_sum[y] / weight_count[y] if weight_count[y] > 0 else 0
        qd = quartile_by_year[y]
        total_y = sum(qd.values())
        q1_pct = 100 * qd.get("Q1", 0) / total_y if total_y > 0 else 0
        bar = "█" * int(avg_wt * 60)
        print(f"{y:>6} {avg_wt:>11.3f} {q1_pct:>9.1f}% {bar}")

    # Source type distribution
    print(f"\n{'=' * 80}")
    print("TABLE 5: SOURCE TYPE DISTRIBUTION")
    print("=" * 80)
    total_typed = sum(venue_type_counts.values())
    for vtype, count in sorted(venue_type_counts.items(), key=lambda x: -x[1]):
        pct = 100 * count / total_typed
        print(f"  {vtype:<20} {count:>8} ({pct:>5.1f}%)")

    # Key findings
    print(f"\n{'=' * 80}")
    print("KEY FINDINGS")
    print("=" * 80)
    print(f"\nDataset: {total_base:,} works, {min(years)}-{max(years)}")
    for name in SUBTOPIC_DEFINITIONS:
        total_sub = sum(subtopic_raw[name][y] for y in years)
        print(f"  {name}: {total_sub} works ({100*total_sub/total_base:.1f}%)")

    early_years = years[:2]
    late_years = years[-3:]
    if early_years and late_years:
        early_wt = sum(weight_sum[y] for y in early_years) / sum(weight_count[y] for y in early_years)
        late_wt = sum(weight_sum[y] for y in late_years) / sum(weight_count[y] for y in late_years)
        print(f"\nVenue quality drift: {early_wt:.3f} -> {late_wt:.3f} ({(late_wt-early_wt)/early_wt*100:+.1f}%)")

    # --- Save results ---
    results = {
        "data_source": "OpenAlex + Scopus/SJR journal rankings",
        "total_works": total_base,
        "year_range": f"{min(years)}-{max(years)}",
        "config": {
            "delta": DELTA,
            "quartile_weights": QUARTILE_WEIGHTS,
            "subtopic_definitions": SUBTOPIC_DEFINITIONS
        },
        "raw_counts": {str(y): {
            "baseline": baseline_raw[y],
            **{name: subtopic_raw[name][y] for name in SUBTOPIC_DEFINITIONS}
        } for y in years},
        "venue_weighted": {str(y): {
            "baseline": round(baseline_vw[y], 1),
            **{name: round(subtopic_vw[name][y], 1) for name in SUBTOPIC_DEFINITIONS}
        } for y in years},
        "emergence_venue_weighted": {name: {str(y): emergence_vw[name].get(y) for y in years} for name in SUBTOPIC_DEFINITIONS},
        "emergence_raw": {name: {str(y): emergence_raw[name].get(y) for y in years} for name in SUBTOPIC_DEFINITIONS},
        "avg_quality_weight": {str(y): round(weight_sum[y]/weight_count[y], 3) if weight_count[y] > 0 else 0 for y in years},
        "source_types": dict(venue_type_counts),
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {OUTPUT_JSON}")
    print("DONE.")


if __name__ == "__main__":
    main()
