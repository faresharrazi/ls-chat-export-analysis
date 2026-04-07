<script setup>
import { computed } from "vue";

const props = defineProps({
  title: {
    type: String,
    default: "",
  },
  description: {
    type: String,
    default: "",
  },
  rows: {
    type: Array,
    default: () => [],
  },
});

const chartWidth = 860;
const chartHeight = 320;
const margin = { top: 18, right: 20, bottom: 42, left: 48 };

const normalizedRows = computed(() => {
  const plotWidth = chartWidth - margin.left - margin.right;
  const plotHeight = chartHeight - margin.top - margin.bottom;
  const maxTime = Math.max(1, ...props.rows.map((row) => Number(row?.time_seconds) || 0));
  const maxWpm = Math.max(1, ...props.rows.map((row) => Number(row?.segment_wpm) || 0));

  return props.rows.map((row) => {
    const time = Number(row?.time_seconds) || 0;
    const wpm = Number(row?.segment_wpm) || 0;
    const x = margin.left + (time / maxTime) * plotWidth;
    const y = margin.top + (plotHeight - (wpm / maxWpm) * plotHeight);
    const intensity = Math.max(0, Math.min(wpm / maxWpm, 1));
    const hue = 200 - intensity * 150;
    return {
      x,
      y,
      time,
      wpm,
      color: `hsl(${hue}, 92%, ${58 - intensity * 8}%)`,
    };
  });
});

const linePath = computed(() => {
  if (!normalizedRows.value.length) return "";
  return normalizedRows.value
    .map((row, index) => `${index === 0 ? "M" : "L"} ${row.x.toFixed(2)} ${row.y.toFixed(2)}`)
    .join(" ");
});

const xTicks = computed(() => {
  const plotWidth = chartWidth - margin.left - margin.right;
  const maxTime = Math.max(1, ...props.rows.map((row) => Number(row?.time_seconds) || 0));
  const tickCount = 4;
  return Array.from({ length: tickCount + 1 }, (_, index) => {
    const value = (maxTime / tickCount) * index;
    const x = margin.left + (plotWidth / tickCount) * index;
    return { value: Math.round(value), x };
  });
});

const yTicks = computed(() => {
  const plotHeight = chartHeight - margin.top - margin.bottom;
  const maxWpm = Math.max(1, ...props.rows.map((row) => Number(row?.segment_wpm) || 0));
  const tickCount = 4;
  return Array.from({ length: tickCount + 1 }, (_, index) => {
    const value = Math.round((maxWpm / tickCount) * (tickCount - index));
    const y = margin.top + (plotHeight / tickCount) * index;
    return { value, y };
  });
});
</script>

<template>
  <section class="panel" v-if="rows.length">
    <div class="panel-heading">
      <h3>{{ title }}</h3>
      <p v-if="description">{{ description }}</p>
    </div>

    <div class="svg-chart-shell">
      <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" class="svg-chart" role="img" :aria-label="title">
        <defs>
          <linearGradient id="pace-line-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#74d9ef" />
            <stop offset="45%" stop-color="#68b7ff" />
            <stop offset="100%" stop-color="#ffbf47" />
          </linearGradient>
        </defs>

        <g class="svg-grid">
          <line
            v-for="tick in yTicks"
            :key="`pace-grid-${tick.value}-${tick.y}`"
            :x1="margin.left"
            :x2="chartWidth - margin.right"
            :y1="tick.y"
            :y2="tick.y"
          />
        </g>

        <g class="svg-axis-labels">
          <text
            v-for="tick in yTicks"
            :key="`pace-y-${tick.value}-${tick.y}`"
            :x="margin.left - 10"
            :y="tick.y + 4"
            text-anchor="end"
          >
            {{ tick.value }}
          </text>
          <text
            v-for="tick in xTicks"
            :key="`pace-x-${tick.value}-${tick.x}`"
            :x="tick.x"
            :y="chartHeight - 12"
            text-anchor="middle"
          >
            {{ tick.value }}
          </text>
          <text class="svg-axis-title" :x="margin.left - 34" :y="chartHeight / 2" text-anchor="middle" transform="rotate(-90, 14, 160)">
            Words Per Minute
          </text>
          <text class="svg-axis-title" :x="chartWidth / 2" :y="chartHeight - 2" text-anchor="middle">
            Time (sec)
          </text>
        </g>

        <path v-if="linePath" class="pace-chart-line" :d="linePath" />
        <circle
          v-for="(row, index) in normalizedRows"
          :key="`${row.time}-${row.wpm}-${index}`"
          class="pace-chart-point"
          :cx="row.x"
          :cy="row.y"
          r="3"
          :style="{ fill: row.color }"
        >
          <title>{{ `${row.wpm} WPM at ${row.time}s` }}</title>
        </circle>
      </svg>
    </div>
  </section>
</template>
