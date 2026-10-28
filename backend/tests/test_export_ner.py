"""ONNX export wrapper (Task 2.4)."""

from pathlib import Path

import gliner
import pytest

from scripts import export_ner_onnx


def test_export_passes_quantized_artifact_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[tuple, dict]] = []

    class FakeModel:
        def export_to_onnx(self, *args, **kwargs):  # noqa: ANN002, ANN003
            calls.append((args, kwargs))
            return {"onnx_path": "model.onnx", "quantized_path": "model_quantized.onnx"}

    class FakeGLiNER:
        @classmethod
        def from_pretrained(cls, model_name: str) -> FakeModel:
            calls.append(((model_name,), {}))
            return FakeModel()

    monkeypatch.setattr(gliner, "GLiNER", FakeGLiNER)
    result = export_ner_onnx.export("model-id", tmp_path, True, 19)
    assert result["quantized_path"] == "model_quantized.onnx"
    assert calls[0] == (("model-id",), {})
    assert calls[1][0] == (tmp_path,)
    assert calls[1][1] == {
        "quantize": True,
        "opset": 19,
        "onnx_filename": "model.onnx",
        "quantized_filename": "model_quantized.onnx",
    }
