import calendar
from datetime import datetime, timedelta
from functools import partial

import gradio as gr
import numpy as np
import pandas as pd
from bokeh.io import curdoc
from bokeh.models import (ColumnDataSource, CustomJS, HoverTool, Label,
                          LinearColorMapper, Span, TapTool)
from bokeh.palettes import YlOrRd as palette
from bokeh.plotting import figure

from remind.database.mongodb import collection_query
from remind.domain.notes import Source
from remind.process_content.text_to_speech import \
    generate_audio_from_transcript

curdoc().theme = 'dark_minimal'


def create_activity_chart(year: int):
    # Generate data for the specified year
    start_date = datetime(year, 1, 1)
    days_in_year = 366 if calendar.isleap(year) else 365
    dates = [start_date + timedelta(days=x) for x in range(days_in_year)]

    # Retrieve all documents for the specified year from the "source" collection
    filter = {"created": {"$gte": datetime(year, 1, 1), "$lt": datetime(year + 1, 1, 1)}}
    documents = collection_query("source", filter)
    values = [0] * days_in_year
    note_cnt = [0] * days_in_year

    # Process each document to count topics per day
    for doc in documents:
        doc_date = doc['created'].date()
        day_of_year = (doc_date - start_date.date()).days
        if 0 <= day_of_year < days_in_year:
            values[day_of_year] += len(doc['topics'])
            note_cnt[day_of_year] += 1

    # Create DataFrame with proper week calculation
    data = {
        'date': dates,
        'value': values,
        'note_cnt': note_cnt,
        'weekday': [d.weekday() for d in dates],
        'month': [d.month for d in dates],
        'day': [d.day for d in dates],
        'date_str': [d.strftime('%Y-%m-%d') for d in dates],
        'day_name': [d.strftime('%A') for d in dates],
        'month_name': [d.strftime('%B') for d in dates]
    }
    df = pd.DataFrame(data)

    # Calculate the week number relative to the start of the year
    current_week = 0
    prev_month = 0
    week_numbers = []

    for _, row in df.iterrows():
        if row['month'] != prev_month:
            current_week += 1
            prev_month = row['month']
        if row['weekday'] == 0 and not (row['day'] == 1 and row['month'] == 1):
            current_week += 1
        week_numbers.append(current_week)

    df['week'] = week_numbers

    # Create ColumnDataSource
    source = ColumnDataSource(df)

    # Create color mapper
    colors = palette[6][::-1]
    mapper = LinearColorMapper(palette=colors, low=0, high=max(1, max(values)))

    # Create main figure
    p = figure(#title=f'Activity Calendar {year}',
        width=2400,
        height=250,
        x_range=(0.5, max(df['week']) + 0.5), y_range=(-0.5, 6.5),
        tools="hover,tap",
        toolbar_location=None,
    )

    # JavaScript callback for date capture
    tap_callback = CustomJS(args=dict(source=source), code="""
        const indices = cb_data.source.selected.indices;
        if (indices.length > 0) {
            const index = indices[0];
            const data = source.data;
            const clickedDate = data['date_str'][index];
            var gradioText = document.querySelector("#text_to_update textarea");
            if (gradioText && gradioText.value !== clickedDate) {
                gradioText.value = clickedDate;
                var event = new Event("input");
                gradioText.dispatchEvent(event);
            }
        }
    """)

    # Add rectangles for each day
    rect = p.rect(x='week', y='weekday',
                  width=0.9, height=0.9,
                  source=source,
                  fill_color={'field': 'value', 'transform': mapper},
                  line_color='white',
                  line_alpha=0.9,
                  hover_line_color="lime",
                  hover_line_width=3,
                  line_cap='round',
                  nonselection_alpha=1.0,
                  nonselection_line_alpha=1.0,
                  nonselection_fill_alpha=1.0)

    # Add TapTool with callback
    tap_tool = p.select_one(TapTool)
    tap_tool.callback = tap_callback

    # Enhanced hover tool
    hover = p.select_one(HoverTool)
    hover.tooltips = """
        <div style="background-color: #f0f0f0; padding: 5px; border-radius: 5px; box-shadow: 0px 0px 5px rgba(0,0,0,0.3);">
            <font size="2" style="background-color: #f0f0f0; padding: 5px; border-radius: 5px;">
                <i>Date:</i> <b>@date_str</b> <br>
                <i>Topics:</i> <b>@value</b> <br>
                <i>Notes: </i> <b>@note_cnt</b> <br>
            </font>
        </div>
        <style> :host { --tooltip-border: transparent;  --tooltip-color: transparent; --tooltip-text: #2f2f2f;} </style>
    """
    hover.attachment = 'left'
    hover.anchor = 'left'

    # Customize appearance
    p.axis.axis_line_color = None
    p.axis.major_tick_line_color = None
    p.axis.minor_tick_line_color = None
    p.grid.grid_line_color = None
    p.outline_line_color = None

    # Add weekday labels
    weekday_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    p.yaxis.ticker = list(range(7))
    p.yaxis.major_label_overrides = {i: day for i, day in enumerate(weekday_labels)}

    # Add month labels and separators
    month_weeks = {}
    for month in range(1, 13):
        month_data = df[df['month'] == month]
        if not month_data.empty:
            first_week = month_data['week'].min()
            last_week = month_data['week'].max()
            month_weeks[month] = (first_week + last_week) / 2

            if month > 1:
                separator = Span(location=first_week - 0.5, dimension='height',
                               line_color='#666666', line_width=1, line_alpha=0.3)
                p.add_layout(separator)

    month_positions = list(month_weeks.values())
    month_labels = [calendar.month_name[month] for month in month_weeks.keys()]

    p.xaxis.ticker = month_positions
    p.xaxis.major_label_overrides = {pos: label for pos, label in zip(month_positions, month_labels)}

    # Style the plot
    p.title.text_font_size = '16pt'
    p.title.text_font = 'helvetica'
    p.title.text_color = '#2b83ba'
    p.axis.axis_label = None
    p.axis.major_label_text_font_size = '9pt'
    p.axis.major_label_text_font_style = 'bold'

    # Add explanatory text
    p.add_layout(Label(
        x=-1, y=-1,
        text='Weekend',
        text_color='#666666',
        text_font_size='8pt'
    ))

    return p

