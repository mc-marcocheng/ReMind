import re
import time

import gradio as gr
from bson import ObjectId

from remind.database.mongodb import collection_query
from remind.domain.models import DefaultModels, model_manager
from remind.domain.notes import Source, SourceEmbedding, SourceInsight
from remind.graphs.ask import graph as ask_graph
from remind.webui.components.model_selector import (get_model_from_key,
                                                    model_selector)


def add_user_query(history, user_query):
    if not history:
        history = []
    return history + [{"role": "user", "content": user_query}], ""

def convert_source_references(text: str):
    # Convert references such as [note:123] to [1] and the actual content.
    pattern = r"\[((?:insight|note|source):[\w\d]+)\]"
    references = set(re.findall(pattern, text))
    reference_objs = []
    replaced_references = []
    for reference in references:
        reference_split = reference.split(":", 1)
        if len(reference_split) != 2:
            continue
        source_type, source_id = reference_split
        if source_type == "insight":
            insight = collection_query("source_insight", {"_id": ObjectId(source_id)})
            if not insight:
                continue
            insight = SourceInsight(**insight[0])
            reference_objs.append(insight)
            text = text.replace(reference, str(len(reference_objs)))
            replaced_references.append(reference)
        elif source_type == "note":
            note = collection_query("source_embedding", {"_id": ObjectId(source_id)})
            if not note:
                continue
            note = SourceEmbedding(**note[0])
            reference_objs.append(note)
            text = text.replace(reference, str(len(reference_objs)))
            replaced_references.append(reference)
        elif source_type == "source":
            source = collection_query("source", {"_id": ObjectId(source_id)})
            if not source:
                continue
            source = Source(**source[0])
            reference_objs.append(source)
            text = text.replace(reference, str(len(reference_objs)))
            replaced_references.append(reference)
    return text, reference_objs, replaced_references

async def process_ask_query(history, strategy_model, answer_model, final_answer_model):
    question = history[-1]["content"]
    strategy_model_id = get_model_from_key(strategy_model, "language").id
    answer_model_id = get_model_from_key(answer_model, "language").id
    final_answer_model_id = get_model_from_key(final_answer_model, "language").id

    # Thinking... spinner
    thinking_id = str(time.time())
    assistant_messages = [gr.ChatMessage(role="assistant", content="", metadata={"title": "Thinking...", "id": thinking_id, "status": "pending"})]
    yield history + assistant_messages

    async for chunk in ask_graph.astream(
        input=dict(
            question=question,
        ),
        config=dict(
            configurable=dict(
                strategy_model=strategy_model_id,
                answer_model=answer_model_id,
                final_answer_model=final_answer_model_id,
            )
        ),
        stream_mode="updates",
    ):
        # Search plan
        if "agent" in chunk:
            for search in chunk["agent"]["strategy"].searches:
                assistant_messages.append(gr.ChatMessage(role="assistant", content=search.instructions, metadata={"title": "Search: " + search.term, "parent_id": thinking_id}))
        # Search results and answers
        elif "provide_answer" in chunk:
            for answer in chunk["provide_answer"]["answers"]:
                assistant_messages.append(gr.ChatMessage(role="assistant", content=answer, metadata={"title": "Search Result", "parent_id": thinking_id}))
        # Final answer
        elif "write_final_answer" in chunk:
            final_answer = chunk["write_final_answer"]["final_answer"]
            # Convert source references in search answers and final answer to [int]
            final_answer, reference_objs, replaced_references = convert_source_references(final_answer)
            for msg in assistant_messages:
                for i, reference in enumerate(replaced_references, 1):
                    msg.content = msg.content.replace(reference, str(i))
            assistant_messages.append(gr.ChatMessage(role="assistant", content=final_answer))
            # Display citations
            if reference_objs:
                assistant_messages.append(gr.ChatMessage(role="assistant", content="", metadata={"title": "📑 Citations", "id": thinking_id + "_cite", "status": "done"}))
                for i, reference in enumerate(reference_objs, 1):
                    if isinstance(reference, SourceEmbedding):
                        source = reference.source
                        source_content_display = f"**Title**: {source.title}\n**Date**: {source.created.strftime('%Y-%m-%d')}\n**Type**: Full Text\n**Content**:\n{source.full_text}"
                    elif isinstance(reference, SourceInsight):
                        source = reference.source
                        source_content_display = f"**Title**: {source.title}\n**Date**: {source.created.strftime('%Y-%m-%d')}\n**Type**: Insight ({reference.insight_type})\n**Content**:\n{reference.content}"
                    elif isinstance(reference, Source):
                        source_content_display = f"**Title**: {reference.title}\n**Date**: {reference.created.strftime('%Y-%m-%d')}\n**Type**: Full Text\n**Content**:\n{reference.full_text}"
                    assistant_messages.append(gr.ChatMessage(role="assistant", content=source_content_display, metadata={"title": f"Source [{i}]", "parent_id": thinking_id + "_cite"}))
            # Update the tool title
            assistant_messages[0] = gr.ChatMessage(role="assistant", content="", metadata={"title": "🧠 Thoughts", "id": thinking_id, "status": "done"})
        yield history + assistant_messages

def ask_tab(all_models):
    with gr.Tab("🤔 Ask"):
        @gr.render(triggers=[all_models.change])
        def render_chatbot():
            default_model = DefaultModels().default_chat_model
            with gr.Accordion("Select Chat Models", open=False):
                strategy_model = model_selector(
                    label="Query Strategy Model",
                    selected_id=default_model,
                    model_type="language",
                    info="This is the LLM that will be responsible for strategizing the search",
                )
                answer_model = model_selector(
                    label="Individual Answer Model",
                    selected_id=default_model,
                    model_type="language",
                    info="This is the LLM that will be responsible for processing individual subqueries",
                )
                final_answer_model = model_selector(
                    label="Final Answer Model",
                    selected_id=default_model,
                    model_type="language",
                    info="This is the LLM that will be responsible for processing the final answer",
                )
            if not model_manager.embedding_model:
                gr.Markdown("No embedding model selected. Please set one up in the Models page.")
            else:
                chatbot = gr.Chatbot(type="messages", label="Teacher", height="75vh")
                user_query = gr.Textbox(container=False)
                user_query.submit(
                    add_user_query,
                    inputs=[chatbot, user_query],
                    outputs=[chatbot, user_query],
                    show_progress=False,
                ).then(
                    process_ask_query,
                    inputs=[chatbot, strategy_model, answer_model, final_answer_model],
                    outputs=[chatbot],
                )
