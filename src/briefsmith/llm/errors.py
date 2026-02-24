"""LLM and structured-output error types."""


class StructuredOutputError(Exception):
    """Raised when structured JSON output cannot be validated after retries."""

    def __init__(
        self,
        message: str,
        *,
        last_raw_output: str = "",
        last_extracted_json: str | None = None,
        validation_error: str | None = None,
    ) -> None:
        super().__init__(message)
        self.last_raw_output = last_raw_output
        self.last_extracted_json = last_extracted_json
        self.validation_error = validation_error
