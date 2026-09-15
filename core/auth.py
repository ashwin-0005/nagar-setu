import os, hashlib, csv, re

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "users.csv")

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _is_valid_email(email):
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))

def init_users():
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["email", "password_hash"])
            w.writerow(["demo@nagar setu.local", _hash("demo")])

def validate_user(email, password):
    if not _is_valid_email(email):
        return False
    init_users()
    h = _hash(password)
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            if row["email"] == email and row["password_hash"] == h:
                return True
    return False

def create_user(email, password):
    if not _is_valid_email(email):
        return False
    init_users()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH) as f:
            for row in csv.DictReader(f):
                if row["email"] == email:
                    return False
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([email, _hash(password)])
    return True