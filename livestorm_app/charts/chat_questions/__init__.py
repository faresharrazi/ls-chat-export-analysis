from livestorm_app.charts.chat_questions.activity_timeline import render_activity_timeline_chart
from livestorm_app.charts.chat_questions.question_response_coverage import render_question_response_coverage_chart
from livestorm_app.charts.chat_questions.top_contributors import render_top_contributors_chart
from livestorm_app.charts.common import ChartSpec


CHAT_QUESTION_CHARTS = [
    ChartSpec("top_contributors", "Top Contributors", render_top_contributors_chart),
    ChartSpec("activity_timeline", "Activity Over Time", render_activity_timeline_chart),
    ChartSpec("question_response_coverage", "Question Response Coverage", render_question_response_coverage_chart),
]

DEFAULT_CHAT_QUESTION_CHART_KEYS = [chart.key for chart in CHAT_QUESTION_CHARTS]
