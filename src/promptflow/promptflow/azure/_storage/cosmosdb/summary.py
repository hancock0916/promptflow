import datetime
import json
import typing
from dataclasses import asdict, dataclass

from promptflow._constants import SpanAttributeFieldName, SpanFieldName
from promptflow._sdk.entities._trace import Span
from promptflow.azure._storage.cosmosdb.client import get_client_with_workspace_info


@dataclass
class SummaryLine:
    """
    This class represents an Item in Summary container
    """

    partition_key: str
    session_id: str
    line_run_id: str
    trace_id: str
    root_span_id: str
    inputs: typing.Dict
    outputs: typing.Dict
    start_time: datetime.datetime
    end_time: datetime.datetime
    status: str
    latency: float
    name: str
    kind: str
    cumulative_token_count: typing.Optional[typing.Dict[str, int]]


@dataclass
class LineEvaluation:
    """
    This class represents an evaluation value in Summary container item.

    """

    line_run_id: str
    outputs: typing.Dict
    trace_id: str
    root_span_id: str
    display_name: str = ""
    flow_id: str = ""


class Summary:
    __container__ = "Summary"

    def __init__(self, span: Span) -> None:
        self.span = span

    def persist(self):
        if self.span.parent_span_id:
            # This is not the root span
            return
        attributes = self.span._content[SpanFieldName.ATTRIBUTES]
        client = get_client_with_workspace_info(self.__container__, attributes)
        if client is None:
            # This span is not associated with a workspace
            return

        # Persist span as a line run, since even evaluation is a line run, could be referenced by other evaluations.
        self._persist_line_run(client)

        if SpanAttributeFieldName.REFERENCED_LINE_RUN_ID in attributes:
            self._insert_evaluation()

    def _persist_line_run(self, client):
        attributes: dict = self.span._content[SpanFieldName.ATTRIBUTES]
        if SpanAttributeFieldName.LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
        else:
            # eager flow/arbitrary script
            line_run_id = self.span.trace_id
        session_id = self.span.session_id
        start_time = self.span._content[SpanFieldName.START_TIME]
        end_time = self.span._content[SpanFieldName.END_TIME]

        # Span's original format don't include latency, so we need to calculate it.
        # Convert ISO 8601 formatted strings to datetime objects
        start_time_date = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_time_date = datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        latency = (end_time_date - start_time_date).total_seconds()
        # calculate `cumulative_token_count`
        completion_token_count = int(attributes.get(SpanAttributeFieldName.COMPLETION_TOKEN_COUNT, 0))
        prompt_token_count = int(attributes.get(SpanAttributeFieldName.PROMPT_TOKEN_COUNT, 0))
        total_token_count = int(attributes.get(SpanAttributeFieldName.TOTAL_TOKEN_COUNT, 0))
        # if there is no token usage, set `cumulative_token_count` to None
        if total_token_count > 0:
            cumulative_token_count = {
                "completion": completion_token_count,
                "prompt": prompt_token_count,
                "total": total_token_count,
            }
        else:
            cumulative_token_count = None
        item = SummaryLine(
            partition_key=session_id,
            session_id=session_id,
            line_run_id=line_run_id,
            trace_id=self.span.trace_id,
            root_span_id=self.span.span_id,
            inputs=json.loads(attributes[SpanAttributeFieldName.INPUTS]),
            outputs=json.loads(attributes[SpanAttributeFieldName.OUTPUT]),
            start_time=start_time,
            end_time=end_time,
            status=self.span._content[SpanFieldName.STATUS],
            latency=latency,
            name=self.span.name,
            kind=attributes[SpanAttributeFieldName.SPAN_TYPE],
            cumulative_token_count=cumulative_token_count,
        )

        return client.create_item(body=asdict(item))

    def _insert_evaluation(self, client):
        attributes: dict = self.span._content[SpanFieldName.ATTRIBUTES]
        id = attributes[SpanAttributeFieldName.REFERENCED_LINE_RUN_ID]
        partition_key = self.span.session_id
        name = self.span.name
        if SpanAttributeFieldName.LINE_RUN_ID in attributes:
            line_run_id = attributes[SpanAttributeFieldName.LINE_RUN_ID]
        else:
            # eager flow/arbitrary script
            line_run_id = self.span.trace_id
        item = LineEvaluation(
            line_run_id=line_run_id,
            trace_id=self.span.trace_id,
            root_span_id=self.span.span_id,
            outputs=json.loads(attributes[SpanAttributeFieldName.OUTPUT]),
        )
        patch_operations = [{"op": "add", "path": f"/evaluations/{name}", "value": asdict(item)}]
        return client.patch_item(item=id, partition_key=partition_key, patch_operations=patch_operations)