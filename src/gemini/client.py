import os

from google import genai
from google.genai import types

from gemini import prompts
from gemini.model import LLMDecision, MatchResult
from model.product import Product
from model.submission import Submission

DEFAULT_MODEL_ID = "gemini-2.5-flash"


class Client:
    def __init__(self, api_key: str | None = None, model_id: str | None = None):
        self._client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
        self.model_id = model_id or os.environ.get("GEMINI_MODEL_ID") or DEFAULT_MODEL_ID

    def generate(
        self,
        submission: Submission,
        catalog: list[Product],
        producer_aliases: dict[str, str],
    ) -> MatchResult:
        system = prompts.system_instruction(catalog, producer_aliases)
        user = prompts.user_message(submission)
        response = self._client.models.generate_content(
            model=self.model_id,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=LLMDecision,
            ),
        )
        if response.parsed is None:
            raise RuntimeError(f"No parsed response for {submission.submission_id}")
        return MatchResult(
            decision=response.parsed,
            prompt_version=prompts.PROMPT_VERSION,
            output_text=response.text or "",
        )
