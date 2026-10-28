"""NER skip, cache and ONNX loader selection (Task 2.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

import gliner
from app.config import settings
from app.scrubber.ner import GlinerNer, has_name_candidate


class FakeModel:
    def __init__(self) -> None:
        self.seen: list[list[str]] = []

    def inference(self, chunks, labels, threshold):  # noqa: ANN001
        self.seen.append(list(chunks))
        return [
            [{"start": 0, "end": 4, "text": chunk[:4]}]
            for chunk in chunks
        ]


def test_has_name_candidate() -> None:
    assert has_name_candidate("Chinedu Okafor")
    assert has_name_candidate("chinedu")
    assert not has_name_candidate("0123456789")
    assert not has_name_candidate("50000 12345")


def test_skips_chunks_without_name_letters_and_keeps_alignment() -> None:
    ner = GlinerNer()
    fake = FakeModel()
    ner._model = fake
    found = ner.find_persons(["0123456789", "Chinedu Okafor"])
    assert found[0] == []
    assert [span.text for span in found[1]] == ["Chin"]
    assert fake.seen == [["Chinedu Okafor"]]


def test_cache_is_by_content_and_avoids_second_inference() -> None:
    ner = GlinerNer()
    fake = FakeModel()
    ner._model = fake
    first = ner.find_persons(["Ngozi Eze"])
    second = ner.find_persons(["Ngozi Eze"])
    assert first == second
    assert fake.seen == [["Ngozi Eze"]]


def test_cache_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ner_cache_ttl_seconds", 0)
    ner = GlinerNer()
    fake = FakeModel()
    ner._model = fake
    ner.find_persons(["Ngozi Eze"])
    ner.find_persons(["Ngozi Eze"])
    assert len(fake.seen) == 2


def test_onnx_loader_uses_configured_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[tuple, dict]] = []

    class FakeGLiNER:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append((args, kwargs))
            return object()

    monkeypatch.setattr(gliner, "GLiNER", FakeGLiNER)
    monkeypatch.setattr(settings, "ner_runtime", "onnx")
    monkeypatch.setattr(settings, "ner_onnx_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ner_onnx_file", "model_quantized.onnx")
    (tmp_path / "model_quantized.onnx").write_bytes(b"fake")
    GlinerNer()._load_model()
    assert calls == [
        (
            (str(tmp_path),),
            {"runtime": "onnxruntime", "runtime_model_file": "model_quantized.onnx"},
        )
    ]


def test_onnx_loader_rejects_missing_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "ner_runtime", "onnx")
    monkeypatch.setattr(settings, "ner_onnx_dir", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        GlinerNer()._load_model()
