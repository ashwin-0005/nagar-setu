import re

KEYWORDS = {
 "garbage": ["kachra", "garbage", "dustbin", "safai", "waste", "heap"],
 "water": ["paani", "water", "pipeline", "nal ", "supply", "leakage"],
 "sewer": ["sewer", "nalli", "nali ka paani", "overflow", "bad smell", "block"],
 "drainage": ["drain", "naali jaam", "logging", "barish"],
 "streetlight": ["streetlight", "street light", "light", "live wire", "flicker"],
 "road": ["pothole", "sadak", "gaddha", "road", "bus stop", "bike gir"],
 "property-tax": ["property tax", "tax bill", "revenue"],
}

def predict_rule(text: str):
    t = (text or "").lower().strip()
    if not t or t == "photo only":
        return "other", 0.40, ["empty/photo-only fallback"]
    scores = {}
    reasons = []
    for cat, kws in KEYWORDS.items():
        for kw in kws:
            if kw in t:
                scores[cat] = scores.get(cat, 0) + 1
                reasons.append(kw)
    if not scores:
        return "other", 0.45, ["no keyword match"]
    best = max(scores, key=scores.get)
    conf = 0.96 if scores[best] >= 2 else 0.82
    return best, conf, sorted(set(reasons))[:4]

# TF-IDF backup: trained lazily on tickets.csv
_vectorizer = None
_clf = None

def _ensure_model():
    global _vectorizer, _clf
    if _clf is not None:
        return True
    try:
        import pandas as pd
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        df = pd.read_csv("data/tickets.csv", dtype=str).fillna("")
        df = df[df["raw_text"].str.strip() != ""]
        _vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        X = _vectorizer.fit_transform(df["raw_text"].str.lower())
        _clf = MultinomialNB()
        _clf.fit(X, df["true_category"])
        return True
    except Exception:
        return False

def predict(text: str):
    cat, conf, reasons = predict_rule(text)
    if conf >= 0.9 or not _ensure_model():
        # top-2: rule best + other
        return cat, conf, reasons, [cat, "other"]
    try:
        import numpy as np
        X = _vectorizer.transform([(text or "").lower()])
        proba = _clf.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        ml_cat = str(_clf.classes_[idx])
        ml_conf = float(proba[idx])
        # trust ML only if stronger than rule
        if ml_conf > 0.55 and ml_cat != cat:
            return ml_cat, round(ml_conf, 2), reasons + [f"ml:{ml_cat}"], [ml_cat, cat]
        order = np.argsort(proba)[::-1][:2]
        top2 = [str(_clf.classes_[i]) for i in order]
        return cat, conf, reasons, top2
    except Exception:
        return cat, conf, reasons, [cat, "other"]
