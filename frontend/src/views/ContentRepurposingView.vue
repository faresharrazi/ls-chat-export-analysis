<script setup>
import { computed, ref } from "vue";
import RichMarkdownCard from "../components/RichMarkdownCard.vue";
import { api } from "../api";
import { useWorkspace } from "../store/workspace";

const { state, runContentRepurposing, hasTranscriptData, isTranscriptLoading } = useWorkspace();

const activeLanguage = ref("English");
const activeContentType = ref("summary");

const languageTabs = [
  { id: "English", label: "English", icon: "🇬🇧" },
  { id: "French", label: "Français", icon: "🇫🇷" },
];

const contentTabs = [
  { id: "summary", label: "Summary" },
  { id: "blog", label: "Blog Post" },
  { id: "email", label: "Email Follow-up" },
  { id: "social_media", label: "Social Media Posts" },
];

const contentBundle = computed(() => state.workspace?.outputs?.contentRepurposeBundle || {});
const activeLanguageBundle = computed(() => contentBundle.value?.[activeLanguage.value] || {});
const activeBody = computed(() => String(activeLanguageBundle.value?.[activeContentType.value] || "").trim());
const hasActiveBody = computed(() => Boolean(activeBody.value));
const hasActiveLanguageContent = computed(() =>
  Object.values(activeLanguageBundle.value || {}).some((value) => String(value || "").trim())
);
const activePdfUrl = computed(() =>
  state.workspace?.sessionId
    ? api.getContentRepurposingPdfUrl(state.workspace.sessionId, activeLanguage.value, activeContentType.value)
    : "#"
);

const languageHint = computed(() =>
  activeLanguage.value === "English"
    ? "Content has already been generated for English. Switch language to generate the other version."
    : "Le contenu est deja genere en anglais. Passez en francais pour generer cette version."
);

async function generateForLanguage(language) {
  activeLanguage.value = language;
  await runContentRepurposing(language);
}
</script>

<template>
  <section class="page-section">
    <h2>Content Repurposing</h2>
    <p class="page-description">Turn the session into summary, blog, email, and social content.</p>

    <template v-if="state.workspace && hasTranscriptData">
      <p class="analysis-subcopy" v-if="contentBundle?.English">{{ languageHint }}</p>

      <div class="section-tabs analysis-language-tabs">
        <button
          v-for="tab in languageTabs"
          :key="tab.id"
          type="button"
          class="section-tab"
          :class="{ active: activeLanguage === tab.id }"
          @click="activeLanguage = tab.id"
        >
          {{ tab.icon }} {{ tab.label }}
        </button>
      </div>

      <div class="section-tabs">
        <button
          v-for="tab in contentTabs"
          :key="tab.id"
          type="button"
          class="section-tab"
          :class="{ active: activeContentType === tab.id }"
          @click="activeContentType = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="action-row" v-if="!hasActiveLanguageContent">
        <button class="primary" :disabled="state.loading.contentRepurposing" @click="generateForLanguage(activeLanguage)">
          {{ state.loading.contentRepurposing ? "Generating..." : `Generate ${activeLanguage} Content` }}
        </button>
      </div>

      <div class="action-row" v-else-if="hasActiveBody">
        <a class="ghost-link-button" :href="activePdfUrl">Download PDF</a>
      </div>

      <RichMarkdownCard :body="activeBody" empty-message="No content available yet for this section." />
    </template>
    <section v-else-if="isTranscriptLoading" class="panel loading-panel">
      <h3>Transcript still loading</h3>
      <p>Content Repurposing will become available once the transcript is ready.</p>
    </section>
  </section>
</template>
