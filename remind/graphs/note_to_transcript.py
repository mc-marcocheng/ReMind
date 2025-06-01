from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class TranscriptState(TypedDict):
    content: str
    output: str


def convert_note_to_transcript(state: TranscriptState, config: RunnableConfig) -> dict:
    """ Convert note content to speakable transcript. """
    system_prompt = Prompter(prompt_template="note_to_transcript").render(data=state)
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("transcript_model"),
        "tools",
        max_tokens=5000,
    )
    ai_message = model.invoke(system_prompt)
    return {"output": ai_message.content}


agent_state = StateGraph(TranscriptState)
agent_state.add_node("agent", convert_note_to_transcript)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)

graph = agent_state.compile()
