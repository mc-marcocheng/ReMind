from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class Correctness(BaseModel):
    is_correct: bool = Field(description="Whether the student answer is correct or not")


class JudgeState(TypedDict):
    content: str
    question: str
    model_answer: str
    answer: str
    output: Correctness


def judge_answer(state: JudgeState, config: RunnableConfig) -> dict:
    """ Judge whether the answer is correct or not based on the given model answer. """
    parser = PydanticOutputParser(pydantic_object=Correctness)
    system_prompt = Prompter(prompt_template="quiz/judge_answer", parser=parser).render(data=state)
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("quiz_model"),
        "tools",
        max_tokens=50,
    )
    ai_message = (model | parser).invoke(system_prompt)
    return {"output": ai_message}


agent_state = StateGraph(JudgeState)
agent_state.add_node("agent", judge_answer)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)

graph = agent_state.compile()
