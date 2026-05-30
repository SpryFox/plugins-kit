"""Single error type for the whole pipeline.

Every validation, parse, and compile failure raises WorkflowError with a message
that names *where* in the document the problem is (e.g. "step 'review'.agent").
The CLI catches this one type and prints the message to stderr -- callers never
see a raw traceback for a user authoring mistake.
"""


class WorkflowError(Exception):
    """A workflow document is malformed, invalid, or cannot be compiled."""
