"""Content-free validation diagnostics shared by generation and its durable queue."""


class SummaryValidationError(ValueError):
    """Only fixed local codes may reach logs; never include provider content."""

    CODES = frozenset({
        'missing_choice', 'unfinished_response', 'empty_content', 'invalid_json',
        'unexpected_fields', 'summary_type', 'empty_summary', 'summary_too_long',
        'dispatch_log',
    })

    def __init__(self, code):
        if code not in self.CODES:
            raise ValueError('Unknown summary validation code')
        self.code = code
        super().__init__(code)


def safe_error_code(error):
    if isinstance(error, SummaryValidationError):
        return 'validation:' + error.code
    # Provider exception messages can contain request bodies or credentials.
    return type(error).__name__
