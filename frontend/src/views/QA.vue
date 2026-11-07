<template>
  <main class="page">
    <h2>问答</h2>
    <div class="ask-box">
      <input v-model="question" placeholder="输入问题..." class="q-input" @keyup.enter="ask" />
      <button class="ask-btn" @click="ask" :disabled="!question || loading">
        {{ loading ? "思考中..." : "提问" }}
      </button>
    </div>
    <div class="answer" v-if="result">
      <p>{{ result.answer }}</p>
      <div v-if="result.citations?.length" class="citations">
        <h4>引用</h4>
        <div class="citation" v-for="(c, i) in result.citations" :key="i">
          <span class="cite-id">[{{ c.attachment_id }}:{{ c.chunk_index }}]</span>
          <span class="cite-quote">{{ c.quote }}</span>
        </div>
      </div>
    </div>
    <p class="error" v-if="error">{{ error }}</p>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "../api/client";
import { ApiError } from "../api/client";

const question = ref("");
const result = ref<any>(null);
const loading = ref(false);
const error = ref("");

async function ask() {
  if (!question.value.trim()) return;
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    const res = await api.post("/qa/ask", { question: question.value });
    result.value = res.data;
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "提问失败";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.ask-box { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.q-input { flex: 1; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius); }
.ask-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-3) var(--space-6); border-radius: var(--radius); font-weight: 600; }
.answer { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); }
.citations { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
.citation { font-size: var(--text-sm); margin-bottom: var(--space-2); }
.cite-id { color: var(--color-primary); margin-right: var(--space-2); }
.cite-quote { color: var(--color-text-muted); font-style: italic; }
.error { color: #dc2626; }
</style>
