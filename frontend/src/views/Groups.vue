<template>
  <main class="page">
    <h2>小组</h2>
    <div class="actions">
      <input v-model="newName" placeholder="小组名称" class="name-input" />
      <input v-model="newDesc" placeholder="描述（可选）" class="desc-input" />
      <button class="btn" :disabled="creating || !newName.trim()" @click="createGroup">
        {{ creating ? "创建中…" : "创建" }}
      </button>
    </div>
    <div class="actions">
      <input v-model="inviteToken" placeholder="邀请令牌" class="token-input" />
      <button class="btn" :disabled="joining || !inviteToken.trim()" @click="joinGroup">
        {{ joining ? "加入中…" : "加入" }}
      </button>
    </div>
    <p v-if="message" class="message" :class="{ error: isError }">{{ message }}</p>

    <div class="list" v-if="groups.length">
      <div
        class="card"
        v-for="g in groups"
        :key="g.id"
        @click="openDetail(g.id)"
      >
        <div class="card-title">{{ g.name }}</div>
        <div v-if="g.description" class="card-desc">{{ g.description }}</div>
        <div class="card-meta">
          <span>{{ g.member_count }} 名成员</span>
          <span class="role">{{ roleLabel(g.my_role) }}</span>
          <span :class="['sync', g.my_sync_enabled ? 'on' : 'off']">
            {{ g.my_sync_enabled ? "同步已开启" : "同步已关闭" }}
          </span>
        </div>
      </div>
    </div>
    <p class="empty" v-else>暂无小组，创建或凭邀请令牌加入一个吧</p>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { ApiError } from "../api/client";
import { listGroups, createGroup as createGroupApi, joinByToken, GroupSummary, GroupRole } from "../api/groups";

const router = useRouter();
const groups = ref<GroupSummary[]>([]);
const newName = ref("");
const newDesc = ref("");
const inviteToken = ref("");
const creating = ref(false);
const joining = ref(false);
const message = ref("");
const isError = ref(false);

function showMessage(text: string, error = false) {
  message.value = text;
  isError.value = error;
  if (!error) setTimeout(() => (message.value = ""), 2500);
}

function roleLabel(role: GroupRole): string {
  return role === "owner" ? "所有者" : role === "admin" ? "管理员" : "成员";
}

async function load() {
  try {
    const res = await listGroups();
    groups.value = res.data || [];
  } catch (e) {
    showMessage(e instanceof ApiError ? e.message : "加载失败", true);
  }
}

async function createGroup() {
  if (!newName.value.trim()) return;
  creating.value = true;
  try {
    await createGroupApi(newName.value.trim(), newDesc.value.trim() || undefined);
    newName.value = "";
    newDesc.value = "";
    showMessage("小组已创建");
    await load();
  } catch (e) {
    showMessage(e instanceof ApiError ? e.message : "创建失败", true);
  } finally {
    creating.value = false;
  }
}

async function joinGroup() {
  if (!inviteToken.value.trim()) return;
  joining.value = true;
  try {
    await joinByToken(inviteToken.value.trim());
    inviteToken.value = "";
    showMessage("已加入小组");
    await load();
  } catch (e) {
    showMessage(e instanceof ApiError ? e.message : "加入失败", true);
  } finally {
    joining.value = false;
  }
}

function openDetail(id: string) {
  router.push(`/groups/${id}`);
}

onMounted(load);
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); max-width: 720px; margin: 0 auto; }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.actions { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.name-input, .desc-input, .token-input {
  padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius);
  font-size: var(--text-sm);
}
.name-input { flex: 2; }
.desc-input { flex: 3; }
.token-input { flex: 1; }
.btn {
  background: var(--color-primary); color: white; border: none;
  padding: var(--space-2) var(--space-4); border-radius: var(--radius); font-size: var(--text-sm);
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.message { font-size: var(--text-sm); margin-bottom: var(--space-3); color: var(--color-text-muted); }
.message.error { color: #dc2626; }
.list { display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-4); }
.card {
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius); padding: var(--space-4); cursor: pointer; transition: border-color 0.15s;
}
.card:hover { border-color: var(--color-primary); }
.card-title { font-size: var(--text-base); margin-bottom: var(--space-1); font-weight: 600; }
.card-desc { font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.card-meta { display: flex; gap: var(--space-4); font-size: var(--text-xs); color: var(--color-text-muted); flex-wrap: wrap; }
.role { background: var(--color-bg); padding: 1px 6px; border-radius: 4px; }
.sync.on { color: #166534; }
.sync.off { color: var(--color-text-muted); }
.empty { color: var(--color-text-muted); margin-top: var(--space-4); }
</style>
