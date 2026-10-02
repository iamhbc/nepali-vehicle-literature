import io
import json

from PIL import Image


def test_health_and_meta(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["engine"] == "baseline" and h["corpus_size"] >= 61
    m = client.get("/api/meta").json()
    assert len(m["themes"]) >= 23 and m["ocr_available"] is False


def test_analyze_corpus_phrase_returns_researcher_record(client):
    r = client.post("/api/analyze", json={"text": "भाडा लिऊँ भने इष्ट बाङ्गो; भाडा नलिऊँ भने आफू नाङ्गो।"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["corpus_match"]["corpus_id"] == "NVL-001"
    assert {t["code"] for t in data["payload"]["themes"]} >= {"FARE_LIVELIHOOD"}
    assert data["graph"]["nodes"][0]["type"] == "root"
    assert data["verification"]["quotes_checked"] == data["verification"]["quotes_verified"]
    again = client.get(f"/api/analyses/{data['id']}").json()
    assert again["id"] == data["id"]


def test_analyze_new_phrase_is_honest_about_limits(client):
    data = client.post("/api/analyze", json={"text": "परदेशमा आमाको याद आउँछ"}).json()
    assert data["corpus_match"] is None
    assert data["payload"]["literal_translation"] == ""
    assert any("not in the research corpus" in w for w in data["warnings"])
    assert any(t["code"] == "MIGRATION" for t in data["payload"]["themes"])
    assert data["related"]


def test_analyze_validation(client):
    assert client.post("/api/analyze", json={"text": "   "}).status_code == 422
    assert client.post("/api/analyze", json={"text": "१२३ ..."}).status_code == 422
    assert client.post("/api/analyze", json={"text": "क" * 700}).status_code == 422


def test_analyze_stream_emits_stages_then_result(client):
    with client.stream("POST", "/api/analyze/stream", json={"text": "देश त पुरानै ठीक थियो।"}) as r:
        body = "".join(r.iter_text())
    events = [blk.split("\n")[0].removeprefix("event: ") for blk in body.strip().split("\n\n")]
    assert events[0] == "stage" and events[-1] == "result"
    result = json.loads(body.strip().split("\n\n")[-1].split("data: ", 1)[1])
    assert result["corpus_match"]["corpus_id"] == "NVL-057"


def test_contribution_creates_submission(client, admin_headers):
    client.post("/api/analyze", json={"text": "बाटो लामो छ, साथी नछोड", "contribute": True,
                                      "context": {"vehicle_type": "truck", "district_id": 68}})
    subs = client.get("/api/admin/submissions", headers=admin_headers).json()
    assert any(s["text"] == "बाटो लामो छ, साथी नछोड" and s["vehicle_type"] == "truck" and s["district"] == "Surkhet" for s in subs)


def test_corpus_endpoints(client):
    assert client.get("/api/phrases").json()["total"] >= 61
    assert client.get("/api/phrases", params={"theme": "MIGRATION"}).json()["total"] == 4
    detail = client.get("/api/phrases/15").json()
    assert detail["places_mentioned"][0]["district"] == "Mugu" and detail["graph"]
    assert client.get("/api/phrases/9999").status_code == 404
    s = client.get("/api/search", params={"q": "corruption and politicians"}).json()
    assert s["results"] and "INSTITUTION_CRITIQUE" in s["results"][0]["codes"]
    stats = client.get("/api/stats").json()
    assert stats["total"] >= 61 and stats["cooccurrence"]
    locs = client.get("/api/locations").json()
    assert len(locs) == 7 and sum(len(p["districts"]) for p in locs) == 77
    assert len(client.get("/api/vehicles").json()) >= 10
    ex = client.get("/api/examples").json()
    assert 4 <= len(ex) <= 8


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_reports_unavailable_and_rejects_non_images(client):
    r = client.post("/api/ocr", files={"file": ("x.png", _png(), "image/png")})
    assert r.status_code == 503 and "type the inscription" in r.json()["detail"]
    r = client.post("/api/ocr", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_image_preparation_strips_metadata():
    from app.ocr.image import prepare_image

    buf = io.BytesIO()
    img = Image.new("RGB", (3000, 1000), "red")
    exif = Image.Exif()
    exif[0x010F] = "SecretPhoneMaker"
    img.save(buf, format="JPEG", exif=exif)
    prepared = prepare_image(buf.getvalue(), 8 * 1024 * 1024)
    assert max(prepared.width, prepared.height) == 1600
    assert b"SecretPhoneMaker" not in prepared.data
