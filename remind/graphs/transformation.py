import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from remind.domain.notes import Source
from remind.domain.transformation import DefaultPrompts, Transformation
from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class TransformationState(TypedDict):
    input_text: str
    source: Source
    transformation: Transformation
    output: str

def extract_markdown_from_string(input_string: str) -> dict:
    m = re.findall(r"```markdown\s*(.*?)\s*```", input_string, re.DOTALL)
    if len(m) == 1:
        return m[0]
    return input_string

def run_transformation(state: dict, config: RunnableConfig) -> dict:
    """ Transform a given content into another form based on a prompt. """
    source: Source = state.get("source")
    content = state.get("input_text")
    assert source or content, "No content to transform"
    transformation: Transformation = state["transformation"]
    if not content:
        content = source.full_text
    transformation_prompt_text = transformation.prompt
    default_prompts: DefaultPrompts = DefaultPrompts()
    if default_prompts.transformation_instructions:
        transformation_prompt_text = f"{default_prompts.transformation_instructions}\n\n{transformation_prompt_text}"

    transformation_prompt_text = f"{transformation_prompt_text}\n\n# INPUT"

    system_prompt = Prompter(prompt_text=transformation_prompt_text).render(data=state)
    payload = [SystemMessage(content=system_prompt)] + [HumanMessage(content=content)]
    chain = provision_langchain_model(
        str(payload),
        config.get("configurable", {}).get("model_id"),
        "transformation",
        max_tokens=5000,
    )

    response = chain.invoke(payload)
    if source:
        source.add_insight(transformation.title, response.content)
    output = extract_markdown_from_string(response.content)
    return {
        "output": output,
    }


agent_state = StateGraph(TransformationState)
agent_state.add_node("agent", run_transformation)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)
graph = agent_state.compile()
