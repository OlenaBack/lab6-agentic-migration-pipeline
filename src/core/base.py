from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


NonEmptyText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
