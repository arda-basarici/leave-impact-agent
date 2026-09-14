"""The prose models behind a request-shaped seam: the writer that turns a rendered request into
text and the checker that fills a forced tool over one, both over Bedrock's Converse API.

The adapter owns the Converse translation and nothing of prompt policy: what a request says,
which tool the checker is forced to call and what its input means are the generator's (the
step 14 rulings in DESIGN, "Materialization"). ``seam`` holds the request and answer types,
the two protocols and the closed fault vocabulary; ``bedrock`` the one translation under
both callers. The unit level runs the materializer over fakes of the two protocols and this
translation over botocore's stub; the real pair runs under the ``live`` marker and,
authoritatively, from the generator role in the probe workflow.
"""

from leaveimpact.adapters.prose import bedrock, seam
from leaveimpact.adapters.prose.bedrock import (
    UNREACHABLE_CODES,
    BedrockChecker,
    BedrockWriter,
    bedrock_client,
)
from leaveimpact.adapters.prose.seam import (
    CheckerRequest,
    InferenceConfiguration,
    ModelAccessRefused,
    ModelMisconfigured,
    ModelProtocolFault,
    ModelUnreachable,
    ProseChecker,
    ProseWriter,
    ToolCall,
    ToolSpec,
    Usage,
    WriterRequest,
    WrittenText,
)

__all__ = [
    "UNREACHABLE_CODES",
    "BedrockChecker",
    "BedrockWriter",
    "CheckerRequest",
    "InferenceConfiguration",
    "ModelAccessRefused",
    "ModelMisconfigured",
    "ModelProtocolFault",
    "ModelUnreachable",
    "ProseChecker",
    "ProseWriter",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "WriterRequest",
    "WrittenText",
    "bedrock",
    "bedrock_client",
    "seam",
]
