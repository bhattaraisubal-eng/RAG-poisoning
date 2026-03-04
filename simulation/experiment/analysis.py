"""
analysis.py — Statistical analysis and visualization for experiment results.

- Chi-squared / Fisher's exact test on conversion rates
- Bar charts with 95% CI error bars
- Heatmaps (per-round outcome)
- Summary table printed to console
"""

import json
import math
from pathlib import Path

from experiment.paths import OUTPUT_DIR

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (95% CI)."""
    if trials == 0:
        return (0.0, 0.0)
    p = successes / trials
    denom = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denom
    spread = z * math.sqrt((p * (1 - p) + z**2 / (4 * trials)) / trials) / denom
    return (max(0, center - spread), min(1, center + spread))


def chi_squared_test(counts: dict[str, dict]) -> dict:
    """Run chi-squared test across conditions.

    Args:
        counts: {condition_name: {"successes": n, "trials": n}}

    Returns:
        dict with chi2 statistic, p_value, and interpretation.
    """
    if not HAS_SCIPY:
        return {"error": "scipy not installed — skipping chi-squared test"}

    conditions = list(counts.keys())
    observed = []
    for c in conditions:
        s = counts[c]["successes"]
        t = counts[c]["trials"]
        observed.append([s, t - s])

    if len(observed) < 2:
        return {"error": "Need at least 2 conditions for chi-squared test"}

    try:
        chi2, p, dof, expected = scipy_stats.chi2_contingency(observed)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "test": "chi-squared",
        "chi2": round(chi2, 4),
        "p_value": round(p, 6),
        "dof": dof,
        "significant_005": p < 0.05,
        "significant_001": p < 0.01,
    }


def fisher_exact_test(a_successes: int, a_trials: int,
                      b_successes: int, b_trials: int) -> dict:
    """Fisher's exact test for 2x2 contingency table."""
    if not HAS_SCIPY:
        return {"error": "scipy not installed — skipping Fisher's exact test"}

    table = [
        [a_successes, a_trials - a_successes],
        [b_successes, b_trials - b_successes],
    ]

    try:
        result = scipy_stats.fisher_exact(table)
        # scipy returns (odds_ratio, p_value) — handle both old and new API
        if hasattr(result, 'pvalue'):
            odds_ratio = result.statistic
            p_value = result.pvalue
        else:
            odds_ratio, p_value = result
    except ValueError as e:
        return {"error": str(e)}

    return {
        "test": "fisher_exact",
        "odds_ratio": round(odds_ratio, 4),
        "p_value": round(p_value, 6),
        "significant_005": p_value < 0.05,
        "significant_001": p_value < 0.01,
    }


# ---------------------------------------------------------------------------
# Analysis driver
# ---------------------------------------------------------------------------

def analyze_study(study_result: dict, output_prefix: str | None = None) -> dict:
    """Run full analysis on a study result dict.

    Args:
        study_result: Output from runner.run_study().
        output_prefix: Prefix for saved PNGs. None = don't save charts.

    Returns:
        dict with statistical test results and summary.
    """
    summaries = study_result["condition_summaries"]
    all_rounds = study_result["all_rounds"]
    conditions = list(summaries.keys())

    analysis = {"study": study_result["study_name"], "conditions": {}}

    # Per-condition stats with CIs
    for name, s in summaries.items():
        counts = s["counts"]
        retr_ci = wilson_ci(counts["retrieved"], counts["total"])
        comp_ci = wilson_ci(counts["compromised"], counts["total"])
        inj_ci = wilson_ci(counts["injection"], counts["total"])
        conv_successes = counts["compromised"]
        conv_trials = counts["retrieved"]
        conv_ci = wilson_ci(conv_successes, conv_trials)

        analysis["conditions"][name] = {
            **s,
            "retrieval_ci": retr_ci,
            "compromise_ci": comp_ci,
            "injection_ci": inj_ci,
            "conversion_ci": conv_ci,
        }

    # Chi-squared on injection rates
    inj_counts = {
        name: {"successes": s["counts"]["injection"], "trials": s["counts"]["total"]}
        for name, s in summaries.items()
    }
    analysis["chi_squared_injection"] = chi_squared_test(inj_counts)

    # Chi-squared on compromise rates
    comp_counts = {
        name: {"successes": s["counts"]["compromised"], "trials": s["counts"]["total"]}
        for name, s in summaries.items()
    }
    analysis["chi_squared_compromise"] = chi_squared_test(comp_counts)

    # Pairwise Fisher's exact tests (each condition vs first condition)
    if len(conditions) >= 2:
        baseline = conditions[0]
        analysis["pairwise_fisher"] = {}
        for other in conditions[1:]:
            key = f"{baseline}_vs_{other}"
            analysis["pairwise_fisher"][key] = fisher_exact_test(
                summaries[baseline]["counts"]["compromised"],
                summaries[baseline]["counts"]["total"],
                summaries[other]["counts"]["compromised"],
                summaries[other]["counts"]["total"],
            )

    # Print analysis
    _print_analysis(analysis)

    # Charts
    if output_prefix and HAS_MATPLOTLIB:
        rates_path = str(OUTPUT_DIR / f"{output_prefix}_rates.png")
        outcomes_path = str(OUTPUT_DIR / f"{output_prefix}_outcomes.png")
        _plot_bar_chart(analysis, rates_path)
        _plot_outcome_breakdown(all_rounds, conditions, analysis, outcomes_path)
        print(f"\n  Charts saved: {rates_path}, {outcomes_path}")

    return analysis


