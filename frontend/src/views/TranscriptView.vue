<script setup>
import { computed, reactive, ref, watch } from "vue";
import BarChartCard from "../components/BarChartCard.vue";
import DataTable from "../components/DataTable.vue";
import HistogramChartCard from "../components/HistogramChartCard.vue";
import PaceOverTimeChartCard from "../components/PaceOverTimeChartCard.vue";
import SpeakerShareChartCard from "../components/SpeakerShareChartCard.vue";
import SpeakerTimelineChartCard from "../components/SpeakerTimelineChartCard.vue";
import SpeakerTurnsTimelineChartCard from "../components/SpeakerTurnsTimelineChartCard.vue";
import SpeakingBurstChartCard from "../components/SpeakingBurstChartCard.vue";
import TimelinePauseChartCard from "../components/TimelinePauseChartCard.vue";
import WordsOverTimeChartCard from "../components/WordsOverTimeChartCard.vue";
import { useWorkspace } from "../store/workspace";

const { state, saveSpeakerLabels } = useWorkspace();
const speakerNames = reactive({});
const activeTab = ref("transcript");
const showSpeakerEditor = ref(false);
const transcriptSearch = ref("");

function mapSpeakerLabel(value) {
  const key = String(value || "").trim();
  return speakerNames[key] || key;
}

async function handleSaveSpeakerLabels() {
  await saveSpeakerLabels(speakerNames);
  showSpeakerEditor.value = false;
}

