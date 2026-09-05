from dataclasses import dataclass
from typing import Any


@dataclass
class GeminiServiceException(Exception):
    code: str
    message: str


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise GeminiServiceException(
                "MISSING_GEMINI_API_KEY", "Gemini API key is not configured."
            )
        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        except Exception as error:
            raise GeminiServiceException(
                "GEMINI_CLIENT_ERROR", "Unable to initialize the Gemini client."
            ) from error
        return self._client

    def generate(self, prompt: str) -> str:
        try:
            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            answer = getattr(response, "text", None)
        except GeminiServiceException:
            raise
        except Exception as error:
            raise GeminiServiceException(
                "GEMINI_REQUEST_FAILED", "Gemini could not generate an answer."
            ) from error
        if not isinstance(answer, str) or not answer.strip():
            raise GeminiServiceException(
                "MALFORMED_GEMINI_RESPONSE", "Gemini returned an empty answer."
            )
        return answer.strip()