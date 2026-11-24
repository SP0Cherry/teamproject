<template>
  <main class="page" v-if="notif">
    <h2>确认通知</h2>
    <div class="layout">
      <section class="pane original">
        <h3>原文</h3>
        <pre>{{ notif.raw_text }}</pre>
        <div class="source-tag">来源: {{ notif.source }}</div>
      </section>
      <section class="pane candidates">
        <h3>候选待办</h3>
        <div class="candidate" v-for="(c, i) in candidates" :key="i">
          <input
            v-model="c.title"
            placeholder="待办标题"
            class="title-input"
          />
          <label>日期<input type="date" v-model="c.date" @change="c.date_manually_edited = true" /></label>
          <label>时间<input type="time" v-model="c.time" /></label>
          <div v-if="c.date_basis && c.date_expression">
            <label>{{ c.date_basis.source === 'source_text' ? '原文日期基准' : '按发送当天推算，待确认' }}（{{ c.date_basis.timezone }}）
              <input type="date" v-model="c.date_basis.date" @change="rebaseCandidates(candidates, i)" />
            </label>
          </div>
          <p v-if="c.warnings?.length">{{ c.warnings.join('；') }}</p>
          <p v-if="c.source_text">原文：{{ c.source_text }}</p>
          <label class="notes-field">注意事项
            <textarea v-model="c.notes" rows="2" class="notes-input" placeholder="无"></textarea>
          </label>
          <label v-if="c.time && !c.date"><input type="checkbox" v-model="c.accept_no_deadline" />接受无截止日期</label>
          <button class="remove-btn" @click="removeCandidate(i)">删除</button>
        </div>
        <button class="add-btn" @click="addCandidate">+ 添加候选</button>
        <div class="actions">
          <button class="primary-btn" @click="confirm" :disabled="loading">
            {{ loading ? "确认中..." : "确认生成待办" }}
          </button>
          <button class="ghost-btn" @click="discard">忽略</button>
        </div>
        <p class="error" v-if="error">{{ error }}</p>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { editableTime, timePayload, rebaseCandidates } from "../utils/time.mjs";
import { useRoute, useRouter } from "vue-router";
import { getNotification, confirmNotification, discardNotification, NotificationCandidate } from "../api/notifications";
import { ApiError } from "../api/client";

const route = useRoute();
const router = useRouter();
const notif = ref<any>(null);
const candidates = ref<NotificationCandidate[]>([]);
const loading = ref(false);
const error = ref("");

function addCandidate() {
  candidates.value.push({ title: "", deadline: null });
}

function removeCandidate(i: number) {
  candidates.value.splice(i, 1);
}

async function confirm() {
  error.value = "";
  const valid = candidates.value.filter((c) => c.title && c.title.trim());
  if (valid.length === 0) {
    error.value = "至少需要一个有效的待办标题";
    return;
  }
  loading.value = true;
  try {
    await confirmNotification(route.params.id as string, valid.map(timePayload));
    router.push("/todos");
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "确认失败";
  } finally {
    loading.value = false;
  }
}

async function discard() {
  await discardNotification(route.params.id as string);
  router.push("/notifications");
}

onMounted(async () => {
  const res = await getNotification(route.params.id as string);
  notif.value = res.data;
  const cands = res.data?.candidates?.items || [];
  candidates.value = cands.map((c: any) => ({
    ...editableTime(c),
    title: c.text || c.title || "",
  }));
});
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.layout {
  display: flex;
  gap: var(--space-4);
  flex-direction: column;
}
.pane {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-4);
  flex: 1;
}
.pane h3 { font-size: var(--text-base); margin-bottom: var(--space-3); }
pre { white-space: pre-wrap; font-size: var(--text-sm); }
.source-tag { font-size: var(--text-xs); color: var(--text-muted); margin-top: var(--space-2); }
.notes-field { display: flex; flex-direction: column; gap: var(--space-1); width: 100%; font-size: var(--text-sm); color: var(--color-text-muted); }
.notes-input { width: 100%; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius); font-size: var(--text-sm); resize: vertical; }
.candidate {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
}
.title-input { flex: 1; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius); }
.deadline-input { width: 180px; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius); }
.remove-btn { background: none; border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-1) var(--space-3); font-size: var(--text-xs); }
.add-btn { background: none; border: 1px dashed var(--color-border); border-radius: var(--radius); padding: var(--space-2) var(--space-3); width: 100%; margin-bottom: var(--space-4); color: var(--color-text-muted); }
.actions { display: flex; gap: var(--space-3); }
.primary-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-3) var(--space-6); border-radius: var(--radius); font-weight: 600; }
.ghost-btn { background: none; border: 1px solid var(--color-border); padding: var(--space-3) var(--space-6); border-radius: var(--radius); }
.error { color: #dc2626; font-size: var(--text-sm); margin-top: var(--space-2); }
@media (min-width: 768px) {
  .layout { flex-direction: row; }
}
</style>
