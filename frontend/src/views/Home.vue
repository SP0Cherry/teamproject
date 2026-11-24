<template>
  <main class="page">
    <div class="header">
      <h2>今日清单</h2>
      <button class="refresh-btn" @click="load" :disabled="loading">
        {{ loading ? "刷新中..." : "刷新" }}
      </button>
    </div>
    <p class="updated" v-if="data">更新于 {{ formatTime(data.updated_at) }}</p>

    <section v-if="data?.overdue.length" class="group overdue">
      <h3>逾期</h3>
      <div class="todo" v-for="t in data.overdue" :key="t.id">{{ t.title }} <span>{{ formatTodoTime(t) }}</span></div>
    </section>

    <section v-if="data?.today.length" class="group today">
      <h3>今日</h3>
      <div class="todo" v-for="t in data.today" :key="t.id">{{ t.title }} <span>{{ formatTodoTime(t) }}</span></div>
    </section>

    <section v-if="data?.upcoming.length" class="group upcoming">
      <h3>未来七天</h3>
      <div class="todo" v-for="t in data.upcoming" :key="t.id">{{ t.title }} <span>{{ formatTodoTime(t) }}</span></div>
    </section>

    <p class="empty" v-if="data && !data.overdue.length && !data.today.length && !data.upcoming.length">
      暂无待办
    </p>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { formatTodoTime, splitInstant } from "../utils/time.mjs";
import { api } from "../api/client";

const data = ref<any>(null);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const res = await api.get("/home/checklist");
    data.value = res.data;
  } finally {
    loading.value = false;
  }
}

function formatTime(s: string) {
  const value = splitInstant(s);
  return `${value.date} ${value.time}`;
}

onMounted(load);
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2); }
h2 { font-size: var(--text-lg); }
.refresh-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-2) var(--space-4); border-radius: var(--radius); font-size: var(--text-sm); }
.updated { font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-4); }
.group { margin-bottom: var(--space-6); }
.group h3 { font-size: var(--text-base); margin-bottom: var(--space-2); }
.group.overdue h3 { color: #dc2626; }
.group.today h3 { color: var(--color-primary); }
.group.upcoming h3 { color: var(--color-text-muted); }
.todo {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-2);
}
.empty { color: var(--color-text-muted); }
</style>
