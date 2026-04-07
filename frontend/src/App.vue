<script setup>
import { computed, onMounted } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import { api } from "./api";
import { useWorkspace } from "./store/workspace";

const { state, fetchSessionData, hasTranscriptData, isTranscriptLoading } = useWorkspace();
const route = useRoute();
const logoUrl = "/brand-assets/icons/Icon-Livestorm-Tertiary-Light.png";

const navItems = [
  { to: "/session-overview", label: "Session Overview", key: "session" },
  { to: "/transcript", label: "Transcript", key: "transcript" },
  { to: "/chat-questions", label: "Chat & Questions", key: "chat" },
  { to: "/analysis", label: "Analysis", key: "analysis" },
  { to: "/content-repurposing", label: "Repurposing", key: "repurposing" },
  { to: "/smart-recap", label: "Smart Recap", key: "recap" },
];

const navStateByKey = computed(() => {
  const hasWorkspace = Boolean(state.workspace);
  const transcriptReady = hasTranscriptData.value;
  const transcriptLoading = isTranscriptLoading.value;

  return {
    session: { disabled: !hasWorkspace, loading: false, ready: hasWorkspace },
    chat: { disabled: !hasWorkspace, loading: false, ready: hasWorkspace },
    transcript: { disabled: !hasWorkspace, loading: transcriptLoading, ready: transcriptReady },
    analysis: { disabled: !transcriptReady, loading: transcriptLoading, ready: transcriptReady },
    repurposing: { disabled: !transcriptReady, loading: transcriptLoading, ready: transcriptReady },
    recap: { disabled: !transcriptReady, loading: transcriptLoading, ready: transcriptReady },
  };
});

function getNavMeta(item) {
  return navStateByKey.value[item.key] || { disabled: false, loading: false, ready: false };
}

onMounted(async () => {
  if (state.apiKey) return;
  try {
    const bootstrap = await api.bootstrap();
    const defaultApiKey = String(bootstrap?.defaults?.apiKey || "").trim();
    if (defaultApiKey && !state.apiKey) {
      state.apiKey = defaultApiKey;
    }
  } catch (_error) {
    // Ignore bootstrap failures so manual entry still works without friction.
  }
});

async function handleFetchClick() {
  try {
    await fetchSessionData(false);
  } catch (_error) {
    // The workspace store already surfaces a friendly message in the sidebar.
  }
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <img :src="logoUrl" alt="Livestorm" class="brand-logo" />
        <div class="brand-copy">
          <h1>StormIQ</h1>
        </div>
      </div>

      <section class="control-card">
        <div class="field-group">
          <input v-model="state.apiKey" type="password" placeholder="Livestorm API Key" />
        </div>

        <div class="field-group">
          <div class="toggle-row">
            <button :class="{ active: state.inputMode === 'session' }" @click="state.inputMode = 'session'">Session ID</button>
            <button :class="{ active: state.inputMode === 'event' }" @click="state.inputMode = 'event'">Event ID</button>
          </div>
        </div>

        <div v-if="state.inputMode === 'session'" class="field-group">
          <input v-model="state.sessionId" type="text" placeholder="Session ID" />
        </div>

        <div v-else class="field-group">
          <input v-model="state.eventId" type="text" placeholder="Event ID" />
          <select v-model="state.selectedEventSessionId" v-if="state.eventSessions.length">
            <option value="">Select a past session</option>
            <option v-for="session in state.eventSessions" :key="session.id" :value="session.id">
              {{ session.label }}
            </option>
          </select>
          <p v-if="state.selectedEventSessionId" class="field-hint">{{ state.selectedEventSessionId }}</p>
        </div>

        <button
          class="primary fetch-button"
          :disabled="state.loading.sessionFetch || state.loading.eventSessions || !state.apiKey || !(state.inputMode === 'session' ? state.sessionId.trim() : state.eventId.trim())"
          @click="handleFetchClick"
        >
          {{ state.loading.sessionFetch || state.loading.eventSessions ? "Fetching..." : "Fetch Data" }}
        </button>
      </section>

      <p v-if="state.error" class="error-text">{{ state.error }}</p>
    </aside>

    <main class="main-content">
      <nav class="top-nav">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" custom v-slot="{ navigate }">
          <button
            type="button"
            class="top-nav-item"
            :class="{
              'router-link-active': route.path === item.to,
              disabled: getNavMeta(item).disabled,
              loading: getNavMeta(item).loading,
            }"
            :disabled="getNavMeta(item).disabled"
            @click="navigate"
          >
            <span class="top-nav-item-text">{{ item.label }}</span>
            <span v-if="getNavMeta(item).loading" class="top-nav-status top-nav-status-loading" aria-hidden="true"></span>
            <span v-else-if="getNavMeta(item).ready" class="top-nav-status top-nav-status-ready" aria-hidden="true"></span>
          </button>
        </RouterLink>
      </nav>
      <RouterView />
    </main>
  </div>
</template>
