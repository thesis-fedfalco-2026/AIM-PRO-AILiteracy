"""Shared local authoring transport types, independent of model providers."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
