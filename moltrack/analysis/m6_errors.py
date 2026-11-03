class M6BlockingGraphQCError(ValueError):
    """Raised when domain construction cannot trust the first-shell graph."""

    def __init__(self, qc_status: str) -> None:
        self.qc_status = str(qc_status)
        super().__init__(
            f"first_shell_graph has blocking QC ({self.qc_status}) "
            "and cannot construct domains."
        )
