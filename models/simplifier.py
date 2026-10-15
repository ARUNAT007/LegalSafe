import os
import re
import textwrap
from typing import Dict, Optional
import openai
from transformers import pipeline as hf_pipeline

# Simplifier tuned for higher-quality rewrites when OPENAI_API_KEY is available.
# Includes conservative system prompt, a careful example, party substitution, and stripping of test sections.

def _strip_test_sections(text: str) -> str:
    if not text:
        return text
    patterns = [
        r"(?is)^\s*Test\s*Objective[:\-\s\n].*?(?=^\s*[A-Z][A-Za-z\s]{0,60}:|\Z)",
        r"(?is)^\s*Required\s*Fact[:\-\s\n].*?(?=^\s*[A-Z][A-Za-z\s]{0,60}:|\Z)",
        r"(?is)^\s*Test\s*instructions[:\-\s\n].*?(?=^\s*[A-Z][A-Za-z\s]{0,60}:|\Z)",
    ]
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _insert_parties(text: str, party_overrides: Optional[Dict[str,str]]):
    if not party_overrides:
        return text
    out = text
    for key, val in party_overrides.items():
        if not val:
            continue
        # replace placeholder tokens exactly
        out = out.replace(key, val)
        # replace some common label forms
        out = re.sub(r"\bDisclosing Party\b", val if 'Disclosing' in key or key=="Disclosing Party" else out, out)
    # Also replace blank underline placeholders: simple heuristic
    out = re.sub(r"_{3,}", lambda m: party_overrides.get('<PRIVATE COMPANY A>', party_overrides.get('<PRIVATE COMPANY B>', m.group(0))), out)
    return out

class Simplifier:
    def __init__(self):
        self.openai_key = os.environ.get('OPENAI_API_KEY')
        self.hf_fallback = None
        if not self.openai_key:
            try:
                self.hf_fallback = hf_pipeline('text2text-generation', model='t5-small')
            except Exception:
                self.hf_fallback = None

    def simplify(self, original_text: str, constraints: Dict, attempt: int = 0,
                 party_overrides: Optional[Dict[str,str]] = None,
                 exclude_test_instructions: bool = True) -> str:
        constraint_lines = []
        if constraints.get('parties'):
            constraint_lines.append('Parties to preserve: ' + ', '.join(constraints['parties']))
        if constraints.get('amounts'):
            constraint_lines.append('Amounts to preserve: ' + ', '.join(constraints['amounts']))
        if constraints.get('deadlines'):
            constraint_lines.append('Deadlines to preserve: ' + ', '.join(constraints['deadlines']))
        if constraints.get('obligations'):
            constraint_lines.append('Obligation keywords: ' + ', '.join(sorted(set(constraints['obligations']))))

        overrides_text = ''
        if party_overrides:
            pairs = [f"{k} -> {v}" for k,v in party_overrides.items() if v]
            if pairs:
                overrides_text = 'Party substitutions (apply exactly): ' + '; '.join(pairs)

        instruction = (
            'Rewrite the following legal text into clear, precise plain English while PRESERVING all legally significant facts '
            '(parties, obligations, permissions, prohibitions, conditions, deadlines, and monetary amounts). '
            'Do NOT invent new facts. Do not remove or change dates/amounts/party names. '
            'Do NOT include internal test or instruction blocks (for example sections titled "Test Objective" or "Required Fact"). '
            'Always rephrase — do not return the original sentence verbatim unless no safe rephrasing exists.'
        )

        # Add a conservative example to bias the output style
        example = (
            'Example:\n'
            'Original: "The Receiving Party shall use the Confidential Information solely for the purpose of evaluating and negotiating the Proposed Transaction."\n'
            'Plain: "The Receiving Party may use the Confidential Information only to evaluate and negotiate the proposed transaction."\n\n'
        )

        prompt_parts = [instruction, example, 'Constraints to preserve:', '\n'.join(constraint_lines) if constraint_lines else 'None.', overrides_text if overrides_text else '', 'Original text:', original_text]
        prompt = '\n\n'.join([p for p in prompt_parts if p])

        output = None
        if self.openai_key:
            openai.api_key = self.openai_key
            try:
                response = openai.ChatCompletion.create(
                    model='gpt-3.5-turbo',
                    messages=[
                        {'role':'system','content':'You are an expert legal editor who rewrites legal clauses into plain English while preserving legal meaning. Be concise and precise.'},
                        {'role':'user','content':prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.1
                )
                output = response['choices'][0]['message']['content'].strip()
            except Exception:
                output = None

        if output is None and self.hf_fallback:
            try:
                payload = 'Simplify: ' + original_text[:2500]
                outputs = self.hf_fallback(payload, max_length=512, truncation=True)
                generated = outputs[0].get('generated_text') or outputs[0].get('summary_text') or ''
                output = textwrap.fill(generated, 100)
            except Exception:
                output = None

        if output is None:
            output = original_text

        if exclude_test_instructions:
            output = _strip_test_sections(output)
        output = _insert_parties(output, party_overrides)

        # If output is identical to input and we have no OpenAI, try a secondary paraphrase attempt
        if output.strip() == original_text.strip() and not self.openai_key and self.hf_fallback:
            try:
                payload = 'Paraphrase precisely: ' + original_text[:2000]
                outputs = self.hf_fallback(payload, max_length=512, truncation=True)
                alt = outputs[0].get('generated_text','')
                if alt and alt.strip() != original_text.strip():
                    output = alt
            except Exception:
                pass

        return output
