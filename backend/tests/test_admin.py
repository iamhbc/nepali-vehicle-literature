def test_admin_requires_auth(client):
    assert client.get("/api/admin/review-queue").status_code == 401
    assert client.post("/api/admin/login", json={"username": "researcher", "password": "wrong"}).status_code == 401


def test_review_queue_is_prioritised(client, admin_headers):
    queue = client.get("/api/admin/review-queue", headers=admin_headers).json()
    assert len(queue) == 27
    assert queue[0]["review_priority"].startswith("High")


def test_edit_approve_and_audit(client, admin_headers):
    r = client.put("/api/admin/phrases/1", headers=admin_headers, json={
        "translation_normalized": "If I ask kin for the fare they sulk; if I don't, I go bare.",
        "note": "Native-speaker correction",
    })
    assert r.status_code == 200
    assert r.json()["translation_original"].startswith("If I ask for the fare, people")  # original kept
    r = client.put("/api/admin/phrases/1/themes", headers=admin_headers,
                   json={"code": "FAMILY", "status": "approved", "rationale": "इष्ट = kin"})
    assert any(t["code"] == "FAMILY" and t["status"] == "approved" for t in r.json()["themes"])
    r = client.post("/api/admin/phrases/1/approve", headers=admin_headers, json={"note": "checked"})
    assert r.json()["needs_review"] is False
    audit = client.get("/api/admin/audit", headers=admin_headers, params={"target_id": "1"}).json()
    assert {"update", "approve"} <= {e["action"] for e in audit}


def test_reimport_skips_researcher_edited_entries(client, admin_headers):
    result = client.post("/api/admin/import-corpus", headers=admin_headers).json()
    assert result["skipped_researcher_edited"] >= 1
    assert client.get("/api/phrases/1").json()["translation"].startswith("If I ask kin")


def test_create_archive_and_reanalyze(client, admin_headers):
    r = client.post("/api/admin/phrases", headers=admin_headers,
                    json={"text_nepali": "सुर्खेतको बाटो, आमाको याद", "codes": ["FAMILY"], "vehicle_type": "bus"})
    assert r.status_code == 201
    pid = r.json()["id"]
    assert r.json()["corpus_id"] == f"NVL-{pid:03d}"
    re_ = client.post(f"/api/admin/phrases/{pid}/reanalyze", headers=admin_headers).json()
    assert re_["engine"] == "baseline"
    assert client.delete(f"/api/admin/phrases/{pid}", headers=admin_headers).json()["status"] == "archived"
    assert client.get(f"/api/phrases/{pid}").status_code == 404


def test_add_theme_and_reference(client, admin_headers):
    r = client.post("/api/admin/themes", headers=admin_headers, json={
        "code": "ROAD_SAFETY", "label_en": "Road safety", "label_ne": "सडक सुरक्षा", "group": "social",
        "definition": "Warnings and appeals about safe driving"})
    assert r.status_code == 201
    assert any(t["code"] == "ROAD_SAFETY" for t in client.get("/api/meta").json()["themes"])
    r = client.post("/api/admin/references", headers=admin_headers, json={
        "id": "test-ref", "title": "T", "authors": "A", "source": "S", "url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_submission_accept_with_ocr_correction(client, admin_headers):
    client.post("/api/analyze", json={"text": "जिन्दगी एउटा लामो बाटो", "contribute": True, "ocr_text": "जिन्दगि एउटा लामो वाटो"})
    sub = next(s for s in client.get("/api/admin/submissions", headers=admin_headers).json() if s["text"] == "जिन्दगी एउटा लामो बाटो")
    r = client.post(f"/api/admin/submissions/{sub['id']}/accept", headers=admin_headers,
                    json={"text": "जिन्दगी एउटा लामो बाटो हो", "note": "fixed ending"})
    assert r.status_code == 200 and r.json()["phrase"]["source"] == "public-submission"


def test_exports(client, admin_headers):
    csv_ = client.get("/api/admin/export", params={"format": "csv"}, headers=admin_headers)
    assert csv_.status_code == 200 and "corpus_id" in csv_.text and "NVL-001" in csv_.text
    js = client.get("/api/admin/export", headers=admin_headers).json()
    assert js["records"] and js["taxonomy_version"]
    an = client.get("/api/admin/analytics", headers=admin_headers).json()
    assert an["analyses"] >= 1


def test_corpus_edit_invalidates_cached_analysis(client, admin_headers):
    text = "देश त पुरानै ठीक थियो।"
    first = client.post("/api/analyze", json={"text": text}).json()
    assert client.post("/api/analyze", json={"text": text}).json()["engine"]["cached"] is True
    client.put(f"/api/admin/phrases/{first['corpus_match']['id']}", headers=admin_headers,
               json={"review_reason": "Referent of 'old' still unclear", "note": "cache test"})
    assert client.post("/api/analyze", json={"text": text}).json()["engine"]["cached"] is False