def _print_analysis(analysis: dict):
    """Print statistical analysis to console."""
    print(f"\n{'='*70}")
    print(f"  STATISTICAL ANALYSIS: {analysis['study']}")
    print(f"{'='*70}")

    for name, c in analysis["conditions"].items():
        print(f"\n  {name}:")
        print(f"    Retrieval:  {c['retrieval_rate']:6.1%}  "
              f"95% CI [{c['retrieval_ci'][0]:.1%}, {c['retrieval_ci'][1]:.1%}]")
        print(f"    Compromise: {c['compromise_rate']:6.1%}  "
              f"95% CI [{c['compromise_ci'][0]:.1%}, {c['compromise_ci'][1]:.1%}]")
        print(f"    Injection:  {c['injection_rate']:6.1%}  "
              f"95% CI [{c['injection_ci'][0]:.1%}, {c['injection_ci'][1]:.1%}]")
        print(f"    Conversion: {c['conversion_rate']:6.1%}  "
              f"95% CI [{c['conversion_ci'][0]:.1%}, {c['conversion_ci'][1]:.1%}]")

    chi2_inj = analysis.get("chi_squared_injection", {})
    if "chi2" in chi2_inj:
        sig = "***" if chi2_inj["significant_001"] else ("*" if chi2_inj["significant_005"] else "n.s.")
        print(f"\n  Chi-squared (injection): X2={chi2_inj['chi2']}, "
              f"p={chi2_inj['p_value']:.6f} {sig}")

    chi2_comp = analysis.get("chi_squared_compromise", {})
    if "chi2" in chi2_comp:
        sig = "***" if chi2_comp["significant_001"] else ("*" if chi2_comp["significant_005"] else "n.s.")
        print(f"  Chi-squared (compromise): X2={chi2_comp['chi2']}, "
              f"p={chi2_comp['p_value']:.6f} {sig}")

    for key, result in analysis.get("pairwise_fisher", {}).items():
        if "odds_ratio" in result:
            sig = "***" if result["significant_001"] else ("*" if result["significant_005"] else "n.s.")
            print(f"  Fisher ({key}): OR={result['odds_ratio']}, "
                  f"p={result['p_value']:.6f} {sig}")

    print(f"{'='*70}\n")


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _plot_bar_chart(analysis: dict, filename: str):
    """Bar chart of key rates with 95% CI error bars."""
    conditions = list(analysis["conditions"].keys())
    metrics = ["retrieval_rate", "compromise_rate", "injection_rate", "conversion_rate"]
    labels = ["Retrieval", "Compromise", "Injection", "Conversion"]

    fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 5))
    if len(metrics) == 1:
        axes = [axes]

    colors = plt.cm.Set2(range(len(conditions)))

    for ax, metric, label in zip(axes, metrics, labels):
        vals = []
        errs_low = []
        errs_high = []
        for name in conditions:
            c = analysis["conditions"][name]
            v = c[metric]
            ci = c.get(f"{metric.replace('_rate', '_ci')}", (v, v))
            vals.append(v)
            errs_low.append(v - ci[0])
            errs_high.append(ci[1] - v)

        x = range(len(conditions))
        bars = ax.bar(x, vals, color=colors[:len(conditions)],
                      yerr=[errs_low, errs_high], capsize=5, edgecolor="black", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(conditions, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Rate")
        ax.set_title(label)
        ax.set_ylim(0, 1.05)
        ax.axhline(y=0, color="black", linewidth=0.5)

    fig.suptitle(f"Study: {analysis['study']}", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()


def _plot_outcome_breakdown(all_rounds: list[dict], conditions: list[str],
                            analysis: dict, filename: str):
    """Stacked horizontal bar chart showing outcome breakdown per condition.

    Each bar represents one condition, with segments for:
      Safe | Retrieved only | Compromised (hallucination) | Compromised (injection)
    Percentages are labeled inside segments when large enough.
    """
    from matplotlib.patches import Patch

    categories = ["safe", "retrieved", "hallucination", "injection"]
    cat_labels = ["Safe", "Retrieved only", "Compromised (halluc.)", "Compromised (injection)"]
    colors = {
        "safe":          "#4CAF50",
        "retrieved":     "#FFC107",
        "hallucination": "#FF9800",
        "injection":     "#F44336",
    }

    # Classify each round
    condition_counts = {}
    for cond in conditions:
        condition_counts[cond] = {c: 0 for c in categories}

    for r in all_rounds:
        cond = r["condition"]
        if r["compromised"] and r.get("compromise_cause") == "rag_injection":
            condition_counts[cond]["injection"] += 1
        elif r["compromised"]:
            condition_counts[cond]["hallucination"] += 1
        elif r["payload_retrieved"]:
            condition_counts[cond]["retrieved"] += 1
        else:
            condition_counts[cond]["safe"] += 1

    fig, ax = plt.subplots(figsize=(10, max(3, len(conditions) * 0.9 + 1.5)))

    y_pos = range(len(conditions))

    for i, cond in enumerate(conditions):
        total = sum(condition_counts[cond].values())
        if total == 0:
            continue
        left = 0
        for cat in categories:
            count = condition_counts[cond][cat]
            width = count / total
            bar = ax.barh(i, width, left=left, height=0.6,
                          color=colors[cat], edgecolor="white", linewidth=0.8)
            if width >= 0.10:
                ax.text(left + width / 2, i, f"{width:.0%}",
                        ha="center", va="center", fontsize=8, fontweight="bold",
                        color="white" if cat in ("injection", "hallucination") else "#333")
            left += width

    ax.set_yticks(y_pos)
    ax.set_yticklabels(conditions, fontsize=10)
    ax.set_xlabel("Proportion of Rounds", fontsize=10)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_elements = [
        Patch(facecolor=colors[c], edgecolor="gray", label=l)
        for c, l in zip(categories, cat_labels)
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8, frameon=True)

    study_name = analysis.get("study", "")
    ax.set_title(f"{study_name} — Outcome Breakdown", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
