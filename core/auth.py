import os, hashlib, csv

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "users.csv")

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_users():
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["username", "password_hash"])
            w.writerow(["admin", _hash("admin")])

def validate_user(username, password):
    init_users()
    h = _hash(password)
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            if row["username"] == username and row["password_hash"] == h:
                return True
    return False

def create_user(username, password):
    init_users()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH) as f:
            for row in csv.DictReader(f):
                if row["username"] == username:
                    return False
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([username, _hash(password)])
    return True
