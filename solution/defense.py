"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
import sys
from api import Verdict


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    batch_id = payload.get("batch_id")
    res = ctx.tools.batch_profile(batch_id)

    if "error" in res:
        return Verdict(alert=False, pillar="checks")

    b = ctx.baseline
    row_count = res.get("row_count", 0)
    null_rate = res.get("null_rate", {}).get("customer_id", 0.0)
    mean_amount = res.get("mean_amount", 0.0)
    staleness_min = res.get("staleness_min", 0.0)

    alert = False
    reasons = []

    if row_count < b.get("row_count_min", 435.4732) or row_count > b.get("row_count_max", 561.2948):
        alert = True
        reasons.append("row_count")
    if null_rate > b.get("null_rate_max", 0.0109):
        alert = True
        reasons.append("null_rate")
    if mean_amount < b.get("mean_amount_min", 72.7645) or mean_amount > b.get("mean_amount_max", 90.6053):
        alert = True
        reasons.append("mean_amount")
    if staleness_min > b.get("staleness_min_max", 8.418):
        alert = True
        reasons.append("staleness")

    return Verdict(alert=alert, pillar="checks", reason="; ".join(reasons))


def check_contract_checkpoint(payload, ctx):
    contract_id = payload.get("contract_id")
    checkpoint_batch_id = payload.get("checkpoint_batch_id")
    res = ctx.tools.contract_diff(contract_id, checkpoint_batch_id)
    if "error" in res:
        return Verdict(alert=False, pillar="contracts")

    b = ctx.baseline
    violations = res.get("violations", [])
    freshness_delay_min = res.get("freshness_delay_min", 0.0)

    alert = False
    reasons = []

    if violations:
        alert = True
        reasons.extend(violations)
    if freshness_delay_min > b.get("freshness_delay_max_min", 11.1141):
        alert = True
        reasons.append("freshness_delay")

    return Verdict(alert=alert, pillar="contracts", reason="; ".join(reasons))


def check_lineage_run(payload, ctx):
    run_id = payload.get("run_id")
    job = payload.get("job", "")
    res = ctx.tools.lineage_graph_slice(run_id)
    if "error" in res:
        return Verdict(alert=False, pillar="lineage")

    b = ctx.baseline
    dur = res.get("duration_ms", 0.0)
    upstream = set(res.get("actual_upstream", []))
    downstream_cnt = res.get("actual_downstream_count", 1)

    alert = False
    reasons = []

    if dur > b.get("lineage_duration_ms_max", 5134.9804):
        alert = True
        reasons.append("runtime_anomaly")

    if downstream_cnt == 0:
        alert = True
        reasons.append("orphan_output")

    if "job_upstreams" not in ctx.state:
        ctx.state["job_upstreams"] = {}

    known = ctx.state["job_upstreams"].get(job)
    if known is not None:
        if len(upstream) < len(known):
            alert = True
            reasons.append("missing_upstream")
        elif len(upstream) > len(known):
            ctx.state["job_upstreams"][job] = upstream
    else:
        if len(upstream) < 2:
            alert = True
            reasons.append("missing_upstream")
        else:
            ctx.state["job_upstreams"][job] = upstream

    return Verdict(alert=alert, pillar="lineage", reason="; ".join(reasons))


def check_feature_materialization(payload, ctx):
    feature_view = payload.get("feature_view")
    batch_id = payload.get("batch_id")
    res = ctx.tools.feature_drift(feature_view, batch_id)
    if "error" in res:
        return Verdict(alert=False, pillar="ai_infra")

    b = ctx.baseline
    shift = res.get("mean_shift_sigma", 0.0)
    alert = shift > b.get("feature_mean_shift_sigma_max", 0.4095)

    return Verdict(alert=alert, pillar="ai_infra", reason=f"shift={shift}")


def check_embedding_batch(payload, ctx):
    corpus = payload.get("corpus")
    chunk_batch_id = payload.get("chunk_batch_id")
    res = ctx.tools.embedding_drift(corpus, chunk_batch_id)
    if "error" in res:
        return Verdict(alert=False, pillar="ai_infra")

    b = ctx.baseline
    shift = res.get("centroid_shift", 0.0)
    age = res.get("avg_doc_age_days", 0.0)

    alert = False
    reasons = []

    if shift > b.get("embedding_centroid_shift_max", 0.0435):
        alert = True
        reasons.append("embedding_drift")
    if age > b.get("corpus_avg_doc_age_days_max", 49.7955):
        alert = True
        reasons.append("corpus_staleness")

    return Verdict(alert=alert, pillar="ai_infra", reason="; ".join(reasons))



