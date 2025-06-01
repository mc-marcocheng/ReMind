import operator
from typing import Annotated, List

from langchain_core.output_parsers.pydantic import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from remind.database.mongodb import db_connection
from remind.domain.models import model_manager
from remind.domain.notes import Source, SourceEmbedding, SourceInsight
from remind.graphs.utils import provision_langchain_model
from remind.prompter import Prompter


class SubGraphState(TypedDict):
    question: str
    term: str
    instructions: str
    results: dict
    answer: str


class Search(BaseModel):
    term: str
    instructions: str = Field(
        description="Tell the answeting LLM what information you need extracted from this search"
    )


class Strategy(BaseModel):
    reasoning: str
    searches: List[Search] = Field(
        default_factory=list,
        description="You can add up to five searches to this strategy",
    )


class ThreadState(TypedDict):
    question: str
    strategy: Strategy
    answers: Annotated[list, operator.add]
    final_answer: str


def vector_search(
        keyword: str,
        results: int,
        source: bool = True,
        insights: bool = True,
        minimum_score: float = 0.2,
):
    """
    Perform a vector search in the database to find relevant documents.

    This function searches the 'source_embedding' and 'source_insight' collections
    within the database for documents that are similar to the given keyword by
    utilizing vector embeddings.

    Parameters:
    ----------
    keyword : str
        The term to search for in the database.
    results : int
        The maximum number of results to return for each collection.
    source : bool, optional
        Whether to search in the 'source_embedding' collection.
    insights : bool, optional
        Whether to search in the 'source_insight' collection.
    minimum_score : float, optional
        The minimum score threshold to consider a result as relevant. Only results
        with a score equal to or greater than this value will be returned.

    Returns:
    -------
    list
        A list of search results that exceed the minimum score threshold,
        composed of SourceEmbedding and SourceInsight objects.
    """
    if not keyword:
        return []

    EMBEDDING_MODEL = model_manager.embedding_model
    embed = EMBEDDING_MODEL.embed(keyword)
    search_results = []
    with db_connection() as db:
        if source:
            collection = db["source_embedding"]
            for result in collection.aggregate([
                {
                    '$vectorSearch': {
                        'index': 'vector_knn_index',
                        'path': 'embedding',
                        'queryVector': embed,
                        'numCandidates': 15 * results,
                        'limit': results,
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'content': 1,
                        'source_id': 1,
                        'updated': 1,
                        'created': 1,
                        'score': {
                            '$meta': 'vectorSearchScore'
                        }
                    }
                }
            ]):
                if result["score"] >= minimum_score:
                    score = result["score"]
                    del result["score"]
                    search_results.append((score, SourceEmbedding(**result)))

        if insights:
            collection = db["source_insight"]
            for result in collection.aggregate([
                {
                    '$vectorSearch': {
                        'index': 'vector_knn_index',
                        'path': 'embedding',
                        'queryVector': embed,
                        'numCandidates': 15 * results,
                        'limit': results,
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'insight_type': 1,
                        'content': 1,
                        'source_id': 1,
                        'updated': 1,
                        'created': 1,
                        'score': {
                            '$meta': 'vectorSearchScore'
                        }
                    }
                }
            ]):
                if result["score"] >= minimum_score:
                    score = result["score"]
                    del result["score"]
                    search_results.append((score, SourceInsight(**result)))

    search_results.sort(key=lambda x: x[0], reverse=True)
    search_results = [result[1] for result in search_results[:results]]
    return search_results


async def call_model_with_messages(state: ThreadState, config: RunnableConfig) -> dict:
    """ Plan the note search. """
    parser = PydanticOutputParser(pydantic_object=Strategy)
    system_prompt = Prompter(prompt_template="ask/entry", parser=parser).render(
        data=state
    )
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("strategy_model"),
        "tools",
        max_tokens=2000,
    )
    ai_message = (model | parser).invoke(system_prompt)
    return {"strategy": ai_message}


async def trigger_queries(state: ThreadState, config: RunnableConfig):
    return [
        Send(
            "provide_answer",
            {
                "question": state["question"],
                "instructions": s.instructions,
                "term": s.term,
            },
        )
        for s in state["strategy"].searches
    ]


async def provide_answer(state: SubGraphState, config: RunnableConfig) -> dict:
    """ Answer to the instruction based on search results. """
    payload = state
    results = vector_search(state["term"], 10, True, True)
    if len(results) == 0:
        return {"answers": []}
    payload_result = []
    payload_ids = []
    for result in results:
        if isinstance(result, SourceEmbedding):
            id_type = "note"
        elif isinstance(result, SourceInsight):
            id_type = "insight"
        payload_id = id_type + ":" + str(result.id)
        payload_result.append({"id": payload_id, "content": result.content})
        payload_ids.append(payload_id)

    payload["results"] = payload_result
    payload["ids"] = payload_ids
    system_prompt = Prompter(prompt_template="ask/query_process").render(data=payload)

    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("answer_model"),
        "tools",
        max_tokens=2000,
    )
    ai_message = model.invoke(system_prompt)
    return {"answers": [ai_message.content]}

async def write_final_answer(state: ThreadState, config: RunnableConfig) -> dict:
    """ Answer to the question based on instruction answers. """
    system_prompt = Prompter(prompt_template="ask/final_answer").render(data=state)
    model = provision_langchain_model(
        system_prompt,
        config.get("configurable", {}).get("final_answer_model"),
        "tools",
        max_tokens=2000,
    )
    ai_message = model.invoke(system_prompt)
    return {"final_answer": ai_message.content}


agent_state = StateGraph(ThreadState)
agent_state.add_node("agent", call_model_with_messages)
agent_state.add_node("provide_answer", provide_answer)
agent_state.add_node("write_final_answer", write_final_answer)
agent_state.add_edge(START, "agent")
agent_state.add_conditional_edges("agent", trigger_queries, ["provide_answer"])
agent_state.add_edge("provide_answer", "write_final_answer")
agent_state.add_edge("write_final_answer", END)

graph = agent_state.compile()
