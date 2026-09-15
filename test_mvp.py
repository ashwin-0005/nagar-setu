import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from core.pipeline import run_pipeline

for name in ["data/demo_50.csv", "data/tickets.csv"]:
    df = run_pipeline(name)
    # routing accuracy top-2
    if "true_category" in df.columns:
        ok = sum(1 for _, r in df.iterrows() if r["true_category"] in str(r["top2"]).split(","))
        acc = ok / len(df) * 100
        print(f"{name}: {len(df)} tickets | top-2 acc {acc:.1f}% | dupes {int(df['is_duplicate'].sum())} | breach {int(df['is_breach'].sum())} | emerg {int((df['urgency']=='emergency').sum())}")
    else:
        print(f"{name}: {len(df)} tickets OK")
    # edge cases must not crash
    assert "pred_category" in df.columns and "parent_id" in df.columns
print("ALL CHECKS PASSED")
