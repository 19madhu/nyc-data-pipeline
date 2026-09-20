# SLA-Breach Prediction Model

## Goal
Predict whether a newly-created NYC 311 complaint is likely to breach its
SLA (defined as taking longer than the 90th percentile resolution time for
its complaint type) — before the outcome is known, enabling early
prioritization rather than only detecting breaches after the fact (which
is what the existing `open_complaints_at_risk` dbt model does).

## Data leakage avoidance
Only features genuinely available at complaint-creation time are used:
`complaint_type`, `borough`, and time-derived features (hour of day, day
of week) from `created_date`. Fields like `closed_date`, `resolution_hours`,
and `status` are deliberately excluded — they either don't exist yet at
prediction time or directly leak the answer.

## Model
RandomForestClassifier (200 trees, max depth 10), trained on 26,863 closed
complaints (80/20 stratified train/test split), with `class_weight="balanced"`
to account for the 9.4% base breach rate.

## Results (honest evaluation)
- Breach recall: 0.64 — catches roughly 2 out of 3 actual breaches
- Breach precision: 0.15 — roughly 6 out of 7 flagged complaints are false alarms
- Accuracy (0.64) is intentionally not used as the headline metric, since
  a model that always predicts "No Breach" would score ~90% accuracy while
  being useless — precision/recall on the minority class is the honest measure.

## Threshold analysis
Precision/recall was evaluated across thresholds from 0.2 to 0.7. The
tradeoff is not smooth: precision stays low (~0.09–0.15) until 0.5, then
jumps sharply while recall collapses. This "cliff" shape indicates the
model isn't confidently separating the two classes — most predicted
probabilities cluster in a narrow middle range rather than spreading out.
**Conclusion: threshold tuning cannot meaningfully improve this model —
the limiting factor is feature quality, not calibration.** The default
0.5 threshold was kept.

## Honest assessment
This is a legitimate first-pass baseline, not a production-ready model.
With only four fairly coarse features, this level of performance is
expected, not surprising. Real improvement would require features not
currently available in this pipeline: agency-level current workload,
complaint description text (via NLP), seasonal/weather effects, or the
number of similar complaints already queued at creation time.

## Next steps (not yet implemented)
- Add agency backlog size at time of complaint creation as a feature
- Try gradient boosting (XGBoost/LightGBM) instead of Random Forest
- Incorporate complaint description text via basic NLP (TF-IDF or embeddings)
- Re-evaluate with a larger, more diverse training window (currently ~1 week of data)