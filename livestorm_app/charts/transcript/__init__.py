from livestorm_app.charts.common import ChartSpec
from livestorm_app.charts.transcript.clarity_score import render_clarity_score_chart
from livestorm_app.charts.transcript.cognitive_load import render_cognitive_load_chart
from livestorm_app.charts.transcript.confidence_distribution import render_confidence_distribution_chart
from livestorm_app.charts.transcript.engagement_score import render_engagement_score_chart
from livestorm_app.charts.transcript.filler_words import render_filler_words_chart
from livestorm_app.charts.transcript.interruptions import render_interruptions_chart
from livestorm_app.charts.transcript.named_entities import render_named_entities_chart
from livestorm_app.charts.transcript.pause_distribution import render_pause_distribution_chart
from livestorm_app.charts.transcript.replay_navigation import render_replay_navigation_chart
from livestorm_app.charts.transcript.response_time import render_response_time_chart
from livestorm_app.charts.transcript.sentence_length_distribution import render_sentence_length_distribution_chart
from livestorm_app.charts.transcript.silence_timeline import render_silence_timeline_chart
from livestorm_app.charts.transcript.speaker_airtime import render_speaker_airtime_chart
from livestorm_app.charts.transcript.speaker_turn_timeline import render_speaker_turn_timeline_chart
from livestorm_app.charts.transcript.speaking_burst import render_speaking_burst_chart
from livestorm_app.charts.transcript.speaking_pace import render_speaking_pace_chart
from livestorm_app.charts.transcript.top_keywords import render_top_keywords_chart
from livestorm_app.charts.transcript.topic_timeline import render_topic_timeline_chart


TRANSCRIPT_CHARTS = [
    ChartSpec("silence_timeline", "Silence Timeline", render_silence_timeline_chart),
    ChartSpec("speaking_pace", "Speaking Pace Over Time", render_speaking_pace_chart),
    ChartSpec("speaker_airtime", "Speaker Airtime Distribution", render_speaker_airtime_chart),
    ChartSpec("speaker_turns", "Speaker Turn Timeline", render_speaker_turn_timeline_chart),
    ChartSpec("pause_distribution", "Pause Distribution Histogram", render_pause_distribution_chart),
    ChartSpec("filler_words", "Filler Words Frequency", render_filler_words_chart),
    ChartSpec("sentence_length", "Sentence Length Distribution", render_sentence_length_distribution_chart),
    ChartSpec("confidence_distribution", "Confidence Score Distribution", render_confidence_distribution_chart),
    ChartSpec("engagement_score", "Engagement Score Over Time", render_engagement_score_chart),
    ChartSpec("speaking_burst", "Speaking Burst Analysis", render_speaking_burst_chart),
    ChartSpec("topic_timeline", "Topic Timeline", render_topic_timeline_chart),
    ChartSpec("named_entities", "Named Entities Chart", render_named_entities_chart),
    ChartSpec("top_keywords", "Top Keywords", render_top_keywords_chart),
    ChartSpec("interruptions", "Interruptions / Overlaps", render_interruptions_chart),
    ChartSpec("response_time", "Response Time Between Speakers", render_response_time_chart),
    ChartSpec("cognitive_load", "Cognitive Load Index", render_cognitive_load_chart),
    ChartSpec("clarity_score", "Clarity Score", render_clarity_score_chart),
    ChartSpec("replay_navigation", "Replay Navigation Map", render_replay_navigation_chart),
]

DEFAULT_TRANSCRIPT_CHART_KEYS = [
    "silence_timeline",
    "speaking_pace",
    "speaker_airtime",
    "pause_distribution",
    "engagement_score",
    "topic_timeline",
]