function downloadCsv(filename, rows) {
  if (!rows?.length) return;
  const columns = Object.keys(rows[0]);
  const escapeCell = (value) => {
    const text = String(value ?? "");
    if (/[",\n]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };
  const csv = [
    columns.join(","),
    ...rows.map((row) => columns.map((column) => escapeCell(row?.[column])).join(",")),
  ].join("\n");
  downloadBlob(filename, csv, "text/csv;charset=utf-8;");
}

function downloadBlob(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadTranscriptJson() {
  const transcriptPayload = state.workspace?.payloads?.transcript;
  if (!transcriptPayload) return;
  const sessionId = state.workspace?.sessionId || "session";
  downloadBlob(
    `livestorm-transcript-${sessionId}.json`,
    JSON.stringify(transcriptPayload, null, 2),
    "application/json;charset=utf-8;",
  );
}

watch(
  () => state.workspace?.speakerNames,
  (nextNames) => {
    const normalized = nextNames || {};
    for (const key of Object.keys(speakerNames)) {
      if (!(key in normalized)) delete speakerNames[key];
    }
    Object.assign(speakerNames, normalized);
  },
  { immediate: true },
);

const transcriptText = computed(() => state.workspace?.text?.transcriptDisplay || "");
const transcriptPayload = computed(() => state.workspace?.payloads?.transcript || null);
const transcriptSegments = computed(() => state.workspace?.tables?.transcriptSegments || []);
const transcriptKeyMoments = computed(() => state.workspace?.tables?.transcriptKeyMoments || []);
const transcriptSpeakers = computed(() => state.workspace?.tables?.transcriptSpeakers || []);
const transcriptSpeakerTurns = computed(() => state.workspace?.tables?.transcriptSpeakerTurns || []);
const transcriptPace = computed(() => state.workspace?.tables?.transcriptPace || []);
const transcriptNumbers = computed(() => state.workspace?.tables?.transcriptNumbers || []);
const transcriptSilence = computed(() => state.workspace?.tables?.transcriptSilence || []);
const transcriptPauseTypes = computed(() => state.workspace?.tables?.transcriptPauseTypes || []);
const transcriptPauseDistribution = computed(() => state.workspace?.tables?.transcriptPauseDistribution || []);
const transcriptUtteranceDistribution = computed(() => state.workspace?.tables?.transcriptUtteranceDistribution || []);
const transcriptTimeline = computed(() => state.workspace?.tables?.transcriptTimeline || []);
const transcriptBursts = computed(() => state.workspace?.tables?.transcriptBursts || []);
const transcriptBurstDistribution = computed(() => state.workspace?.tables?.transcriptBurstDistribution || []);
const transcriptSummary = computed(() => state.workspace?.stats?.transcriptSummary || {});

const transcriptEntries = computed(() => {
  if (transcriptSegments.value.length) {
    return transcriptSegments.value
      .map((row) => {
        const label = String(row?.start_label || "").trim();
        const speaker = mapSpeakerLabel(row?.speaker);
        const text = String(row?.text || "").trim();
        if (!text) return "";
        const prefix = [label ? `[${label}]` : "", speaker ? speaker.toUpperCase() : ""].filter(Boolean).join(" ");
        return prefix ? `${prefix}\n${text}` : text;
      })
      .filter(Boolean);
  }

  return transcriptText.value
    .split("\n")
    .map((entry) => entry.trim())
    .filter(Boolean);
});

const filteredTranscriptEntries = computed(() => {
  const query = transcriptSearch.value.trim().toLowerCase();
  if (!query) return transcriptEntries.value;
  return transcriptEntries.value.filter((entry) => entry.toLowerCase().includes(query));
});

const transcriptMatchCount = computed(() => {
  const query = transcriptSearch.value.trim();
  return query ? filteredTranscriptEntries.value.length : 0;
});

const speakerKeys = computed(() => {
  const fromSaved = Object.keys(speakerNames);
  const fromMetrics = transcriptSpeakers.value
    .map((row) => String(row?.speaker || "").trim())
    .filter(Boolean);
  return [...new Set([...fromSaved, ...fromMetrics])].sort((left, right) =>
    left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" })
  );
});

const highlightsRows = computed(() =>
  transcriptKeyMoments.value
    .map((row) => ({
      time_label: row.time_label,
      speaker: mapSpeakerLabel(row.speaker),
      score: row.score,
      reasons: row.reasons,
      excerpt: row.excerpt,
    }))
    .filter((row) => {
      const excerpt = String(row.excerpt || "").trim();
      const wordCount = excerpt.split(/\s+/).filter(Boolean).length;
      return excerpt.length >= 24 && wordCount >= 4;
    })
);

const numbersRows = computed(() =>
  transcriptNumbers.value.map((row) => ({
    mention: row.mention,
    kind: row.kind,
    speaker: mapSpeakerLabel(row.speaker),
    time_label: row.time_label,
    time_seconds: Number.isFinite(Number(row.time_seconds)) ? Number(Number(row.time_seconds).toFixed(2)) : row.time_seconds,
    context: row.context,
  }))
);

const numbersColumnLabels = {
  mention: "Mention",
  kind: "Type",
  speaker: "Speaker",
  time_label: "Time",
  time_seconds: "Time (sec)",
  context: "Context",
};

const numbersColumnWidths = {
  mention: "10rem",
  kind: "10rem",
  speaker: "10rem",
  time_label: "7rem",
  time_seconds: "8rem",
  context: "30rem",
};

const paceChartRows = computed(() =>
  transcriptPace.value
    .map((row) => ({
      time_seconds: Number(row.time_seconds) || 0,
      time_label: row.time_label || row.start_label || "Unknown",
      segment_wpm: Number(row.segment_wpm) || 0,
    }))
    .filter((row) => row.segment_wpm > 0)
);

const paceSummaryCards = computed(() => [
  {
    label: "Average WPM",
    value: Number(transcriptSummary.value?.global_wpm || transcriptSummary.value?.avg_words_per_minute || 0).toFixed(1),
  },
  {
    label: "Min WPM",
    value: Number(transcriptSummary.value?.min_wpm || 0).toFixed(1),
  },
  {
    label: "Max WPM",
    value: Number(transcriptSummary.value?.max_wpm || 0).toFixed(1),
  },
]);

const speakerAirtimeRows = computed(() =>
  transcriptSpeakers.value
    .map((row) => ({
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
      speaking_seconds: Number(row.speaking_seconds) || 0,
      share_pct: Number(row.share_pct) || 0,
      speaking_label: row.speaking_label || "",
    }))
    .filter((row) => row.speaker)
);

const speakerAirtimeTableRows = computed(() =>
  speakerAirtimeRows.value.map((row) => ({
    speaker: row.speaker,
    speaking_time: row.speaking_label,
    contribution_pct: row.share_pct,
  }))
);

const speakerAirtimeColumnLabels = {
  speaker: "Speaker",
  speaking_time: "Speaking Time",
  contribution_pct: "% Contribution",
};

const speakerTimelineRows = computed(() =>
  transcriptSegments.value
    .map((row) => ({
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
      start_seconds: Number(row.start_seconds) || 0,
      end_seconds: Number(row.end_seconds) || Number(row.start_seconds) || 0,
      duration_seconds: Number(row.duration_seconds) || 0,
    }))
    .filter((row) => row.duration_seconds > 0)
);

const speakerTurnSummaryRows = computed(() => {
  const summary = new Map();
  for (const row of transcriptSpeakerTurns.value) {
    const speaker = mapSpeakerLabel(row?.speaker || "Unknown");
    const duration = Number(row?.duration_seconds) || 0;
    const current = summary.get(speaker) || { speaker, turn_count: 0, avg_turn_duration_seconds: 0, total_duration: 0 };
    current.turn_count += 1;
    current.total_duration += duration;
    summary.set(speaker, current);
  }
  return Array.from(summary.values())
    .map((row) => ({
      speaker: row.speaker,
      turn_count: row.turn_count,
      avg_turn_duration_seconds: row.turn_count ? Number((row.total_duration / row.turn_count).toFixed(2)) : 0,
    }))
    .sort((a, b) => b.turn_count - a.turn_count);
});

const speakerTurnsTableRows = computed(() =>
  speakerTurnSummaryRows.value.map((row) => ({
    speaker: row.speaker,
    number_of_turns: row.turn_count,
    avg_duration_per_turn_seconds: row.avg_turn_duration_seconds,
  }))
);

const speakerTurnsColumnLabels = {
  speaker: "Speaker",
  number_of_turns: "Number Of Turns",
  avg_duration_per_turn_seconds: "Avg Duration Per Turn (sec)",
};

const speakerTurnTimelineRows = computed(() =>
  transcriptSpeakerTurns.value
    .map((row) => ({
      speaker: mapSpeakerLabel(row?.speaker || "Unknown"),
      time_seconds: Number(row?.start_seconds) || 0,
    }))
    .filter((row) => row.time_seconds >= 0)
);

const utteranceDurationRows = computed(() =>
  transcriptSegments.value
    .map((row) => ({
      start_label: row.start_label || "Unknown",
      duration_seconds: Number(row.duration_seconds) || 0,
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
      text: row.text || "",
    }))
    .filter((row) => row.duration_seconds > 0)
    .sort((a, b) => b.duration_seconds - a.duration_seconds)
    .slice(0, 20)
);

const utteranceSummaryCards = computed(() => {
  const durations = utteranceDurationRows.value.map((row) => Number(row.duration_seconds) || 0).filter((value) => value > 0);
  const avg = durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : 0;
  const longest = durations.length ? Math.max(...durations) : 0;
  return [
    { label: "Avg Utterance Duration", value: `${avg.toFixed(2)}s` },
    { label: "Longest Utterance", value: `${longest.toFixed(2)}s` },
  ];
});

const utteranceDistributionRows = computed(() => {
  const backendRows = transcriptUtteranceDistribution.value
    .map((row) => ({
      duration_bin: row?.duration_bin || "Unknown",
      count: Number(row?.count) || 0,
    }))
    .filter((row) => row.count >= 0);

  if (backendRows.length) return backendRows;

  const buckets = [
    { label: "0-5s", min: 0, max: 5, count: 0 },
    { label: "5-10s", min: 5, max: 10, count: 0 },
    { label: "10-20s", min: 10, max: 20, count: 0 },
    { label: "20-30s", min: 20, max: 30, count: 0 },
    { label: "30s+", min: 30, max: Number.POSITIVE_INFINITY, count: 0 },
  ];

  for (const row of transcriptSegments.value) {
    const duration = Number(row?.duration_seconds) || 0;
    if (duration <= 0) continue;
    const bucket = buckets.find((item) => duration >= item.min && duration < item.max);
    if (bucket) bucket.count += 1;
  }

  return buckets.map((bucket) => ({ duration_bin: bucket.label, count: bucket.count }));
});

const wordsCountRows = computed(() =>
  transcriptSpeakers.value
    .map((row) => ({
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
      words: Number(row.words) || 0,
    }))
    .filter((row) => row.words > 0)
);

const wordsSummaryCards = computed(() => {
  const totalWords = Number(transcriptSummary.value?.total_words || 0);
  const avgSentenceLengthFromSummary = Number(transcriptSummary.value?.avg_sentence_length || 0);
  const segmentWordCounts = transcriptSegments.value
    .map((row) => Number(row?.word_count) || 0)
    .filter((value) => value > 0);
  const avgSentenceLengthFromSegments = segmentWordCounts.length
    ? segmentWordCounts.reduce((sum, value) => sum + value, 0) / segmentWordCounts.length
    : 0;
  const avgSentenceLength = avgSentenceLengthFromSummary > 0 ? avgSentenceLengthFromSummary : avgSentenceLengthFromSegments;
  const topSpeaker = [...wordsCountRows.value].sort((a, b) => b.words - a.words)[0];
  const speakerCount = wordsCountRows.value.length;

  return [
    {
      label: "Total Words",
      value: String(totalWords),
    },
    {
      label: "Avg Sentence Length",
      value: `${avgSentenceLength.toFixed(1)} words`,
    },
    {
      label: "Top Speaker",
      value: topSpeaker ? `${topSpeaker.speaker} (${topSpeaker.words})` : "N/A",
    },
    {
      label: "Active Speakers",
      value: String(speakerCount),
    },
  ];
});

const wordsTimelineRows = computed(() =>
  transcriptTimeline.value
    .map((row) => ({
      minute_label: row?.minute_label || "Unknown",
      word_count: Number(row?.word_count) || 0,
    }))
    .filter((row) => row.word_count >= 0)
);

const wordsCountColumnLabels = {
  speaker: "Speaker",
  words: "Words",
};

const speakingSegmentsRows = computed(() => {
  const burstRows = transcriptBursts.value
    .map((row) => ({
      start_label: row.start_label || "Unknown",
      duration_seconds: Number(row.duration_seconds) || 0,
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
    }))
    .filter((row) => row.duration_seconds > 0);

  if (burstRows.length) return burstRows;

  return transcriptSegments.value
    .map((row) => ({
      start_label: row.start_label || "Unknown",
      duration_seconds: Number(row.duration_seconds) || 0,
      speaker: mapSpeakerLabel(row.speaker || "Unknown"),
    }))
    .filter((row) => row.duration_seconds > 0);
});

const speakingSegmentsSummaryCards = computed(() => {
  const durations = speakingSegmentsRows.value.map((row) => row.duration_seconds).filter((value) => value > 0);
  const average = durations.length ? durations.reduce((sum, value) => sum + value, 0) / durations.length : 0;
  const longest = durations.length ? Math.max(...durations) : 0;
  return [
    { label: "Avg Speaking Burst", value: `${average.toFixed(2)}s` },
    { label: "Longest Continuous Speech", value: `${longest.toFixed(2)}s` },
  ];
});

const speakingSegmentsDistributionRows = computed(() => {
  const backendRows = transcriptBurstDistribution.value
    .map((row) => ({
      burst_duration_bin: row?.burst_duration_bin || "Unknown",
      count: Number(row?.count) || 0,
    }))
    .filter((row) => row.count >= 0);

  if (backendRows.length) return backendRows;

  const buckets = [
    { label: "0-5s", min: 0, max: 5, count: 0 },
    { label: "5-10s", min: 5, max: 10, count: 0 },
    { label: "10-20s", min: 10, max: 20, count: 0 },
    { label: "20-30s", min: 20, max: 30, count: 0 },
    { label: "30s+", min: 30, max: Number.POSITIVE_INFINITY, count: 0 },
  ];

  for (const row of speakingSegmentsRows.value) {
    const duration = Number(row?.duration_seconds) || 0;
    if (duration <= 0) continue;
    const bucket = buckets.find((item) => duration >= item.min && duration < item.max);
    if (bucket) bucket.count += 1;
  }

  return buckets.map((bucket) => ({
    burst_duration_bin: bucket.label,
    count: bucket.count,
  }));
});

const pauseSummaryCards = computed(() => [
  {
    label: "Average Pause Duration",
    value: `${Number(transcriptSummary.value?.avg_pause_seconds || 0).toFixed(2)}s`,
  },
  {
    label: "Longest Pause",
    value: `${Number(transcriptSummary.value?.longest_silence_seconds || 0).toFixed(2)}s`,
  },
  {
    label: "Pauses > 1s",
    value: String(Number(transcriptSummary.value?.pause_count_over_1s || 0)),
  },
]);

const silenceTimelineRows = computed(() =>
  transcriptSilence.value
    .map((row) => ({
      time_label:
        row?.silence_start_label && row?.silence_end_label
          ? `${row.silence_start_label} - ${row.silence_end_label}`
          : row?.silence_start_label || row?.silence_end_label || "Unknown",
      time_seconds: Number(row?.silence_start_seconds) || 0,
      pause_seconds: Number(row?.gap_seconds) || 0,
      pause_type: row?.pause_type || "Pause",
    }))
    .filter((row) => row.pause_seconds > 0)
    .slice(0, 60)
);

const pauseTypeRows = computed(() =>
  transcriptPauseTypes.value
    .map((row) => ({
      pause_type: row?.pause_type || "Pause",
      count: Number(row?.count) || 0,
    }))
    .filter((row) => row.count > 0)
);

const silenceDistributionRows = computed(() =>
  transcriptPauseDistribution.value
    .map((row) => ({
      duration_bin: row?.duration_bin || "Unknown",
      count: Number(row?.count) || 0,
    }))
    .filter((row) => row.count >= 0)
);

const tabs = [
  { id: "transcript", label: "Transcript" },
  { id: "silence", label: "Silence / Pause Metrics" },
  { id: "pace", label: "Speaking Pace" },
  { id: "airtime", label: "Speaker Airtime" },
  { id: "turns", label: "Speaker Turns" },
  { id: "words", label: "Words Count" },
  { id: "segments", label: "Speaking Segments" },
  { id: "utterance", label: "Utterance Duration" },
  { id: "highlights", label: "NER" },
];

const hasTranscriptData = computed(
  () =>
    Boolean(transcriptPayload.value) ||
    transcriptSegments.value.length > 0 ||
    Boolean(String(transcriptText.value || "").trim()),
);

const isTranscriptLoading = computed(
  () => Boolean(state.workspace) && state.loading.sessionFetch && !hasTranscriptData.value,
);
</script>

<template>
  <section class="page-section">
    <h2>Transcript</h2>
    <p class="page-description">Transcript text, highlights, and timing-based speaking diagnostics.</p>

    <template v-if="state.workspace && hasTranscriptData">
      <div class="section-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="section-tab"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <template v-if="activeTab === 'transcript'">
        <div class="panel transcript-search-panel">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <button class="transcript-editor-toggle" type="button" @click="showSpeakerEditor = !showSpeakerEditor">
                {{ showSpeakerEditor ? "Close Speaker Labels" : "Edit Speaker Labels" }}
              </button>
            </div>
          </div>
          <input v-model="transcriptSearch" type="text" class="transcript-search-input" placeholder="Search by keyword" />
          <p v-if="transcriptSearch.trim()" class="field-hint transcript-search-hint">
            {{ transcriptMatchCount }} match<span v-if="transcriptMatchCount !== 1">es</span> found
          </p>
        </div>

        <section class="panel" v-if="showSpeakerEditor">
          <div class="panel-heading">
            <h3>Speaker Labels</h3>
          </div>
          <div class="speaker-grid">
            <label v-for="speaker in speakerKeys" :key="speaker">
              {{ speaker }}
              <input v-model="speakerNames[speaker]" type="text" />
            </label>
          </div>
          <button class="primary" :disabled="state.loading.speakerLabels" @click="handleSaveSpeakerLabels()">
            {{ state.loading.speakerLabels ? "Saving..." : "Save Speaker Labels" }}
          </button>
        </section>

        <section class="panel">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <h3>Transcript text</h3>
              <button class="inline-icon-button" type="button" title="Download transcript JSON" @click="downloadTranscriptJson">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>
          <pre class="markdown-block transcript-block">{{ filteredTranscriptEntries.length ? filteredTranscriptEntries.join("\n\n") : "No matches found." }}</pre>
        </section>
      </template>

      <template v-else-if="activeTab === 'highlights'">
        <section class="panel" v-if="numbersRows.length">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <h3>NER (Named Entity Recognition)</h3>
              <button class="inline-icon-button" type="button" title="Download NER CSV" @click="downloadCsv('transcript-ner-extraction.csv', numbersRows)">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>
          <DataTable :rows="numbersRows" :column-labels="numbersColumnLabels" :column-widths="numbersColumnWidths" csv-filename="transcript-ner-extraction.csv" :show-toolbar="false" />
        </section>
      </template>

      <template v-else-if="activeTab === 'silence'">
        <div class="metric-grid transcript-metric-grid">
          <article v-for="card in pauseSummaryCards" :key="card.label" class="metric-card metric-card-hero transcript-metric-card">
            <span class="metric-label">{{ card.label }}</span>
            <strong class="metric-value">{{ card.value }}</strong>
          </article>
        </div>

        <section class="panel">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <h3>Pause Timeline &amp; Histogram</h3>
              <button
                class="inline-icon-button"
                type="button"
                title="Download pause timeline CSV"
                @click="downloadCsv('transcript-pause-timeline.csv', silenceTimelineRows)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>

          <div class="overview-chart-grid">
            <HistogramChartCard
              title="Pause Histogram"
              description="Buckets of pause duration across the session."
              :rows="silenceDistributionRows"
              label-key="duration_bin"
              value-key="count"
            />
            <TimelinePauseChartCard
              title="Pause Timeline"
              description="Each pause event across the session timeline."
              :rows="silenceTimelineRows"
            />
          </div>
        </section>

        <section class="panel" v-if="pauseTypeRows.length">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <h3>Pause Types</h3>
              <button
                class="inline-icon-button"
                type="button"
                title="Download pause types CSV"
                @click="downloadCsv('transcript-pause-types.csv', pauseTypeRows)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>
          <DataTable :rows="pauseTypeRows" csv-filename="transcript-pause-types.csv" :show-toolbar="false" />
        </section>
      </template>

      <template v-else-if="activeTab === 'pace'">
        <div class="metric-grid transcript-metric-grid">
          <article v-for="card in paceSummaryCards" :key="card.label" class="metric-card metric-card-hero transcript-metric-card">
            <span class="metric-label">{{ card.label }}</span>
            <strong class="metric-value">{{ card.value }}</strong>
          </article>
        </div>

        <section class="panel">
          <div class="panel-heading panel-heading-inline">
            <div class="panel-heading-inline-title">
              <h3>Speaking Pace</h3>
              <button
                class="inline-icon-button"
                type="button"
                title="Download speaking pace CSV"
                @click="downloadCsv('transcript-speaking-pace.csv', paceChartRows)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                    fill="currentColor"
                  />
                </svg>
              </button>
            </div>
          </div>

          <PaceOverTimeChartCard
            title="Words Per Minute Over Time"
            description="Words-per-minute by transcript segment across the session."
            :rows="paceChartRows"
          />
        </section>
      </template>

      <template v-else-if="activeTab === 'airtime'">
        <div class="panel-heading panel-heading-inline table-toolbar-panel" v-if="speakerAirtimeRows.length">
          <div class="panel-heading-inline-title">
            <h3>Speaker Metrics</h3>
            <button
              class="inline-icon-button"
              type="button"
              title="Download speaker airtime CSV"
              @click="downloadCsv('transcript-speaker-airtime.csv', speakerAirtimeTableRows)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>

        <div class="overview-chart-grid">
          <SpeakerShareChartCard title="Pie Chart Per Speaker" :rows="speakerAirtimeRows" />
          <SpeakerTimelineChartCard title="Timeline Per Speaker" :rows="speakerTimelineRows" />
        </div>

        <DataTable
          :rows="speakerAirtimeTableRows"
          :column-labels="speakerAirtimeColumnLabels"
          csv-filename="transcript-speaker-airtime.csv"
          :show-toolbar="false"
        />
      </template>

      <template v-else-if="activeTab === 'turns'">
        <div class="panel-heading panel-heading-inline table-toolbar-panel" v-if="speakerTurnsTableRows.length">
          <div class="panel-heading-inline-title">
            <h3>Speaker Turns</h3>
            <button
              class="inline-icon-button"
              type="button"
              title="Download speaker turns CSV"
              @click="downloadCsv('transcript-speaker-turns.csv', speakerTurnsTableRows)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>

        <SpeakerTurnsTimelineChartCard title="Timeline Of Speaker Changes" :rows="speakerTurnTimelineRows" />

        <DataTable
          :rows="speakerTurnsTableRows"
          :column-labels="speakerTurnsColumnLabels"
          csv-filename="transcript-speaker-turns.csv"
          :show-toolbar="false"
        />
      </template>

      <template v-else-if="activeTab === 'utterance'">
        <div class="metric-grid transcript-metric-grid">
          <article v-for="card in utteranceSummaryCards" :key="card.label" class="metric-card metric-card-hero transcript-metric-card">
            <span class="metric-label">{{ card.label }}</span>
            <strong class="metric-value">{{ card.value }}</strong>
          </article>
        </div>

        <div class="panel-heading panel-heading-inline table-toolbar-panel" v-if="utteranceDurationRows.length">
          <div class="panel-heading-inline-title">
            <h3>Utterance Duration</h3>
            <button
              class="inline-icon-button"
              type="button"
              title="Download utterance duration CSV"
              @click="downloadCsv('transcript-utterance-duration.csv', utteranceDurationRows)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>

        <HistogramChartCard
          v-if="utteranceDistributionRows.length"
          title="Distribution Of Utterance Length"
          description="Utterance duration refers to the length of time a spoken phrase or sentence lasts."
          :rows="utteranceDistributionRows"
          label-key="duration_bin"
          value-key="count"
        />
      </template>

      <template v-else-if="activeTab === 'words'">
        <div class="metric-grid transcript-metric-grid">
          <article v-for="card in wordsSummaryCards" :key="card.label" class="metric-card metric-card-hero transcript-metric-card">
            <span class="metric-label">{{ card.label }}</span>
            <strong class="metric-value">{{ card.value }}</strong>
          </article>
        </div>

        <div class="panel-heading panel-heading-inline table-toolbar-panel" v-if="wordsCountRows.length">
          <div class="panel-heading-inline-title">
            <h3>Words Count</h3>
            <button
              class="inline-icon-button"
              type="button"
              title="Download words count CSV"
              @click="downloadCsv('transcript-word-count.csv', wordsCountRows)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>

        <div class="overview-chart-grid">
          <BarChartCard
            title="Words By Speaker"
            :rows="wordsCountRows"
            label-key="speaker"
            value-key="words"
          />
          <WordsOverTimeChartCard title="Words Over Time" :rows="wordsTimelineRows" />
        </div>

        <DataTable
          :rows="wordsCountRows"
          :column-labels="wordsCountColumnLabels"
          csv-filename="transcript-word-count.csv"
          :show-toolbar="false"
        />
      </template>

      <template v-else>
        <div class="metric-grid transcript-metric-grid">
          <article v-for="card in speakingSegmentsSummaryCards" :key="card.label" class="metric-card metric-card-hero transcript-metric-card">
            <span class="metric-label">{{ card.label }}</span>
            <strong class="metric-value">{{ card.value }}</strong>
          </article>
        </div>

        <div class="panel-heading panel-heading-inline table-toolbar-panel" v-if="speakingSegmentsRows.length">
          <div class="panel-heading-inline-title">
            <h3>Speaking Segments</h3>
            <button
              class="inline-icon-button"
              type="button"
              title="Download speaking segments CSV"
              @click="downloadCsv('transcript-speaking-segments.csv', speakingSegmentsRows)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 3v10.2l3.6-3.6 1.4 1.4-6 6-6-6 1.4-1.4 3.6 3.6V3H12zm-7 14h14v2H5v-2z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </div>

        <SpeakingBurstChartCard
          v-if="speakingSegmentsRows.length"
          title="Speaking Duration Before Pause"
          :rows="speakingSegmentsRows"
        />

        <HistogramChartCard
          v-if="speakingSegmentsDistributionRows.length"
          title="Distribution Of Speaking Burst Length"
          description="The duration of continuous vocalization (talk-spurt) by a speaker between silences."
          :rows="speakingSegmentsDistributionRows"
          label-key="burst_duration_bin"
          value-key="count"
        />
      </template>
    </template>

    <section v-else-if="isTranscriptLoading" class="panel loading-panel">
      <div class="loading-indicator" aria-hidden="true"></div>
      <div>
        <h3 class="loading-title">Transcript is still loading</h3>
        <p class="loading-copy">Session Overview and Chat &amp; Questions are ready. Transcript data will appear here as soon as processing finishes.</p>
      </div>
    </section>
  </section>
</template>
