from __future__ import annotations
from typing import List, Optional, Dict, Any
from .base import ModelProvider, ModelResponse, Message


class LlamaCppProvider(ModelProvider):
    """Provider for local GGUF models via llama-cpp-python.

    kwargs:
      model_path: str (path to .gguf)
      n_ctx: int (context tokens)
      n_gpu_layers: int (optional, if CUDA build)
      n_threads: int (CPU threads)
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        try:
            from llama_cpp import Llama  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "llama-cpp-python is not installed. Install it to use LlamaCppProvider."
            ) from e
        self._Llama = Llama
        model_path = kwargs.get("model_path")
        if not model_path:
            raise ValueError("LlamaCppProvider requires model_path to a GGUF file")
        self._llm = self._Llama(
            model_path=model_path,
            n_ctx=kwargs.get("n_ctx", 4096),
            n_gpu_layers=kwargs.get("n_gpu_layers", 0),
            n_threads=kwargs.get("n_threads"),
            verbose=False,
        )

    def chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any) -> ModelResponse:
        prompt = "".join(
            f"<|{m.role}|>\n{m.content}\n" for m in messages
        ) + "<|assistant|>\n"
        out = self._llm(prompt=prompt, max_tokens=gen_kwargs.get("max_tokens", 512), temperature=gen_kwargs.get("temperature", 0.2))
        text = out["choices"][0]["text"].strip()
        return ModelResponse(text=text)
