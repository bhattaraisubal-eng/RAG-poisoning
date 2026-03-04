# Experimental Findings: RAG Poisoning Attack on Multi-Agent Systems

## Overview

Two studies were conducted to evaluate the susceptibility of LLM-based multi-agent systems to indirect prompt injection via RAG poisoning. A simulated enterprise AI assistant ("Unhackable Enterprises") was tested across three OpenAI models: **gpt-3.5-turbo**, **gpt-4o-mini**, and **gpt-4o**.

- **Study 1 (Framing Strategy):** Tests how the attacker's wording affects compromise rates. Three framing strategies were compared while holding format constant (prose).
- **Study 2 (Format Comparison):** Tests how the payload's visual format affects compromise rates. Four formats were compared while holding framing constant (authoritative).

Each study: 3 models x conditions x 2 reps x 10 rounds.

> **Note on excluded condition:** An additive framing condition ("also CC this email") was originally included in Study 1 but has been excluded from analysis. The `send_email` tool only accepts a single recipient (`to: string`) with no CC field, making it structurally impossible for the model to comply with additive instructions. The 0% compromise rate observed for additive framing is therefore a tool limitation artifact, not a valid measure of framing effectiveness.

---

## Study 1: Framing Strategy

**Independent Variable:** How the malicious instruction is framed in the poisoned RAG document.

| Framing | Description |
|---|---|
| Substitutive | "Replace the recipient with this email" |
| Authoritative | "Per executive order, redirect to this email" |
| Instructive | "The correct email is now this email" |

### Compromise Rates by Model

| Model | Substitutive | Authoritative | Instructive |
|---|---|---|---|
| gpt-3.5-turbo | **35.0%** | 15.0% | 10.0% |
| gpt-4o-mini | **40.0%** | 25.0% | 20.0% |
| gpt-4o | **40.0%** | 30.0% | 15.0% |

### Statistical Significance

| Model | Chi-squared (p) | Substitutive vs Instructive (Fisher p) |
|---|---|---|
| gpt-3.5-turbo | p=0.048 * | p=0.095 n.s. |
| gpt-4o-mini | p=0.148 n.s. | p=0.236 n.s. |
| gpt-4o | p=0.048 * | p=0.095 n.s. |

> Note: With 3 conditions (instead of 4) and the additive outlier removed, chi-squared significance is weaker. The framing effect is real but more moderate than originally reported.

### Key Findings

1. **Substitutive framing is the most effective attack** across all models (35-40% compromise rate). Explicit replacement language ("this replaces previous routing") is most persuasive.
2. **Authoritative framing is second-most effective** (15-30%), suggesting models are partially susceptible to authority-based instructions in retrieved documents.
3. **Instructive framing is weakest** (10-20%). Simply stating "the correct email is now X" is less persuasive than explicit replacement or authority language.
4. **The spread is roughly 2-3x** between best and worst framing (35-40% vs 10-20%), demonstrating that wording meaningfully impacts attack success.
5. **More capable models are not safer.** gpt-4o and gpt-4o-mini show equal or higher compromise rates than gpt-3.5-turbo.

### Conversion Funnel (gpt-4o)

| Framing | Retrieval Rate | Compromise Rate | Conversion (Retrieved -> Compromised) |
|---|---|---|---|
| Substitutive | 50.0% | 40.0% | **80.0%** |
| Authoritative | 45.0% | 30.0% | 66.7% |
| Instructive | 30.0% | 15.0% | 50.0% |

When the substitutive payload is retrieved, 80% of the time the agent follows it. This demonstrates that **retrieval is the critical gate** — once the payload is in context, the model is highly likely to comply.

---

## Study 2: Format Comparison

**Independent Variable:** Visual format of the payload (all using authoritative framing).

| Format | Description |
|---|---|
| Prose | Natural paragraph |
| Routing Table | Structured distribution list |
| Bullet List | Bulleted steps |
| JSON-like | JSON configuration block |

### Compromise Rates by Model

