from typing import Optional

import gradio as gr

from remind.domain.notes import Source
from remind.graphs.quiz import QuestionAnswer
from remind.process_content.get_quiz import (get_hint, get_next_quiz_note,
                                             get_quiz_question_answer_pairs,
                                             judge_correctness,
                                             save_quizzed_note)


def get_next_question(note, question_idx, question_answer_pairs: list[QuestionAnswer]):
    # Get the next note if note is None or there are no more questions in the current note
    if note is None or question_idx == len(question_answer_pairs):
        while True:
            if note is not None and question_idx == len(question_answer_pairs):
                # no more questions in this note, save as quizzed
                save_quizzed_note(note)
            note = get_next_quiz_note()
            if note is None:
                return (
                    gr.Button(visible=True),
                    gr.Markdown(visible=True),
                    gr.Group(visible=False),
                    gr.Group(visible=False),
                    gr.Button(visible=False),
                    gr.Accordion(visible=False),
                    None,
                    0,
                    [],
                    None,
                    None,
                    None,
                )
            question_answer_pairs = get_quiz_question_answer_pairs(source=note)
            if question_answer_pairs:
                question_idx = 0
                break
    # Get the current question and model answer
    question_answer_pair = question_answer_pairs[question_idx]
    return (
        gr.Button(visible=False),       # start_quiz_button
        gr.Markdown(visible=False),     # completed_quiz_markdown
        gr.Group(visible=True),         # question_answer_group
        gr.Group(visible=False),        # judged_group
        gr.Button(visible=True),        # get_hint_button
        gr.Accordion(visible=False),    # hint_display_accordion
        note,                           # cur_note
        question_idx + 1,               # cur_question_idx
        question_answer_pairs,          # cur_question_answer_pairs
        question_answer_pair.question,  # question_text
        question_answer_pair.answer,    # model_answer
        None,                           # answer_text
    )

def judge_answer(note: Source, question: str, answer: str, model_answer: str):
    if not answer.strip():
        is_correct = False
    else:
        is_correct = judge_correctness(note, question, answer, model_answer)
    if is_correct:
        judge_display = "✔️ Correct!"
    else:
        judge_display = "❌ Incorrect!"

    return gr.Group(visible=True), judge_display

def quiz_tab():
    with gr.Tab("📋 Quiz"):
        cur_note = gr.State()
        cur_question_idx = gr.State(0)
        cur_question_answer_pairs = gr.State([])

        start_quiz_button = gr.Button("Start Quiz")
        completed_quiz_markdown = gr.Markdown("You have completed the quiz. Come back tomorrow!", visible=False)

        with gr.Row():
            # Note and Hint column
            with gr.Column():
                @gr.render(inputs=[cur_note])
                def render_notes(note: Optional[Source]):
                    if not note:
                        return
                    with gr.Accordion(note.title, open=False):
                        with gr.Accordion("Content", open=True):
                            gr.Markdown(note.full_text)
                        for insight in note.insights:
                            with gr.Accordion(insight.insight_type, open=True):
                                gr.Markdown(insight.content)

                get_hint_button = gr.Button("Get Hint", visible=False)
                with gr.Accordion("Hint", open=True, visible=False) as hint_display_accordion:
                    hint_display = gr.Markdown()

            # Quiz and Judge column
            with gr.Column():
                with gr.Group(visible=False) as question_answer_group:
                    model_answer = gr.State()
                    question_text = gr.Textbox(label="Question", interactive=False)
                    answer_text = gr.TextArea(label="Answer")
                    submit_button = gr.Button("Submit")
                with gr.Group(visible=False) as judged_group:
                    judged_display = gr.Markdown()
                    with gr.Accordion("Model Answer", open=True):
                        model_answer = gr.Markdown()
                    next_question_button = gr.Button("Next Question")


        start_quiz_button.click(
            lambda: gr.Info("Starting...", duration=5),
        ).then(lambda: gr.Button("Loading...", interactive=False), outputs=[start_quiz_button]).then(
            get_next_question,
            inputs=[cur_note, cur_question_idx, cur_question_answer_pairs],
            outputs=[
                start_quiz_button,
                completed_quiz_markdown,
                question_answer_group,
                judged_group,
                get_hint_button,
                hint_display_accordion,
                cur_note,
                cur_question_idx,
                cur_question_answer_pairs,
                question_text,
                model_answer,
                answer_text,
            ]
        ).then(lambda: gr.Button("Start Quiz", interactive=True), outputs=[start_quiz_button])

        get_hint_button.click(
            lambda: gr.Info("Loading hint...", duration=2),
        ).then(
            get_hint,
            inputs=[cur_note, question_text, model_answer],
            outputs=[hint_display],
        ).then(lambda: (gr.Accordion(visible=True), gr.TextArea(visible=True)), outputs=[hint_display_accordion, hint_display])

        submit_button.click(
            lambda: gr.Info("Judging...", duration=2),
        ).then(
            judge_answer,
            inputs=[cur_note, question_text, answer_text, model_answer],
            outputs=[judged_group, judged_display],
        )

        next_question_button.click(
            lambda: gr.Info("Loading...", duration=5),
        ).then(lambda: gr.Button(interactive=False), outputs=[next_question_button]).then(
            get_next_question,
            inputs=[cur_note, cur_question_idx, cur_question_answer_pairs],
            outputs=[
                start_quiz_button,
                completed_quiz_markdown,
                question_answer_group,
                judged_group,
                get_hint_button,
                hint_display_accordion,
                cur_note,
                cur_question_idx,
                cur_question_answer_pairs,
                question_text,
                model_answer,
                answer_text,
            ]
        ).then(lambda: gr.Button(interactive=True), outputs=[next_question_button])
