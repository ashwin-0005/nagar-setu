from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def assign_parents(df, threshold=0.82):
    """Add parent_id: duplicates point to first occurrence in same ward."""
    texts = df["raw_text"].fillna("").str.lower().tolist()
    wards = df["ward"].fillna("").tolist()
    ids = df["id"].tolist()
    if len(texts) <= 1:
        df["parent_id"] = ids
        return df
    vec = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(texts)
    sim = cosine_similarity(vec)
    parent = {}
    for i, tid in enumerate(ids):
        found = None
        for j in range(i):
            if wards[i] == wards[j] and sim[i, j] >= threshold and texts[i].strip():
                found = parent.get(ids[j], ids[j])
                break
        parent[tid] = found if found else tid
    df["parent_id"] = df["id"].map(parent)
    df["is_duplicate"] = df["id"] != df["parent_id"]
    return df
