"""Export the configured GLiNER checkpoint to ONNX + dynamic int8.

Usage (from backend/):
    uv run python scripts/export_ner_onnx.py
    NER_ONNX_DIR=data/ner_onnx uv run python scripts/export_ner_onnx.py

The exported directory contains the tokenizer, gliner_config.json and both
model.onnx / model_quantized.onnx. Point NER_RUNTIME=onnx at it after export.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/: `app` package

import argparse

from app.config import settings


def export(model_name: str, out: Path, quantize: bool, opset: int) -> dict[str, str | None]:
    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_name)
    return model.export_to_onnx(
        out,
        quantize=quantize,
        opset=opset,
        onnx_filename="model.onnx",
        quantized_filename="model_quantized.onnx",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=settings.ner_model)
    parser.add_argument("--out", type=Path, default=Path(settings.ner_onnx_dir))
    parser.add_argument("--no-quantize", action="store_true")
    parser.add_argument("--opset", type=int, default=19)
    args = parser.parse_args()
    result = export(args.model, args.out, not args.no_quantize, args.opset)
    print(f"onnx: {result['onnx_path']}")
    if result["quantized_path"] is not None:
        print(f"int8: {result['quantized_path']}")


if __name__ == "__main__":
    main()
