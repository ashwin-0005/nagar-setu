import pandas as pd
from datetime import datetime
from .classifier import predict
from .urgency import score, priority
from .dedupe import assign_parents
from .router import load_refs, route

def run_pipeline(csv_path, base="."):
    sla, officers = load_refs(base)
    df = pd.read_csv(csv_path, dtype=str).fillna("")
    cats, confs, reasons, top2s, urg, ureasons, pris, prreasons = [], [], [], [], [], [], [], []
    depts, oids, onames, dues, rreasons = [], [], [], [], []
    for _, r in df.iterrows():
        c, cf, rs, t2 = predict(r["raw_text"])
        u, ur = score(r["raw_text"])
        p, pr = priority(r["raw_text"])
        d, oid, oname, due, rr = route(c, r["ward"], r.get("created_at", datetime.now().isoformat()), sla, officers)
        cats.append(c); confs.append(cf); reasons.append(",".join(rs))
        top2s.append(",".join(t2)); urg.append(u); ureasons.append(",".join(ur))
        pris.append(p); prreasons.append(",".join(pr))
        depts.append(d); oids.append(oid); onames.append(oname); dues.append(due); rreasons.append(rr)
    df["pred_category"] = cats
    df["confidence"] = confs
    df["match_reasons"] = reasons
    df["top2"] = top2s
    df["urgency"] = urg
    df["urgency_reasons"] = ureasons
    df["priority"] = pris
    df["priority_reasons"] = prreasons
    df["priority_color"] = df["priority"].map({"P1": "red", "P2": "yellow", "P3": "green"})
    df["dept"] = depts
    df["officer_id"] = oids
    df["officer_name"] = onames
    df["sla_due"] = dues
    df["route_reason"] = rreasons
    df["status"] = "open"
    # SLA breach vs now
    now = datetime.now()
    df["is_breach"] = pd.to_datetime(df["sla_due"]) < now
    df = assign_parents(df)
    return df
