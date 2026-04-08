<script setup>
import { computed, onMounted } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { api } from "./api";
import FetchSessionForm from "./components/FetchSessionForm.vue";
import { useWorkspace } from "./store/workspace";

const { state, fetchSessionData, hasTranscriptData, isTranscriptLoading, isTranscriptUnavailable, loadWorkspaceEvents } = useWorkspace();
const route = useRoute();
const router = useRouter();
const logoUrl = "/brand-assets/icons/Icon-Livestorm-Tertiary-Light.png";
const hasEvents = computed(() => state.workspaceEvents.length > 0);

const navItems = [
  { to: "/events", label: "Events", key: "events" },
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
  const transcriptUnavailable = isTranscriptUnavailable.value;
  const isFreshSessionFetch =
    state.loading.sessionFetch &&
    (
      (state.inputMode === "session" && Boolean(state.sessionId.trim())) ||
      (state.inputMode === "event" && Boolean(state.selectedEventSessionId.trim()))
    );

  if (isFreshSessionFetch) {
    return {
      events: { disabled: true, loading: true, ready: false },
      session: { disabled: true, loading: true, ready: false },
      chat: { disabled: true, loading: true, ready: false },
      transcript: { disabled: true, loading: true, ready: false },
      analysis: { disabled: true, loading: true, ready: false },
      repurposing: { disabled: true, loading: true, ready: false },
      recap: { disabled: true, loading: true, ready: false },
    };
  }

  return {
    events: { disabled: !hasEvents.value, loading: state.loading.workspaceEvents, ready: hasEvents.value },
    session: { disabled: !hasWorkspace, loading: false, ready: hasWorkspace },
    chat: { disabled: !hasWorkspace, loading: false, ready: hasWorkspace },
    transcript: { disabled: !hasWorkspace || transcriptUnavailable, loading: transcriptLoading, ready: transcriptReady, unavailable: transcriptUnavailable },
    analysis: { disabled: !transcriptReady || transcriptUnavailable, loading: transcriptLoading, ready: transcriptReady, unavailable: transcriptUnavailable },
    repurposing: { disabled: !transcriptReady || transcriptUnavailable, loading: transcriptLoading, ready: transcriptReady, unavailable: transcriptUnavailable },
    recap: { disabled: !transcriptReady || transcriptUnavailable, loading: transcriptLoading, ready: transcriptReady, unavailable: transcriptUnavailable },
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
    if (
      (state.inputMode === "session" && state.sessionId.trim()) ||
      (state.inputMode === "event" && state.selectedEventSessionId.trim())
    ) {
      router.push("/session-overview");
    }
    await fetchSessionData(false);
  } catch (_error) {
    // The workspace store already surfaces a friendly message in the sidebar.
  }
}

async function handleFetchEventsClick() {
  try {
    router.push("/events");
    await loadWorkspaceEvents();
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

      <FetchSessionForm
        :state="state"
        @fetch="handleFetchClick"
        @fetch-events="handleFetchEventsClick"
      />

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
            <span v-else-if="getNavMeta(item).unavailable" class="top-nav-status top-nav-status-unavailable" aria-hidden="true"></span>
            <span v-else-if="getNavMeta(item).ready" class="top-nav-status top-nav-status-ready" aria-hidden="true"></span>
          </button>
        </RouterLink>
      </nav>
      <RouterView />
    </main>
  </div>
</template>
