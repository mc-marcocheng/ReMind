from datetime import datetime, timedelta
from typing import Optional

from remind.database.mongodb import collection_query
from remind.domain.notes import Source
from remind.domain.quiz import Quizzed
from remind.graphs.hint import graph as hint_graph
from remind.graphs.judge import graph as judge_graph
from remind.graphs.quiz import QuestionAnswer, QuestionAnswerList
from remind.graphs.quiz import graph as quiz_graph


def get_today_quizzed() -> Quizzed:
    """ Get the quizzed notes of today. """
    quizzed = collection_query("quiz", filter={"created": {"$gte": datetime.combine(datetime.now().date(), datetime.min.time())}})
    if quizzed:
        return Quizzed(**quizzed[-1])
    return Quizzed(quizzed=[])

def get_next_quiz_note() -> Optional[Source]:
    """ Get the next note to quiz. Each note is quizzed after 2, 7, 30 days from its creation. """
    now = datetime.now()
    date_threshold = now - timedelta(days=60)
    all_quizzed = collection_query("quiz", filter={"created": {"$gte": date_threshold}})

    note_quizzed_cnt = {}
    for quizzed in all_quizzed:
        for note_id in quizzed["quizzed"]:
            note_id = str(note_id)
            note_quizzed_cnt[note_id] = note_quizzed_cnt.get(note_id, 0) + 1

    all_sources = collection_query("source", filter={"created": {"$gte": date_threshold}})
    today_quizzed = get_today_quizzed()
    for source in all_sources:
        if source["_id"] in today_quizzed:
            # Skip notes that are already quizzed today
            continue
        source_id = str(source["_id"])
        quizzed_cnt = note_quizzed_cnt.get(source_id, 0)
        if now - source["created"] > timedelta(days=30) and quizzed_cnt < 3:
            return Source(**source)
        if now - source["created"] > timedelta(days=7) and quizzed_cnt < 2:
            return Source(**source)
        if now - source["created"] > timedelta(days=2) and quizzed_cnt < 1:
            return Source(**source)
    return None

def get_quiz_question_answer_pairs(source: Source) -> list[QuestionAnswer]:
    """ Get the question and model answer pairs from a note. """
    question_answer_pairs: QuestionAnswerList = quiz_graph.invoke({"content": source.full_text})["question_answer_pairs"]
    return question_answer_pairs.question_answer_pairs

def save_quizzed_note(note: Source):
    """ Save a note as quizzed today. """
    quizzed = get_today_quizzed()
    if note.id in quizzed.quizzed:
        return
    quizzed.quizzed.append(note.id)
    quizzed.save()


def judge_correctness(note: Source, question: str, answer: str, model_answer: str) -> bool:
    """ Judge the correctness of an answer. """
    return judge_graph.invoke(
        {
            "content": note.full_text,
            "question": question,
            "answer": answer,
            "model_answer": model_answer,
        }
    )["output"].is_correct

def get_hint(note: Source, question: str, model_answer: str) -> str:
    """ Get a hint for the current question. """
    return hint_graph.invoke(
        {
            "content": note.full_text,
            "question": question,
            "model_answer": model_answer,
        }
    )["output"]
