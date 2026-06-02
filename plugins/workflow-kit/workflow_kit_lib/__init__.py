"""workflow-kit: a declarative front-end to the native Claude Code Workflow tool.

A human authors a workflow as YAML; this library validates it and compiles it to a
native Workflow tool script (the JS that uses agent()/parallel()/pipeline()). The
skill then asks Claude to run that script via the Workflow tool.

Public surface:
    load_workflow(path) -> WorkflowDoc   (loader)
    compile_doc(doc)    -> str            (compiler; the JS script)
    WorkflowError                          (raised on any validation/compile error)
"""

from .errors import WorkflowError
from .model import WorkflowDoc
from .loader import load_workflow
from .compiler import compile_doc

__all__ = ["WorkflowError", "WorkflowDoc", "load_workflow", "compile_doc"]
