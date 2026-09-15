import csv, random
from datetime import datetime, timedelta

base = [
 ("kachra 4 din se nahi utha ward 12 Patel nagar", "garbage", "12"),
 ("garbage pile near Patel Nagar gate ward 12 photo attached", "garbage", "12"),
 ("kachra pada hai gali me 3 din se ward 11", "garbage", "11"),
 ("dustbin overflow near market ward 12", "garbage", "12"),
 ("paani nahi aa raha 3 din se ward 12", "water", "12"),
 ("water pipeline leakage near park ward 10", "water", "10"),
 ("nal me ganda paani aa raha hai ward 12", "water", "12"),
 ("no water supply since morning ward 10", "water", "10"),
 ("sewer overflow on main road ward 12 urgent", "sewer", "12"),
 ("nali ka paani road par beh raha hai ward 12", "sewer", "12"),
 ("sewer block near house 45 ward 12 bad smell", "sewer", "12"),
 ("drain blocked rain water logging ward 12", "drainage", "12"),
 ("naali jaam barish ka paani bhara ward 11", "drainage", "11"),
 ("streetlight not working 5 days ward 12", "streetlight", "12"),
 ("street light flicker near school ward 10", "streetlight", "10"),
 ("live wire fallen on road ward 12 EMERGENCY", "streetlight", "12"),
 ("pothole on main road near bus stop ward 12", "road", "12"),
 ("sadak me gaddha bike gir gaya ward 12", "road", "12"),
 ("road broken after rain ward 11", "road", "11"),
 ("property tax bill wrong ward 12", "property-tax", "12"),
 ("stray dogs menace ward 10", "other", "10"),
 ("", "other", ""),
 ("photo only", "garbage", "12"),
 ("paani", "water", ""),
]

rows = []
tid = 1
now = datetime.now()
# expand to 200 with variations
for i in range(200):
    t, cat, ward = base[i % len(base)]
    # inject duplicates: every 7th repeats pothole
    if i % 17 == 0:
        t, cat, ward = ("pothole on main road near bus stop ward 12", "road", "12")
    if i % 23 == 0:
        t, cat, ward = ("kachra 4 din se nahi utha ward 12 Patel nagar", "garbage", "12")
    days_ago = random.randint(0, 6)
    ts = (now - timedelta(days=days_ago, hours=random.randint(0, 12))).isoformat()
    rows.append([f"C{tid:03d}", t, ward, ts, cat])
    tid += 1

with open(r"C:\Users\HP\civic-triage-mvp\data\tickets.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "raw_text", "ward", "created_at", "true_category"])
    w.writerows(rows)

# demo 50: first 50 with edge cases forced
import pandas as pd
df = pd.read_csv(r"C:\Users\HP\civic-triage-mvp\data\tickets.csv", dtype=str)
demo = df.head(50).copy()
# force edge cases
demo.loc[48, ["raw_text", "ward"]] = ["", ""]
demo.loc[49, ["raw_text", "ward"]] = ["photo only", "12"]
demo.to_csv(r"C:\Users\HP\civic-triage-mvp\data\demo_50.csv", index=False)
print(f"wrote {len(rows)} tickets, demo {len(demo)}")