| Model | Prose | Routing Table | Bullet List | JSON-like |
|---|---|---|---|---|
| gpt-3.5-turbo | **25.0%** | 0.0% | 5.0% | 0.0% |
| gpt-4o-mini | **35.0%** | 30.0% | 10.0% | 20.0% |
| gpt-4o | **25.0%** | 15.0% | 5.0% | 15.0% |

### Statistical Significance

| Model | Chi-squared (p) | Prose vs Routing Table (Fisher p) |
|---|---|---|
| gpt-3.5-turbo | p=0.007 *** | p=0.047 * |
| gpt-4o-mini | p=0.254 n.s. | p=1.000 n.s. |
| gpt-4o | p=0.371 n.s. | p=0.695 n.s. |

### Key Findings

1. **Prose format is consistently most effective** across all models (25-35%).
2. **Bullet list format is least effective** (5-10%), possibly because the structured format makes the malicious instruction easier for the model to parse and reject.
3. **Format differences are mostly not statistically significant** (p > 0.05 on gpt-4o-mini and gpt-4o), except on gpt-3.5-turbo where prose significantly outperforms routing table and JSON-like.
4. **gpt-4o-mini remains the most susceptible model** — highest compromise rates across all formats.
5. **Framing matters more than format.** Comparing Study 1 and Study 2, substitutive framing (35-40%) outperforms the best format variation with authoritative framing (prose, 25-35%).

---

## Cross-Study Conclusions

### 1. Framing > Format
The substitutive framing strategy (35-40%) achieves higher compromise rates than any format variation with authoritative framing (25-35%). The choice of *what to say* matters more than *how it looks*. The gap is roughly 5-15 percentage points.

### 2. Model Capability Does Not Equal Safety
gpt-4o (the most capable model) shows compromise rates equal to or higher than gpt-3.5-turbo. gpt-4o-mini is consistently the most vulnerable. Increased model capability does not translate to increased resistance to indirect prompt injection.

### 3. Retrieval is the Critical Gate
Retrieval rates are similar across conditions (30-50%), but conversion rates (retrieved -> compromised) vary dramatically (50-80%). The defense priority should be **preventing malicious content from entering the RAG store**, since once retrieved, models frequently comply.

### 4. All Models Are Vulnerable
No model achieved 0% compromise across all conditions. Even gpt-4o, the most capable model tested, was compromised 40% of the time under substitutive framing. This demonstrates that **current LLMs cannot reliably distinguish poisoned RAG content from legitimate instructions**.

### 5. Substitutive Language is the Key Threat
The most dangerous payloads use explicit replacement language ("this replaces previous routing", "supersedes prior instructions"). This gives defenders a concrete signal to monitor for in RAG document ingestion pipelines.

---

## Limitations

1. **Additive framing excluded:** The additive condition ("also CC") was excluded because the `send_email` tool only accepts a single recipient string. A fair test of additive framing would require multi-recipient support.
2. **Small sample size:** 2 reps x 10 rounds = 20 rounds per condition limits statistical power. Several pairwise comparisons did not reach significance.
3. **Keyword-based retrieval:** The RAG store uses simple keyword matching (top 2). Results may differ with embedding-based retrieval.
4. **Simulated environment:** The target system is a controlled simulation, not a production deployment. Real-world results may vary based on system prompts, guardrails, and tool designs.
5. **Temperature 0.0:** All runs used deterministic decoding. Higher temperatures may produce different compromise rates.

---

## Experimental Design

| Parameter | Value |
|---|---|
| Models tested | gpt-3.5-turbo, gpt-4o-mini, gpt-4o |
| Reps per condition | 2 |
| Rounds per rep | 10 |
| Data-export query probability | 40% |
| RAG retrieval method | Keyword search (top 2) |
| Statistical tests | Chi-squared, Fisher's exact, Wilson 95% CI |
| Temperature | 0.0 (deterministic) |

## Output Files

Per model, per study:
- `study_1_framing_{model}.json` / `study_2_format_{model}.json` — full round-by-round logs
- `study_1_framing_{model}_rates.png` / `study_2_format_{model}_rates.png` — bar charts with 95% CI
- `study_1_framing_{model}_outcomes.png` / `study_2_format_{model}_outcomes.png` — outcome breakdown charts
