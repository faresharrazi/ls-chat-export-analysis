<script setup>
import { computed } from "vue";

const props = defineProps({
  state: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["fetch", "connect", "logout"]);
const isOAuthMode = computed(() => props.state.auth?.oauthEnabled);
const isConnected = computed(() => Boolean(props.state.auth?.connectedUser));
</script>

<template>
  <section class="control-card">
    <div v-if="!isOAuthMode" class="field-group">
      <input v-model="props.state.apiKey" type="password" placeholder="Livestorm API Key" />
    </div>

    <div v-else class="field-group oauth-panel">
      <button v-if="!isConnected" class="primary fetch-button oauth-connect-button" @click="emit('connect')">
        Connect with Livestorm
      </button>
      <div v-else class="oauth-connected-card">
        <div class="oauth-connected-title">Connected with Livestorm</div>
        <div class="oauth-connected-meta">
          <strong>{{ props.state.auth.connectedUser.fullName || props.state.auth.connectedUser.email }}</strong>
        </div>
        <div v-if="props.state.auth.connectedUser.organizationName" class="oauth-connected-meta">
          {{ props.state.auth.connectedUser.organizationName }}
        </div>
        <button class="secondary oauth-disconnect-button" @click="emit('logout')">Disconnect</button>
      </div>
    </div>

    <div class="field-group">
      <div class="toggle-row">
        <button :class="{ active: props.state.inputMode === 'session' }" @click="props.state.inputMode = 'session'">Session ID</button>
        <button :class="{ active: props.state.inputMode === 'event' }" @click="props.state.inputMode = 'event'">Event ID</button>
      </div>
    </div>

    <div v-if="props.state.inputMode === 'session'" class="field-group">
      <input v-model="props.state.sessionId" type="text" placeholder="Session ID" />
    </div>

    <div v-else class="field-group">
      <input v-model="props.state.eventId" type="text" placeholder="Event ID" />
      <select v-model="props.state.selectedEventSessionId" v-if="props.state.eventSessions.length">
        <option value="">Select a past session</option>
        <option v-for="session in props.state.eventSessions" :key="session.id" :value="session.id">
          {{ session.label }}
        </option>
      </select>
      <p v-if="props.state.selectedEventSessionId" class="field-hint">{{ props.state.selectedEventSessionId }}</p>
    </div>

    <button
      class="primary fetch-button"
      :disabled="
        props.state.loading.sessionFetch ||
        props.state.loading.eventSessions ||
        (!isOAuthMode && !props.state.apiKey) ||
        (isOAuthMode && !isConnected) ||
        !(props.state.inputMode === 'session' ? props.state.sessionId.trim() : props.state.eventId.trim())
      "
      @click="emit('fetch')"
    >
      {{ props.state.loading.sessionFetch || props.state.loading.eventSessions ? "Fetching..." : "Fetch Data" }}
    </button>
  </section>
</template>
