from __future__ import annotations
from typing import List, Optional, Dict, Any
from .base import ModelProvider, ModelResponse, Message


class TransformersProvider(ModelProvider):
    """Provider for Hugging Face Transformers models.

    kwargs:
      model_name: str (HF repo id or local path)
      device_map: str (e.g., "auto")
      load_in_4bit: bool (requires bitsandbytes)
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "transformers is not installed. Install it to use TransformersProvider."
            ) from e
        self._AutoModelForCausalLM = AutoModelForCausalLM
        self._AutoTokenizer = AutoTokenizer
        model_name = kwargs.get("model_name")
        if not model_name:
            raise ValueError("TransformersProvider requires model_name")
        load_in_4bit = kwargs.get("load_in_4bit", False)
        device_map = kwargs.get("device_map", "auto")
        quant_kwargs = {}
        if load_in_4bit:
            try:
                import bitsandbytes as bnb  # noqa: F401
                quant_kwargs = dict(load_in_4bit=True)
            except Exception as e:  # pragma: no cover
                raise RuntimeError("bitsandbytes not installed but load_in_4bit=True was set") from e
        self.tokenizer = self._AutoTokenizer.from_pretrained(model_name, use_fast=True)
        self.model = self._AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=device_map,
            **quant_kwargs,
        )

    def chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any) -> ModelResponse:
        # Simple prompt format; for instruct models this works reasonably.
        prompt = "".join(f"[{m.role.upper()}]\n{m.content}\n" for m in messages) + "[ASSISTANT]\n"
        import torch  # type: ignore
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=gen_kwargs.get("max_tokens", 512),
                do_sample=True,
                temperature=gen_kwargs.get("temperature", 0.2),
                eos_token_id=self.tokenizer.eos_token_id,
            )
        text = self.tokenizer.decode(output[0], skip_special_tokens=True)
        # Return only the assistant continuation after the prompt
        completion = text[len(prompt):].strip()
        return ModelResponse(text=completion)

    def stream_chat(self, messages: List[Message], tools_schema: Optional[List[Dict[str, Any]]] = None, **gen_kwargs: Any):
        # Stream using Transformers TextIteratorStreamer
        prompt = "".join(f"[{m.role.upper()}]\n{m.content}\n" for m in messages) + "[ASSISTANT]\n"
        import torch  # type: ignore
        from transformers import TextIteratorStreamer  # type: ignore
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        streamer = TextIteratorStreamer(self.tokenizer, skip_special_tokens=True, skip_prompt=True)
        import threading

        def _worker():
            with torch.no_grad():
                self.model.generate(
                    **inputs,
                    max_new_tokens=gen_kwargs.get("max_tokens", 512),
                    do_sample=True,
                    temperature=gen_kwargs.get("temperature", 0.2),
                    eos_token_id=self.tokenizer.eos_token_id,
                    streamer=streamer,
                )

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        try:
            for token in streamer:
                yield token
        except Exception:
            pass
