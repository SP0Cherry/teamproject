<template>
  <main class="page">
    <h2>通知</h2>

    <section class="preview">
      <h3>解析预览</h3>
      <textarea v-model="parseText" rows="3" placeholder="粘贴通知原文，预览解析与工具调用..." class="parse-input"></textarea>
      <button class="parse-btn" @click="parse" :disabled="!parseText || parseLoading">
        {{ parseLoading ? "解析中..." : "解析" }}
      </button>

      <div class="tool-calls" v-if="parseToolCalls.length">
        <h4>工具调用</h4>
        <div class="tool-row" v-for="(t, i) in parseToolCalls" :key="i">
          <span class="tool-name">{{ t.tool }}</span>
          <span class="tool-status" :class="t.status">{{ statusLabel(t.status) }}</span>
        </div>
      </div>

      <div class="parse-result" v-if="parseResult">
        <h4>解析结果</h4>
        <p class="parse-title" v-if="parseResult.title">{{ parseResult.title }}</p>
        <div class="candidate" v-for="(c, i) in parseResult.items" :key="i">
          <span class="cand-text">{{ c.text }}</span>
          <span class="cand-time" v-if="c.date || c.time">{{ c.date }} {{ c.time || "" }}</span>
          <span class="cand-basis" v-if="c.date_basis">{{ c.date_basis.source === 'source_text' ? '原文基准' : '按发送当天推算' }}</span>
        </div>
        <p v-if="!parseResult.items?.length">未识别到行动事项</p>
      </div>
      <p class="error" v-if="parseError">{{ parseError }}</p>
    </section>

    <h3 class="list-title">我的通知</h3>
    <div class="list" v-if="notifs.length">
      <router-link
        v-for="n in notifs"
        :key="n.id"
        :to="`/notifications/${n.id}`"
        class="card"
      >
        <div class="card-title">{{ n.raw_text }}</div>
        <div class="card-meta">
          <span class="source">{{ n.source }}</span>
          <span class="status" :class="n.status">{{ statusLabel(n.status) }}</span>
        </div>
      </router-link>
    </div>
    <p class="empty" v-else>暂无通知</p>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { listNotifications, Notification } from "../api/notifications";
import { postSSE } from "../api/sse";

const notifs = ref<Notification[]>([]);
const parseText = ref("");
const parseLoading = ref(false);
const parseError = ref("");
const parseToolCalls = ref<Array<{ tool: string; status: string }>>([]);
const parseResult = ref<any>(null);

function statusLabel(s: string) {
  return {
    pending: "待确认", confirmed: "已确认", discarded: "已忽略",
    success: "成功", rejected: "被拒", error: "出错",
  }[s] || s;
}

async function parse() {
  if (!parseText.value.trim()) return;
  parseLoading.value = true;
  parseError.value = "";
  parseToolCalls.value = [];
  parseResult.value = null;
  try {
    await postSSE("/notifications/parse", { text: parseText.value }, {
      onEvent: (event, data) => {
        if (event === "tool") parseToolCalls.value.push(data);
        else if (event === "meta") parseToolCalls.value = data?.tool_calls || [];
        else if (event === "data") parseResult.value = data;
      },
      onError: (_code, message) => {
        parseError.value = message || "解析失败";
      },
      onDone: () => {
        parseLoading.value = false;
      },
    });
  } catch {
    parseError.value = "解析失败";
  } finally {
    parseLoading.value = false;
  }
}

onMounted(async () => {
  const res = await listNotifications();
  notifs.value = res.data || [];
});
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
h3 { font-size: var(--text-base); margin-bottom: var(--space-3); }
.preview { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); margin-bottom: var(--space-6); }
.parse-input { width: 100%; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius); font-size: var(--text-sm); resize: vertical; box-sizing: border-box; }
.parse-btn { margin-top: var(--space-2); background: var(--color-primary); color: white; border: none; padding: var(--space-2) var(--space-5); border-radius: var(--radius); font-weight: 600; }
.tool-calls { margin-top: var(--space-3); }
.tool-calls h4, .parse-result h4 { font-size: var(--text-sm); color: var(--color-text-muted); margin: var(--space-2) 0; }
.tool-row { display: flex; gap: var(--space-2); align-items: center; font-size: var(--text-sm); margin-bottom: 2px; }
.tool-name { font-family: monospace; }
.tool-status { padding: 1px 8px; border-radius: 999px; font-size: var(--text-xs); }
.tool-status.success { background: #dcfce7; color: #166534; }
.tool-status.rejected { background: #fef3c7; color: #92400e; }
.tool-status.error { background: #fee2e2; color: #991b1b; }
.parse-title { font-weight: 600; margin-bottom: var(--space-2); }
.candidate { font-size: var(--text-sm); margin-bottom: var(--space-1); display: flex; gap: var(--space-2); flex-wrap: wrap; }
.cand-time { color: var(--color-primary); }
.cand-basis { color: var(--color-text-muted); font-size: var(--text-xs); }
.list-title { margin-top: var(--space-4); }
.list { display: flex; flex-direction: column; gap: var(--space-3); }
.card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); text-decoration: none; color: inherit; }
.card-title { font-size: var(--text-base); margin-bottom: var(--space-2); }
.card-meta { display: flex; gap: var(--space-3); font-size: var(--text-xs); color: var(--color-text-muted); }
.status.pending { color: #d97706; }
.status.confirmed { color: #059669; }
.status.discarded { color: var(--color-text-muted); }
.empty { color: var(--color-text-muted); }
.error { color: #dc2626; font-size: var(--text-sm); margin-top: var(--space-2); }
</style>
