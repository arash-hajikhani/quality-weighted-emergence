# Quality-Weighted Emergence Analysis

A Python-based evaluation pipeline for detecting genuine technological emergence in bibliometric data, controlling for venue quality, content inflation, and domain trajectory.

## Overview

This repository accompanies **Chapter 15** of *Applied Quantitative Methods in Technology Foresight* (Springer), which argues that frequency-based emergence detection is no longer sufficient in an era of AI-driven content inflation. The code implements a quality-weighted, complexity-normalized framework that separates genuine emergence signals from noise.

## What It Does

Given a dataset of scientific publications (from OpenAlex) and journal quality rankings (from Scopus/SJR), the pipeline:

1. **Counts publications by year** for a domain and its sub-topics
2. **Matches venues to quality rankings** (CiteScore quartile: Q1=1.0, Q2=0.7, Q3=0.4, Q4=0.2, unranked=0.15)
3. **Computes venue-weighted counts** that discount publications in low-quality venues
4. **Calculates normalized emergence indicators** E(t,y) that measure whether a sub-topic grows faster than its domain baseline
5. **Compares raw vs. quality-weighted signals** to reveal how content inflation distorts naive frequency analysis

## Key Formula

```
E(t, y) = [Cvw(t,y) / Cvw(t,y-delta)] / [B(y) / B(y-delta)]
```

Where:
- `Cvw(t,y)` = venue-weighted publication count for sub-topic `t` in year `y`
- `B(y)` = venue-weighted count for the domain baseline
- `delta` = comparison window (default: 2 years)
- `E > 1.0` = sub-topic growing faster than domain (genuine emergence)
- `E ~ 1.0` = tracking domain growth
- `E < 1.0` = relative decline

## Case Study: Quantum Algorithms (2020-2026)

Applied to 13,695 quantum algorithms publications from OpenAlex, matched against 18,013 Scopus journal rankings, the analysis reveals:

- **43.1% of publications** are in repositories (mainly arXiv), only 36.2% in peer-reviewed journals
- **Fault-tolerant QC** showed genuine emergence (E=1.54 in 2023), then matured toward E~1.0
- **Quantum error correction** spiked (E=2.34 in 2022), corrected, then stabilized
- **Raw counts overstate emergence** because the 43% repository share inflates volume while contributing minimally to quality-weighted signals

## Files

| File | Description |
|------|-------------|
| `emergence_analysis.py` | Main analysis pipeline |
| `data/` | Place your OpenAlex CSV and journal ranking CSV here |

## Data Requirements

### OpenAlex Publications CSV
Export from [OpenAlex](https://openalex.org/) with columns including:
- `display_name` (paper title)
- `publication_year`
- `primary_location.source.display_name` (venue name)
- `primary_location.source.type` (journal, repository, etc.)
- `cited_by_count`, `fwci`
- `primary_topic.display_name`
- `is_retracted`

### Journal Rankings CSV
Export from [Scimago/Scopus](https://www.scimagojr.com/) with columns including:
- `Title` (journal name)
- `Best Quartile` (Q1-Q4)
- `CiteScore`
- `SJR-index`
- `H-index`

## Usage

```bash
python emergence_analysis.py
```

Results are printed to stdout and saved to `results.json`.

## Citation

If you use this code, please cite:

> Hajikhani, A. (2026). Signal in the Noise: AI-Enhanced Evaluation of Quantitative Technology Foresight in an Era of Content Inflation. In *Applied Quantitative Methods in Technology Foresight: AI-Enhanced Approaches*. Springer Nature.

## License

MIT License

## Author

**Arash Hajikhani**
VTT Technical Research Centre of Finland / LUT University
