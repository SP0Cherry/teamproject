<template>
  <main class="page">
    <h2>问答</h2>
    <div class="ask-box">
      <input v-model="question" placeholder="输入问题..." class="q-input" @keyup.enter="ask" />
      <button class="ask-btn" @click="ask" :disabled="!question || loading">
        {{ loading ? "思考中..." : "提问" }}
      </button>
    </div>

    <div class="tool-calls" v-if="toolCalls.length">
      <h4>工具调用</h4>
      <div class="tool-row" v-for="(t, i) in toolCalls" :key="i">
        <span class="tool-name">{{ t.tool }}</span>
        <span class="tool-status" :class="t.status">{{ statusLabel(t.status) }}</span>
        <span class="tool-dur" v-if="t.duration_ms != null">{{ t.duration_ms }}ms</span>
      </div>
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
import { postSSE } from "../api/sse";

interface ToolCall {
  tool: string;
  name?: string;
  server?: string | null;
  status: string;
  duration_ms?: number;
}

const question = ref("");
const result = ref<any>(null);
const toolCalls = ref<ToolCall[]>([]);
const loading = ref(false);
const error = ref("");

function statusLabel(s: string) {
  return { success: "成功", rejected: "被拒", error: "出错" }[s] || s;
}

async function ask() {
  if (!question.value.trim()) return;
  loading.value = true;
  error.value = "";
  result.value = null;
  toolCalls.value = [];
  try {
    await postSSE("/qa/ask", { question: question.value }, {
      onEvent: (event, data) => {
        if (event === "tool") {
          toolCalls.value.push(data as ToolCall);
        } else if (event === "meta") {
          // canonical list from the server
          toolCalls.value = (data?.tool_calls || []) as ToolCall[];
        } else if (event === "data") {
          result.value = data;
        }
      },
      onError: (_code, message) => {
        error.value = message || "提问失败";
      },
      onDone: () => {
        loading.value = false;
      },
    });
  } catch {
    error.value = "提问失败";
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
.tool-calls { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-4); }
.tool-calls h4 { font-size: var(--text-sm); margin-bottom: var(--space-2); color: var(--color-text-muted); }
.tool-row { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); margin-bottom: var(--space-1); }
.tool-name { font-family: monospace; }
.tool-status { padding: 1px 8px; border-radius: 999px; font-size: var(--text-xs); }
.tool-status.success { background: #dcfce7; color: #166534; }
.tool-status.rejected { background: #fef3c7; color: #92400e; }
.tool-status.error { background: #fee2e2; color: #991b1b; }
.tool-dur { color: var(--color-text-muted); font-size: var(--text-xs); }
.answer { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); }
.citations { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--color-border); }
.citation { font-size: var(--text-sm); margin-bottom: var(--space-2); }
.cite-id { color: var(--color-primary); margin-right: var(--space-2); }
.cite-quote { color: var(--color-text-muted); font-style: italic; }
.error { color: #dc2626; }
</style>
