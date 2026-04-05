from livestorm_app.charts.common import ChartSpec
from livestorm_app.charts.cross.content_pace_and_activity import render_content_pace_and_activity_chart


CROSS_CHARTS = [
    ChartSpec("content_pace_and_activity", "Content Pace And Audience Activity", render_content_pace_and_activity_chart),
]

DEFAULT_CROSS_CHART_KEYS = [chart.key for chart in CROSS_CHARTS]
