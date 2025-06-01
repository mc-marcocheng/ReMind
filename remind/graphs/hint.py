from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class HintState(TypedDict):
    content: str
    question: str
    model_answer: str
    output: str


def give_hint(state: HintState, config: RunnableConfig) -> dict:
    """ Give a hint for the current question based on the content. """
    system_prompt = Prompter(prompt_template="quiz/give_hint").render(data=state)
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("quiz_model"),
        "tools",
        max_tokens=2000,
    )
    ai_message = model.invoke(system_prompt)
    return {"output": ai_message.content}


agent_state = StateGraph(HintState)
agent_state.add_node("agent", give_hint)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)

graph = agent_state.compile()
