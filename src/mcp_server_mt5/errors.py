"""Safe operational errors exposed to MCP clients."""


class MT5Error(Exception):
    def __init__(
        self,
        message: str,
        error_code: int | None = None,
        *,
        kind: str = "mt5_error",
        operation_id: str | None = None,
        outcome_unknown: bool = False,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.kind = kind
        self.operation_id = operation_id
        self.outcome_unknown = outcome_unknown

    def payload(self) -> dict:
        return {
            "error": str(self),
            "error_code": self.error_code,
            "kind": self.kind,
            "operation_id": self.operation_id,
            "outcome_unknown": self.outcome_unknown,
        }