def calendar_tab(demo, calendar_update):
    with gr.Tab("📅 Calendar"):
        with gr.Row():
            gr.Textbox("Year", container=False, scale=0, min_width=60)
            current_year = gr.Number(label="Year", container=False, min_width=80, scale=0)
            gr.Markdown()
        gr.Markdown("Click on a day in Calendar to see notes for that day.")
        calendar = gr.Plot(show_label=False)
        clicked_date = gr.Textbox(label="Clicked Date", elem_id="text_to_update", visible=False)
        demo.load(lambda: datetime.now().year, [], [current_year])
        current_year.change(create_activity_chart, inputs=[current_year], outputs=[calendar])
        calendar_update.change(create_activity_chart, inputs=[current_year], outputs=[calendar])

        @gr.render(inputs=[clicked_date], triggers=[clicked_date.change, calendar_update.change])
        def render_notes(date: str):
            # Display all notes for the clicked date in the activity chart
            if not date:
                return
            cur_date = datetime.strptime(date, "%Y-%m-%d")
            notes = collection_query("source", {"created": {"$gte": cur_date, "$lt": cur_date + timedelta(days=1)}})
            notes = [Source(**note) for note in notes]
            for note in notes:
                with gr.Accordion(note.title, open=False):
                    with gr.Accordion("Content", open=True):
                        gr.Markdown(note.full_text)
                        # Note to Audio
                        with gr.Row() as note_speak_button_row:
                            note_speak_button = gr.Button("Speak", scale=0)
                            gr.Markdown()
                        note_audio = gr.Audio(visible=False, streaming=True, autoplay=True)
                        note_speak_button.click(lambda: gr.Info("Generating Audio...", 5)).then(
                            lambda: (gr.Row(visible=False), gr.Audio(visible=True)), outputs=[note_speak_button_row, note_audio], show_progress=False
                        ).then(
                            partial(generate_audio_from_transcript, text=note.full_text), outputs=[note_audio]
                        )
                    for insight in note.insights:
                        with gr.Accordion(insight.insight_type, open=True):
                            gr.Markdown(insight.content)
                            # Insight to Audio
                            with gr.Row() as insight_speak_button_row:
                                insight_speak_button = gr.Button("Speak", scale=0)
                                gr.Markdown()
                            insight_audio = gr.Audio(visible=False, streaming=True, autoplay=True)
                            insight_speak_button.click(lambda: gr.Info("Generating Audio...", 5)).then(
                                lambda: (gr.Row(visible=False), gr.Audio(visible=True)), outputs=[insight_speak_button_row, insight_audio], show_progress=False
                            ).then(
                                partial(generate_audio_from_transcript, text=insight.content), outputs=[insight_audio]
                            )
                    if note.asset.file_path:
                        gr.Textbox(note.asset.file_path, label="File path", interactive=False)
                    elif note.asset.url:
                        gr.Textbox(note.asset.url, label="URL", interactive=False)
                    gr.Dropdown(note.topics, value=note.topics, multiselect=True, interactive=False, label="Topics")
                    with gr.Row():
                        note_delete_button = gr.Button("Delete")
                        note_delete_confirm_button = gr.Button("Confirm?", visible=False)
                    note_delete_button.click(lambda: gr.Button(visible=True), outputs=[note_delete_confirm_button])
                    note_delete_confirm_button.click(lambda note=note: note.delete()).then(lambda: gr.Info("Note deleted.", duration=2)).then(
                        lambda: datetime.now(), outputs=[calendar_update]
                    )
