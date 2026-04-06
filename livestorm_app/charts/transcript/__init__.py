from livestorm_app.charts.common import ChartSpec
from livestorm_app.charts.transcript.global_wpm import render_global_wpm_chart
from livestorm_app.charts.transcript.pause_distribution import render_pause_distribution_chart
from livestorm_app.charts.transcript.silence_timeline import render_silence_timeline_chart
from livestorm_app.charts.transcript.speaker_airtime import render_speaker_airtime_chart
from livestorm_app.charts.transcript.speaker_changes_timeline import render_speaker_changes_timeline_chart
from livestorm_app.charts.transcript.speaker_turn_timeline import render_speaker_turn_timeline_chart
from livestorm_app.charts.transcript.speaking_burst_duration import render_speaking_burst_duration_chart
from livestorm_app.charts.transcript.speaking_pace import render_speaking_pace_chart
from livestorm_app.charts.transcript.utterance_duration_distribution import render_utterance_duration_distribution_chart
from livestorm_app.charts.transcript.words_over_time import render_words_over_time_chart
from livestorm_app.charts.transcript.words_per_speaker import render_words_per_speaker_chart


PAUSE_TRANSCRIPT_CHARTS = [
    ChartSpec("pause_distribution", "Pause Histogram", render_pause_distribution_chart),
    ChartSpec("silence_timeline", "Pause Timeline", render_silence_timeline_chart),
]

PACE_TRANSCRIPT_CHARTS = [
    ChartSpec("global_wpm", "Words Per Minute (Global)", render_global_wpm_chart),
    ChartSpec("speaking_pace", "Words Per Minute Over Time", render_speaking_pace_chart),
]

SPEAKER_TRANSCRIPT_CHARTS = [
    ChartSpec("speaker_airtime", "Pie Chart Per Speaker", render_speaker_airtime_chart),
    ChartSpec("speaker_timeline", "Timeline Per Speaker", render_speaker_turn_timeline_chart),
]

TURN_TRANSCRIPT_CHARTS = [
    ChartSpec("speaker_changes_timeline", "Timeline Of Speaker Changes", render_speaker_changes_timeline_chart),
]

UTTERANCE_DURATION_TRANSCRIPT_CHARTS = [
    ChartSpec("utterance_duration_distribution", "Distribution Of Utterance Length", render_utterance_duration_distribution_chart),
]

WORD_COUNT_TRANSCRIPT_CHARTS = [
    ChartSpec("words_per_speaker", "Words Per Speaker", render_words_per_speaker_chart),
    ChartSpec("words_over_time", "Words Over Time", render_words_over_time_chart),
]

BURST_TRANSCRIPT_CHARTS = [
    ChartSpec("speaking_burst_duration", "Speaking Duration Before Pause", render_speaking_burst_duration_chart),
]

TRANSCRIPT_CHART_CATEGORIES = [
    ("Silence / Pause Metrics", PAUSE_TRANSCRIPT_CHARTS),
    ("Speaking Pace", PACE_TRANSCRIPT_CHARTS),
    ("Speaker Airtime", SPEAKER_TRANSCRIPT_CHARTS),
    ("Speaker Turns", TURN_TRANSCRIPT_CHARTS),
    ("Utterance Duration", UTTERANCE_DURATION_TRANSCRIPT_CHARTS),
    ("Words Count", WORD_COUNT_TRANSCRIPT_CHARTS),
    ("Speaking Segments", BURST_TRANSCRIPT_CHARTS),
]
