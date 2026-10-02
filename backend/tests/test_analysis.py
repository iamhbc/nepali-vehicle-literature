import asyncio
import json
from types import SimpleNamespace

from app.analysis.engine import AnalysisEngine
from app.analysis.llm import AnthropicProvider, LLMError
from app.analysis.schema import (
    Ambiguity, AnalysisPayload, DimensionReading, EmotionFinding, EmotionReading, Finding, GenderPowerReading,
    ImpliedMeaning, LoveReading, RelationshipReading, ThemeAssignment, strict_json_schema,
)
from app.analysis.verify import verify
from app.config import get_settings
from app.retrieval.search import get_corpus_index


def _empty_dim():
    return DimensionReading(present=False, summary="", findings=[])


def make_payload(**overrides) -> AnalysisPayload:
    base = dict(
        detected_language="ne", transliteration="", literal_translation="lit", contextual_translation="ctx",
        text_types=[], key_terms=[],
        emotion=EmotionReading(summary="", valence="mixed", overall_intensity="moderate", targets=[], direction="", findings=[]),
        love=LoveReading(present=False, summary="", findings=[]),
        relationships=RelationshipReading(present=False, summary="", findings=[]),
        social=_empty_dim(), economic=_empty_dim(), political=_empty_dim(),
        gender_power=GenderPowerReading(present=False, summary="", power_stance="not_applicable", stance_explanation="", findings=[]),
        cultural=_empty_dim(), philosophical=_empty_dim(), rhetoric=_empty_dim(),
        implied=ImpliedMeaning(literal="", implied="", cultural_reading="", alternatives=[], confidence="medium"),
        themes=[ThemeAssignment(code="LOVE_ROMANCE", confidence="high", rationale="x")],
        ambiguity=Ambiguity(is_ambiguous=False, note=""), context_note="", overall_confidence="high",
    )
    base.update(overrides)
    return AnalysisPayload(**base)


def test_strict_schema_is_closed_and_fully_required():
    schema = strict_json_schema(AnalysisPayload)
    finding = schema["$defs"]["Finding"]
    assert finding["additionalProperties"] is False
    assert set(finding["required"]) == set(finding["properties"])
    assert "title" not in json.dumps(schema)


def test_verify_removes_fabricated_quotes_and_demotes_sensitive_labels():
    text = "तिमी स्त्री हौ, म त पुरुष हुँ"
    payload = make_payload(
        emotion=EmotionReading(summary="", valence="negative", overall_intensity="moderate", targets=[], direction="",
                               findings=[EmotionFinding(label="Resentment", family="anger", intensity="moderate",
                                                        explanation="", evidence=["पुरुष हुँ", "धन कमाउनुपर्छ"],
                                                        confidence="high", kind="evidence")]),
        gender_power=GenderPowerReading(present=True, summary="", power_stance="reproduction", stance_explanation="",
                                        findings=[Finding(label="Misogyny", explanation="", evidence=["नारी"],
                                                          confidence="high", kind="interpretation")]),
        themes=[ThemeAssignment(code="NOT_A_CODE", confidence="low", rationale="")],
    )
    payload, report, warnings = verify(payload, text)
    emo = payload.emotion.findings[0]
    assert emo.evidence == ["पुरुष हुँ"] and emo.confidence == "medium"
    sensitive = payload.gender_power.findings[0]
    assert sensitive.evidence == [] and sensitive.kind == "hypothesis" and sensitive.confidence == "low"
    assert payload.themes == [] and any("unknown theme" in w for w in warnings)
    assert report.quotes_checked == 3 and report.quotes_verified == 1


class FakeMessages:
    def __init__(self, payload: dict, stop_reason: str = "end_turn"):
        self.payload, self.stop_reason, self.calls = payload, stop_reason, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason, model=kwargs["model"],
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20, cache_read_input_tokens=0),
        )


def fake_provider(payload: dict, stop_reason="end_turn"):
    messages = FakeMessages(payload, stop_reason)
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return AnthropicProvider(get_settings(), client=client), messages


def test_llm_engine_sends_structured_request_and_verifies_output(client, db):
    text = "माया भनेको सम्झना रहेछ"
    llm_payload = make_payload(
        love=LoveReading(present=True, summary="", findings=[]),
        emotion=EmotionReading(summary="", valence="mixed", overall_intensity="moderate", targets=[], direction="",
                               findings=[EmotionFinding(label="Longing", family="longing", intensity="moderate",
                                                        explanation="", evidence=["सम्झना"], confidence="high",
                                                        kind="interpretation")]),
    ).model_dump()
    provider, messages = fake_provider(llm_payload)
    engine = AnalysisEngine(get_settings(), get_corpus_index(), provider)
    events = []

    async def run():
        async for ev in engine.stream(db, text, use_cache=False):
            events.append(ev)

    asyncio.run(run())
    names = [e["event"] for e in events]
    assert "preliminary" in names and names[-1] == "result"
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in call["betas"]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "<phrase>\n" + text in call["messages"][0]["content"]
    result = events[-1]["data"]
    assert result["engine"]["mode"] == "llm"
    assert result["payload"]["emotion"]["findings"][0]["evidence"] == ["सम्झना"]
    assert result["payload"]["transliteration"]  # filled automatically when the model leaves it empty


def test_engine_falls_back_to_baseline_on_refusal(client, db):
    provider, _ = fake_provider({}, stop_reason="refusal")
    engine = AnalysisEngine(get_settings(), get_corpus_index(), provider)
    result = asyncio.run(engine.analyze(db, "भाडा लिऊँ भने इष्ट बाङ्गो", use_cache=False))
    assert result.engine.mode == "baseline"
    assert any("unavailable" in w for w in result.warnings)


def test_provider_raises_on_truncation():
    provider, _ = fake_provider({}, stop_reason="max_tokens")
    try:
        asyncio.run(provider.structured("s", "u", {}, 100))
    except LLMError as exc:
        assert "cut off" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected LLMError")
