<template>
  <main class="page">
    <h2>通知</h2>
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

const notifs = ref<Notification[]>([]);

function statusLabel(s: string) {
  return { pending: "待确认", confirmed: "已确认", discarded: "已忽略" }[s] || s;
}

onMounted(async () => {
  const res = await listNotifications();
  notifs.value = res.data || [];
});
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.list { display: flex; flex-direction: column; gap: var(--space-3); }
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-4);
  text-decoration: none;
  color: inherit;
}
.card-title { font-size: var(--text-base); margin-bottom: var(--space-2); }
.card-meta { display: flex; gap: var(--space-3); font-size: var(--text-xs); color: var(--color-text-muted); }
.status.pending { color: #d97706; }
.status.confirmed { color: #059669; }
.status.discarded { color: var(--color-text-muted); }
.empty { color: var(--color-text-muted); }
</style>
