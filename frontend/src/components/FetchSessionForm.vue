<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["fetch", "fetch-events"]);
const activeSource = ref("session");

watch(
  () => props.state.inputMode,
  (mode) => {
    if (mode === "session" || mode === "event") {
      activeSource.value = mode;
    }
  },
  { immediate: true }
);

function setSource(source) {
  activeSource.value = source;
  if (source === "session" || source === "event") {
    props.state.inputMode = source;
  }
}
</script>

<template>
  <section class="control-card">
    <div class="field-group">
      <input v-model="props.state.apiKey" type="password" placeholder="Livestorm API Key" />
    </div>

    <div class="field-group">
      <div class="toggle-row toggle-row-triple">
        <button :class="{ active: activeSource === 'session' }" @click="setSource('session')">Session</button>
        <button :class="{ active: activeSource === 'event' }" @click="setSource('event')">Event</button>
        <button :class="{ active: activeSource === 'workspace' }" @click="setSource('workspace')">Org</button>
      </div>
    </div>

    <div v-if="activeSource === 'session'" class="field-group">
      <input v-model="props.state.sessionId" type="text" placeholder="Session ID" />
      <button
        class="primary fetch-button"
        :disabled="
          props.state.loading.sessionFetch ||
          !props.state.apiKey ||
          !props.state.sessionId.trim()
        "
        @click="emit('fetch')"
      >
        {{ props.state.loading.sessionFetch ? "Fetching..." : "Fetch Data" }}
      </button>
    </div>

    <div v-else-if="activeSource === 'event'" class="field-group">
      <input v-model="props.state.eventId" type="text" placeholder="Event ID" />
      <button
        class="primary fetch-button"
        :disabled="
          props.state.loading.eventSessions ||
          !props.state.apiKey ||
          !props.state.eventId.trim()
        "
        @click="emit('fetch')"
      >
        {{ props.state.loading.eventSessions ? "Fetching sessions..." : "Fetch Sessions" }}
      </button>

      <select v-model="props.state.selectedEventSessionId" v-if="props.state.eventSessions.length">
        <option value="">Select a session</option>
        <option v-for="session in props.state.eventSessions" :key="session.id" :value="session.id">
          {{ session.label }}
        </option>
      </select>
      <p v-if="props.state.selectedEventSessionId" class="field-hint">{{ props.state.selectedEventSessionId }}</p>
      <button
        v-if="props.state.selectedEventSessionId.trim()"
        class="primary fetch-button"
        :disabled="
          props.state.loading.sessionFetch ||
          !props.state.apiKey ||
          !props.state.selectedEventSessionId.trim()
        "
        @click="emit('fetch')"
      >
        {{ props.state.loading.sessionFetch ? "Fetching..." : "Fetch Data" }}
      </button>
    </div>

    <div v-else class="field-group">
      <input v-model="props.state.workspaceEventsTitle" type="text" placeholder="Filter by event title (Optional)" />
      <select v-model="props.state.workspaceEventsStatus">
        <option value="">All statuses</option>
        <option value="live">Live</option>
        <option value="upcoming">Upcoming</option>
        <option value="on_demand">On demand</option>
        <option value="ended">Ended</option>
        <option value="not_started">Not started</option>
        <option value="draft">Draft</option>
        <option value="not_scheduled">Not scheduled</option>
      </select>
      <button
        class="primary fetch-button"
        :disabled="props.state.loading.workspaceEvents || !props.state.apiKey"
        @click="emit('fetch-events')"
      >
        {{ props.state.loading.workspaceEvents ? "Fetching events..." : "Fetch Events" }}
      </button>
    </div>
  </section>
</template>
