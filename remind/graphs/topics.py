import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class TopicsState(TypedDict):
    input_text: str
    output: list[str]


def extract_json_from_string(input_string: str) -> dict:
    m = re.findall(r"```json\s*(\{.*?\})\s*```", input_string, re.DOTALL)
    if m:
        try:
            return json.loads(m[-1])
        except json.JSONDecodeError:
            return None
    return None

def run_topics(state: dict, config: RunnableConfig) -> dict:
    """ Generate tags for a given content. """
    content = state.get("input_text")
    assert content, "No content to transform"

    user_prompt = Prompter(prompt_template="topics").render(data=state)
    payload = [HumanMessage(content=user_prompt)]
    chain = provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "transformation",
        max_tokens=5000,
    )

    response = chain.invoke(payload)
    response_json = extract_json_from_string(response.content)
    topics = []
    if response_json and "tags" in response_json and isinstance(response_json["tags"], list):
        topics = response_json["tags"]

    return {
        "output": topics,
    }


agent_state = StateGraph(TopicsState)
agent_state.add_node("agent", run_topics)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)
graph = agent_state.compile()
