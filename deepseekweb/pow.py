from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

try:
    import wasmtime  # noqa: F401
    import numpy as np  # noqa: F401

    HAS_WASM = True
except Exception:  # noqa: BLE001
    wasmtime = None
    np = None
    HAS_WASM = False

WASM_PATH = os.path.join(os.path.dirname(__file__), "pow.wasm")


class DeepSeekHash:
    def __init__(self):
        self.instance = None
        self.memory = None
        self.store = None

    def init(self, wasm_path: str) -> "DeepSeekHash":
        if not HAS_WASM:
            raise ImportError("POW dependencies missing. Install: pip install wasmtime numpy")
        engine = wasmtime.Engine()
        with open(wasm_path, "rb") as f:
            wasm_bytes = f.read()
        module = wasmtime.Module(engine, wasm_bytes)
        self.store = wasmtime.Store(engine)
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        self.instance = linker.instantiate(self.store, module)
        self.memory = self.instance.exports(self.store)["memory"]
        return self

    def _write_to_memory(self, text: str) -> tuple[int, int]:
        encoded = text.encode("utf-8")
        length = len(encoded)
        ptr = self.instance.exports(self.store)["__wbindgen_export_0"](self.store, length, 1)
        memory_view = self.memory.data_ptr(self.store)
        for i, byte in enumerate(encoded):
            memory_view[ptr + i] = byte
        return ptr, length

    def calculate_hash(self, algorithm: str, challenge: str, salt: str, difficulty: int, expire_at: int) -> int | None:
        prefix = f"{salt}_{expire_at}_"
        retptr = self.instance.exports(self.store)["__wbindgen_add_to_stack_pointer"](self.store, -16)
        try:
            challenge_ptr, challenge_len = self._write_to_memory(challenge)
            prefix_ptr, prefix_len = self._write_to_memory(prefix)
            self.instance.exports(self.store)["wasm_solve"](
                self.store,
                retptr,
                challenge_ptr,
                challenge_len,
                prefix_ptr,
                prefix_len,
                float(difficulty),
            )
            memory_view = self.memory.data_ptr(self.store)
            status = int.from_bytes(bytes(memory_view[retptr : retptr + 4]), byteorder="little", signed=True)
            if status == 0:
                return None
            value_bytes = bytes(memory_view[retptr + 8 : retptr + 16])
            value = np.frombuffer(value_bytes, dtype=np.float64)[0]
            return int(value)
        finally:
            self.instance.exports(self.store)["__wbindgen_add_to_stack_pointer"](self.store, 16)


class DeepSeekPOW:
    def __init__(self):
        self.hasher = DeepSeekHash().init(WASM_PATH)

    def solve_challenge(self, config: dict[str, Any]) -> str:
        answer = self.hasher.calculate_hash(
            config["algorithm"],
            config["challenge"],
            config["salt"],
            config["difficulty"],
            config["expire_at"],
        )
        result = {
            "algorithm": config["algorithm"],
            "challenge": config["challenge"],
            "salt": config["salt"],
            "answer": answer,
            "signature": config["signature"],
            "target_path": config["target_path"],
        }
        return base64.b64encode(json.dumps(result).encode()).decode("utf-8")


def has_pow_libs() -> bool:
    return HAS_WASM