from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class QuestionAnswer(BaseModel):
    question: str = Field(description="Question to be answered")
    answer: str = Field(description="Model answer to the question")

class QuestionAnswerList(BaseModel):
    question_answer_pairs: list[QuestionAnswer]

class QuizState(TypedDict):
    content: str
    question_answer_raw: str
    question_answer_pairs: QuestionAnswerList


def question_answer_raw(state: QuizState, config: RunnableConfig) -> dict:
    """ Get question and answer pairs for a given content in raw text form. """
    system_prompt = Prompter(prompt_template="quiz/question_ans_raw").render(data=state)
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("quiz_model"),
        "tools",
        max_tokens=5000,
    )
    ai_message = model.invoke(system_prompt)
    return {"question_answer_raw": ai_message.content}

def question_answer_json(state: QuizState, config: RunnableConfig) -> dict:
    """ Format question_answer_raw into a list of QuestionAnswer objects. """
    parser = PydanticOutputParser(pydantic_object=QuestionAnswerList)
    system_prompt = Prompter(prompt_template="quiz/qa_json_convert", parser=parser).render(
        data=state
    )
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("quiz_model"),
        "tools",
        max_tokens=5000,
    )
    ai_message = (model | parser).invoke(system_prompt)
    return {"question_answer_pairs": ai_message}

agent_state = StateGraph(QuizState)
agent_state.add_node("agent", question_answer_raw)
agent_state.add_node("final_json", question_answer_json)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", "final_json")
agent_state.add_edge("final_json", END)

graph = agent_state.compile()
