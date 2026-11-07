<template>
  <main class="page">
    <h2>小组</h2>
    <div class="actions">
      <input v-model="newName" placeholder="小组名称" class="name-input" />
      <button class="create-btn" @click="createGroup">创建</button>
    </div>
    <div class="actions">
      <input v-model="inviteToken" placeholder="邀请令牌" class="token-input" />
      <button class="join-btn" @click="joinGroup">加入</button>
    </div>
    <div class="list" v-if="groups.length">
      <div class="card" v-for="g in groups" :key="g.id">
        <div class="card-title">{{ g.name }}</div>
        <div class="card-meta">ID: {{ g.id.slice(0, 8) }}</div>
      </div>
    </div>
    <p class="empty" v-else>暂无小组</p>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "../api/client";

const groups = ref<any[]>([]);
const newName = ref("");
const inviteToken = ref("");

async function load() {
  const res = await api.get("/groups");
  groups.value = res.data || [];
}

async function createGroup() {
  if (!newName.value.trim()) return;
  await api.post("/groups", { name: newName.value });
  newName.value = "";
  await load();
}

async function joinGroup() {
  if (!inviteToken.value.trim()) return;
  await api.post("/groups/join-by-token", { invite_token: inviteToken.value });
  inviteToken.value = "";
  await load();
}

onMounted(load);
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.actions { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.name-input, .token-input { flex: 1; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius); }
.create-btn, .join-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-2) var(--space-4); border-radius: var(--radius); }
.list { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-4); }
.card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); }
.card-title { font-size: var(--text-base); margin-bottom: var(--space-2); }
.card-meta { font-size: var(--text-xs); color: var(--color-text-muted); }
.empty { color: var(--color-text-muted); }
</style>
