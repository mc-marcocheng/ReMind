from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class TitleState(TypedDict):
    input_text: str
    output: str


def run_title(state: dict, config: RunnableConfig) -> dict:
    """ Generate a title for the given content. """
    content = state.get("input_text")
    assert content, "No content to transform"

    system_prompt = Prompter(prompt_template="title").render(data=state)
    payload = [SystemMessage(content=system_prompt)] + [HumanMessage(content=content)]
    chain = provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "transformation",
        max_tokens=5000,
    )

    response = chain.invoke(payload)
    title = response.content
    title = title.strip().strip("'").strip('"').strip()
    return {
        "output": title,
    }


agent_state = StateGraph(TitleState)
agent_state.add_node("agent", run_title)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)
graph = agent_state.compile()
