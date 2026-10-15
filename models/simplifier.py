import os
import textwrap
from typing import Dict
import openai
from transformers import pipeline as hf_pipeline

class Simplifier:
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.hf_fallback = None
        if not self.openai_key:
            try:
                self.hf_fallback = hf_pipeline("text2text-generation", model="t5-small")
            except Exception:
                self.hf_fallback = None

    def simplify(self, original_text: str, constraints: Dict, attempt: int = 0) -> str:
        constraint_lines = []
        if constraints.get("parties"):
            constraint_lines.append("Parties: " + ", ".join(constraints["parties"]))
        if constraints.get("amounts"):
            constraint_lines.append("Amounts: " + ", ".join(constraints["amounts"]))
        if constraints.get("deadlines"):
            constraint_lines.append("Deadlines: " + ", ".join(constraints["deadlines"]))
        if constraints.get("obligations"):
            constraint_lines.append("Obligation keywords: " + ", ".join(set(constraints["obligations"])))

        instruction = (
            "Rewrite the legal text in clear, plain English while preserving every legally significant fact "
            "(parties, obligations, permissions, prohibitions, conditions, deadlines, amounts)."
        )
        if attempt > 0:
            instruction += f" This is attempt {attempt + 1} to fix mismatches from prior output."

        prompt = "\n\n".join([
            instruction,
            "Constraints to preserve:",
            "\n".join(constraint_lines) if constraint_lines else "No additional constraints detected.",
            "Original text:",
            original_text
        ])

        if self.openai_key:
            openai.api_key = self.openai_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You simplify legal documents without changing legal meaning."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.2
            )
            output = response["choices"][0]["message"]["content"].strip()
            return output

        if self.hf_fallback:
            payload = "Simplify: " + original_text[:2500]
            outputs = self.hf_fallback(payload, max_length=512, truncation=True)
            generated = outputs[0]["generated_text"]
            return textwrap.fill(generated, 100)

        return original_text
