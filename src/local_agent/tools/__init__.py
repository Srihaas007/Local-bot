from .base import Tool, ToolResult
from .file_tools import ReadFile, WriteFile, ListFiles
from .shell_tool import ShellRun
from .web_fetch import WebFetch
from .run_python import RunPython
from .git_ops import GitOps
from .generated.text_to_speech import TextToSpeechTool  # explicit to guarantee availability
from .generated.speech_to_text import SpeechToTextTool

# Try to import any generated tools installed by the SkillManager.
try:  # pragma: no cover
    from .generated import *  # type: ignore
except Exception:
    pass

__all__ = [
    "Tool",
    "ToolResult",
    "ReadFile",
    "WriteFile",
    "ListFiles",
    "ShellRun",
    "WebFetch",
    "RunPython",
    "GitOps",
    "TextToSpeechTool",
    "SpeechToTextTool",
]
