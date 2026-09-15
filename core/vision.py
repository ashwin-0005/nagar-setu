"""Photo -> complaint category (lightweight starter, no heavy deps).

Layers (best available wins):
 1. OCR text in photo (if pytesseract + tesseract binary installed) -> fed into
    the existing text classifier (strong signal, e.g. signboard "SEWER").
 2. CLIP zero-shot (if torch + transformers installed) -> real visual signal.
 3. PIL colour/texture heuristic (always available) -> experimental guess,
    clearly labelled so the operator confirms.

Returns (category, confidence, reasons). Confidence from layer 3 is capped
at 0.70 and flagged 'experimental' — text prediction should override it
when text confidence is high. See app.py fusion rule.
"""
import io

CATEGORIES = ["garbage", "water", "sewer", "drainage", "streetlight", "road",
              "property-tax", "other"]

# ---- Layer 2: CLIP zero-shot (optional) ----
_CLIP = None

def _clip_predict(pil_img):
    """Return (category, confidence) or None if CLIP unavailable."""
    global _CLIP
    try:
        import torch
        from transformers import CLIPProcessor, CLIPModel
    except ImportError:
        return None
    try:
        if _CLIP is None:
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            _CLIP = (model, proc)
        model, proc = _CLIP
        prompts = {
            "garbage": "a photo of a garbage pile and overflowing dustbin",
            "water": "a photo of leaking water pipe and water supply",
            "sewer": "a photo of overflowing sewer and dirty drain water",
            "drainage": "a photo of blocked drain with rainwater logging",
            "streetlight": "a photo of a street light pole at night",
            "road": "a photo of a broken road with potholes",
            "property-tax": "a photo of a property tax bill document",
            "other": "a photo of a street",
        }
        import torch as _t
        inputs = proc(text=list(prompts.values()), images=pil_img,
                      return_tensors="pt", padding=True)
        with _t.no_grad():
            out = model(**inputs)
        probs = out.logits_per_image.softmax(dim=1)[0].tolist()
        best = max(range(len(probs)), key=lambda i: probs[i])
        return list(prompts)[best], round(float(probs[best]), 2)
    except Exception:
        return None


# ---- Layer 1: OCR (optional) ----
def _ocr_text(pil_img):
    try:
        import pytesseract
        return pytesseract.image_to_string(pil_img) or ""
    except Exception:
        return ""


# ---- Layer 3: PIL heuristic (always available) ----
def _heuristic(pil_img):
    from PIL import Image, ImageStat
    img = pil_img.convert("RGB").resize((64, 64))
    px = list(img.getdata())
    n = len(px)
    stat = ImageStat.Stat(img)
    bright = sum(stat.mean) / 3  # 0-255
    brown = sum(1 for r, g, b in px if r > 90 and r < 170 and g > 60 and g < 130 and b < 80) / n
    green = sum(1 for r, g, b in px if g > r + 20 and g > b + 10) / n
    blue = sum(1 for r, g, b in px if b > r + 30 and b > g + 10) / n
    gray = sum(1 for r, g, b in px if abs(r - g) < 18 and abs(g - b) < 18 and 90 < r < 190) / n
    dark = sum(1 for r, g, b in px if r < 50 and g < 50 and b < 50) / n
    bright_spots = sum(1 for r, g, b in px if r > 220 and g > 220 and b > 180) / n
    scores = {
        "garbage": brown * 2.0 + green * 1.2,
        "water": blue * 2.2,
        "sewer": brown * 1.2 + green * 0.6 + (0.15 if bright < 110 else 0),
        "drainage": blue * 0.9 + gray * 0.7,
        "streetlight": (dark * 1.6 + bright_spots * 3.0) if dark > 0.25 else 0,
        "road": gray * 1.8,
    }
    best = max(scores, key=scores.get)
    val = scores[best]
    if val < 0.08:
        return "other", 0.40, ["experimental visual: unclear photo"]
    conf = round(min(0.70, 0.50 + val), 2)
    why = f"experimental visual: {best} cues"
    detail = f"brown={brown:.2f} green={green:.2f} blue={blue:.2f} gray={gray:.2f} dark={dark:.2f}"
    return best, conf, [why, detail]


def classify_photo(data: bytes):
    """Main entry. Returns dict(category, confidence, reasons, ocr_text)."""
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return {"category": "other", "confidence": 0.40,
                "reasons": ["not a readable image"], "ocr_text": ""}
    reasons, ocr_text = [], ""
    # Layer 1: OCR -> text classifier (strong)
    ocr_text = _ocr_text(img).strip()
    if ocr_text and len(ocr_text) >= 4:
        try:
            from .classifier import predict as text_predict
            cat, conf, kw, _ = text_predict(ocr_text)
            if conf >= 0.6 and cat != "other":
                return {"category": cat, "confidence": round(min(conf, 0.85), 2),
                        "reasons": [f"photo text says: {ocr_text[:60]}"], "ocr_text": ocr_text}
            reasons.append(f"photo text: {ocr_text[:60]}")
        except Exception:
            pass
    # Layer 2: CLIP (real vision, if installed)
    clip = _clip_predict(img)
    if clip:
        cat, conf = clip
        return {"category": cat, "confidence": conf,
                "reasons": ["CLIP zero-shot visual match"] + reasons, "ocr_text": ocr_text}
    # Layer 3: heuristic fallback
    cat, conf, why = _heuristic(img)
    return {"category": cat, "confidence": conf,
            "reasons": why + reasons, "ocr_text": ocr_text}
