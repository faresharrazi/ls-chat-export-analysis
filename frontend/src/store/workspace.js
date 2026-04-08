import { computed, reactive, watch } from "vue";
import { api } from "../api";

const state = reactive({
  apiKey: "",
  auth: {
    oauthEnabled: false,
    connectedUser: null,
  },
  inputMode: "session",
  sessionId: "",
  eventId: "",
  loadedEventId: "",
  eventSessions: [],
  selectedEventSessionId: "",
  outputLanguage: "English",
  workspace: null,
  loading: {
    eventSessions: false,
    sessionFetch: false,
    analysis: false,
    deepAnalysis: false,
    smartRecap: false,
    contentRepurposing: false,
    speakerLabels: false,
  },
  error: "",
});

const activeSessionId = computed(() =>
  state.inputMode === "session" ? state.sessionId.trim() : state.selectedEventSessionId.trim()
);

const hasTranscriptData = computed(() => {
  const payload = state.workspace?.payloads?.transcript;
  const segments = state.workspace?.tables?.transcriptSegments || [];
  const text = String(state.workspace?.text?.transcriptDisplay || "").trim();
  return Boolean(payload) || segments.length > 0 || Boolean(text);
});
const isTranscriptLoading = computed(
  () => Boolean(state.workspace) && state.loading.sessionFetch && !hasTranscriptData.value
);

async function wrapCall(flag, fn) {
  state.error = "";
  state.loading[flag] = true;
  try {
    return await fn();
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
    throw error;
  } finally {
    state.loading[flag] = false;
  }
}

function applyBootstrap(payload) {
  const defaultApiKey = String(payload?.defaults?.apiKey || "").trim();
  if (defaultApiKey && !state.apiKey) {
    state.apiKey = defaultApiKey;
  }
  state.auth.oauthEnabled = Boolean(payload?.auth?.oauthEnabled);
  state.auth.connectedUser = payload?.auth?.connectedUser || null;
}

function resetWorkspace() {
  state.workspace = null;
  state.error = "";
}

async function loadEventSessions() {
  if ((!state.apiKey && !state.auth.connectedUser) || !state.eventId) return;
  const normalizedEventId = state.eventId.trim();
  const currentSelection = state.selectedEventSessionId;
  const data = await wrapCall("eventSessions", () =>
    api.fetchEventSessions({
      apiKey: state.apiKey,
      eventId: normalizedEventId,
    })
  );
  state.eventSessions = data.options || [];
  state.loadedEventId = normalizedEventId;
  const selectionStillExists = state.eventSessions.some((session) => session.id === currentSelection);
  state.selectedEventSessionId = selectionStillExists ? currentSelection : "";
}

async function fetchSessionData(forceRefresh = false) {
  return wrapCall("sessionFetch", async () => {
    if (state.inputMode === "event") {
      const normalizedEventId = state.eventId.trim();
      const shouldReloadEventSessions =
        !state.eventSessions.length || state.loadedEventId !== normalizedEventId;

      if (shouldReloadEventSessions) {
        await loadEventSessions();
        return null;
      }

      if (!state.selectedEventSessionId.trim()) {
        state.error = "Please select a session from the dropdown to continue.";
        return null;
      }
    }

    if (!activeSessionId.value) return;

    if (!forceRefresh) {
      const cached = await api.getCachedSession(activeSessionId.value);
      if (cached) {
        state.workspace = cached;
        return cached;
      }
    }

    const baseData = await api.fetchSessionBase(activeSessionId.value, {
      apiKey: state.apiKey,
      forceRefresh,
    });
    state.workspace = baseData;

    const transcriptData = await api.fetchSessionTranscript(activeSessionId.value, {
      apiKey: state.apiKey,
      forceRefresh,
    });
    state.workspace = transcriptData;
    return transcriptData;
  });
}

watch(
  () => [state.inputMode, state.sessionId, state.eventId, state.selectedEventSessionId],
  ([inputMode, sessionId, eventId, selectedEventSessionId], [previousMode, previousSessionId, previousEventId, previousSelectedEventSessionId] = []) => {
    const targetChanged =
      inputMode !== previousMode ||
      sessionId !== previousSessionId ||
      eventId !== previousEventId ||
      selectedEventSessionId !== previousSelectedEventSessionId;

    if (!targetChanged) return;

    if (inputMode === "event" && eventId !== previousEventId) {
      state.eventSessions = [];
      state.loadedEventId = "";
      state.selectedEventSessionId = "";
    }

  }
);

async function saveSpeakerLabels(speakerNames) {
  if (!activeSessionId.value) return;
  const data = await wrapCall("speakerLabels", () =>
    api.saveSpeakerLabels(activeSessionId.value, {
      apiKey: state.apiKey,
      speakerNames,
    })
  );
  state.workspace = data;
}

async function runAnalysis(outputLanguage = state.outputLanguage) {
  if (!activeSessionId.value) return;
  const result = await wrapCall("analysis", () =>
    api.runAnalysis(activeSessionId.value, {
      apiKey: state.apiKey,
      outputLanguage,
    })
  );
  state.workspace.outputs.analysisBundle = result.bundle;
}

async function runDeepAnalysis(outputLanguage = state.outputLanguage) {
  if (!activeSessionId.value) return;
  const result = await wrapCall("deepAnalysis", () =>
    api.runDeepAnalysis(activeSessionId.value, {
      apiKey: state.apiKey,
      outputLanguage,
    })
  );
  state.workspace.outputs.deepAnalysisBundle = result.bundle;
}

async function runSmartRecap(tone) {
  if (!activeSessionId.value) return;
  const result = await wrapCall("smartRecap", () =>
    api.runSmartRecap(activeSessionId.value, {
      apiKey: state.apiKey,
      tone,
    })
  );
  state.workspace.outputs.smartRecapBundle = result.bundle;
}

async function runContentRepurposing(outputLanguage = state.outputLanguage) {
  if (!activeSessionId.value) return;
  const result = await wrapCall("contentRepurposing", () =>
    api.runContentRepurposing(activeSessionId.value, {
      apiKey: state.apiKey,
      outputLanguage,
    })
  );
  state.workspace.outputs.contentRepurposeBundle = result.bundle;
}

export function useWorkspace() {
  return {
    state,
    activeSessionId,
    hasTranscriptData,
    isTranscriptLoading,
    applyBootstrap,
    loadEventSessions,
    fetchSessionData,
    resetWorkspace,
    saveSpeakerLabels,
    runAnalysis,
    runDeepAnalysis,
    runSmartRecap,
    runContentRepurposing,
  };
}
