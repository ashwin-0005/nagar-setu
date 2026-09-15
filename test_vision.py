import sys; sys.path.insert(0, '.')
import io
from PIL import Image
from core.vision import classify_photo

def solid(color, size=(200, 200)):
    img = Image.new("RGB", size, color)
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

tests = {
    "blue water-like": solid((40, 120, 220)),
    "gray road-like": solid((140, 140, 145)),
    "brown garbage-like": solid((130, 95, 50)),
    "dark night streetlight-like": solid((15, 15, 25)),
    "green garbage-like": solid((70, 130, 60)),
}
for name, data in tests.items():
    r = classify_photo(data)
    print(f"{name:28s} -> {r['category']} ({r['confidence']}) | {r['reasons'][0]}")

# garbage image should not crash and give a plausible bucket
r = classify_photo(solid((130, 95, 50)))
assert r["category"] in ("garbage", "sewer", "water", "drainage", "streetlight", "road", "other")
# corrupt bytes must not crash
r2 = classify_photo(b"not an image at all")
assert r2["category"] == "other"
print("VISION CHECKS PASSED")
