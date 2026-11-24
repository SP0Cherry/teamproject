<template>
  <main class="page">
    <button class="back-btn" @click="goBack">← 返回小组列表</button>

    <div v-if="groupLoading" class="state">正在加载小组…</div>
    <div v-else-if="groupError" class="state error">
      小组加载失败，可能是无权访问或网络异常，请返回列表重试。
      <button class="retry-btn" @click="loadGroup">重试</button>
    </div>

    <template v-else-if="group">
      <h2>{{ group.name }}</h2>
      <p v-if="group.description" class="desc">{{ group.description }}</p>

      <div class="sections">
        <!-- 组信息 -->
        <section class="card">
          <h3>组信息</h3>
          <div class="row">
            <span class="label">邀请令牌</span>
            <code class="token">{{ group.invite_token }}</code>
            <button class="btn" @click="copyToken">{{ copied ? '已复制' : '复制' }}</button>
            <button
              v-if="isAdmin"
              class="btn"
              :disabled="regenLoading"
              @click="regenerateToken"
            >
              重置令牌
            </button>
          </div>
          <div class="row">
            <button
              v-if="!isOwner"
              class="btn btn-danger"
              :disabled="leaveLoading"
              @click="leaveGroup"
            >
              退出小组
            </button>
            <span v-else class="muted">owner 需先转让所有权才能退出</span>
          </div>
          <p v-if="infoMsg" class="muted">{{ infoMsg }}</p>
        </section>

        <!-- 成员 -->
        <section class="card">
          <h3>成员（{{ members.length }}）</h3>
          <div v-if="membersLoading" class="state">正在加载成员…</div>
          <div v-else-if="membersError" class="state error">
            成员加载失败
            <button class="retry-btn" @click="loadMembers">重试</button>
          </div>
          <ul v-else class="member-list">
            <li v-for="m in members" :key="m.user_id" class="member-row">
              <span class="member-name">
                {{ m.username }}
                <em class="role">{{ roleLabel(m.role) }}</em>
                <span v-if="m.user_id === auth.userId" class="muted">（我）</span>
              </span>
              <span class="muted joined">{{ formatJoined(m.joined_at) }}</span>
              <button
                v-if="canRemove(m)"
                class="btn btn-danger btn-sm"
                :disabled="removeLoading === m.user_id"
                @click="removeMember(m)"
              >
                移除
              </button>
            </li>
          </ul>
        </section>

        <!-- 通知同步 -->
        <section class="card">
          <h3>通知同步</h3>
          <label class="switch-row">
            <input
              type="checkbox"
              :checked="syncEnabled"
              :disabled="syncLoading"
              @change="toggleSync"
            />
            同步组通知到我的待办
          </label>
          <p class="muted">
            开启后，本组新发布的通知会同步为你的个人待办；关闭后停止后续同步，已有待办保留。
          </p>
        </section>

        <!-- 组通知 -->
        <section class="card">
          <h3>组通知</h3>
          <div v-if="isAdmin" class="publish-row">
            <textarea
              v-model="publishText"
              class="publish-input"
              placeholder="输入通知文本，发布后开启同步的成员会收到个人待办…"
              rows="2"
            />
            <button
              class="btn"
              :disabled="publishLoading || !publishText.trim()"
              @click="publishNotification"
            >
              发布
            </button>
          </div>
          <p v-if="publishMsg" class="muted">{{ publishMsg }}</p>
          <div v-if="notifsLoading" class="state">正在加载通知…</div>
          <ul v-else class="notif-list">
            <li v-for="n in notifs" :key="n.id" class="notif-row">
              <span class="notif-text">{{ n.raw_text }}</span>
              <span class="tag" :class="{ withdrawn: !n.published }">
                {{ n.published ? '已发布' : '已撤回' }}
              </span>
              <button
                v-if="isAdmin && n.published"
                class="btn btn-sm"
                @click="withdrawNotification(n)"
              >
                撤回
              </button>
            </li>
            <li v-if="!notifs.length" class="muted">暂无组通知</li>
          </ul>
        </section>

        <!-- 组资料 -->
        <section class="card">
          <h3>组资料</h3>
          <div class="upload-row">
            <input type="file" @change="onFileChange" />
            <button
              class="btn"
              :disabled="!selectedFile || uploadLoading"
              @click="uploadAttachment"
            >
              上传
            </button>
          </div>
          <p v-if="uploadMsg" class="muted">{{ uploadMsg }}</p>
          <div v-if="attsLoading" class="state">正在加载资料…</div>
          <ul v-else class="att-list">
            <li v-for="a in atts" :key="a.id" class="att-row">
              <span>{{ a.filename }} <em class="muted">{{ a.status }}</em></span>
              <button
                v-if="isAdmin"
                class="btn btn-danger btn-sm"
                @click="deleteAttachment(a)"
              >
                删除
              </button>
            </li>
            <li v-if="!atts.length" class="muted">暂无组资料</li>
          </ul>
        </section>
      </div>
    </template>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { ApiError } from "../api/client";
import {
  getGroup,
  leaveGroup as leaveGroupApi,
  listMembers,
  regenerateToken as regenerateTokenApi,
  removeMember as removeMemberApi,
  setSync,
  GroupDetail,
  GroupMember,
} from "../api/groups";
import {
  publishGroupNotification,
  listGroupNotifications,
  withdrawNotification as withdrawNotificationApi,
  GroupNotificationItem,
} from "../api/notifications";
import {
  listAttachments,
  uploadAttachment as uploadAttachmentApi,
  deleteAttachment as deleteAttachmentApi,
  Attachment,
} from "../api/attachments";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const groupId = route.params.id as string;

const group = ref<GroupDetail | null>(null);
const groupLoading = ref(true);
const groupError = ref(false);

const members = ref<GroupMember[]>([]);
const membersLoading = ref(false);
const membersError = ref(false);

const notifs = ref<GroupNotificationItem[]>([]);
const notifsLoading = ref(false);

const atts = ref<Attachment[]>([]);
const attsLoading = ref(false);

const syncEnabled = ref(false);
const syncLoading = ref(false);

const isAdmin = computed(() => {
  const r = group.value?.my_role;
  return r === "owner" || r === "admin";
});
const isOwner = computed(() => group.value?.my_role === "owner");

const copied = ref(false);
const regenLoading = ref(false);
const leaveLoading = ref(false);
const removeLoading = ref<string | null>(null);
const infoMsg = ref("");

const publishText = ref("");
const publishLoading = ref(false);
const publishMsg = ref("");

const selectedFile = ref<File | null>(null);
const uploadLoading = ref(false);
const uploadMsg = ref("");

function errMsg(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

async function loadGroup() {
  groupLoading.value = true;
  groupError.value = false;
  try {
    const res = await getGroup(groupId);
    group.value = res.data;
    syncEnabled.value = res.data?.my_sync_enabled ?? false;
    await Promise.all([loadMembers(), loadNotifs(), loadAtts()]);
  } catch {
    groupError.value = true;
  } finally {
    groupLoading.value = false;
  }
}

async function loadMembers() {
  membersLoading.value = true;
  membersError.value = false;
  try {
    const res = await listMembers(groupId);
    members.value = res.data || [];
  } catch {
    membersError.value = true;
  } finally {
    membersLoading.value = false;
  }
}

async function loadNotifs() {
  notifsLoading.value = true;
  try {
    const res = await listGroupNotifications(groupId);
    notifs.value = res.data || [];
  } catch {
    notifs.value = [];
  } finally {
    notifsLoading.value = false;
  }
}

async function loadAtts() {
  attsLoading.value = true;
  try {
    const res = await listAttachments(groupId);
    atts.value = res.data || [];
  } catch {
    atts.value = [];
  } finally {
    attsLoading.value = false;
  }
}

function goBack() {
  router.push("/groups");
}

function roleLabel(role: string): string {
  return role === "owner" ? "所有者" : role === "admin" ? "管理员" : "成员";
}

function formatJoined(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function canRemove(m: GroupMember): boolean {
  if (!isAdmin.value) return false;
  if (m.user_id === auth.userId) return false;
  if (m.role === "owner") return false;
  return true;
}

async function copyToken() {
  if (!group.value) return;
  try {
    await navigator.clipboard.writeText(group.value.invite_token);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    infoMsg.value = "复制失败，请手动选择令牌文本";
  }
}

async function regenerateToken() {
  regenLoading.value = true;
  infoMsg.value = "";
  try {
    const res = await regenerateTokenApi(groupId);
    if (group.value && res.data) group.value.invite_token = res.data.invite_token;
    infoMsg.value = "邀请令牌已重置";
  } catch (e) {
    infoMsg.value = errMsg(e, "重置失败");
  } finally {
    regenLoading.value = false;
  }
}

async function leaveGroup() {
  if (!confirm("确定退出该小组？已同步的待办会保留。")) return;
  leaveLoading.value = true;
  try {
    await leaveGroupApi(groupId);
    router.push("/groups");
  } catch (e) {
    infoMsg.value = errMsg(e, "退出失败");
    leaveLoading.value = false;
  }
}

async function removeMember(m: GroupMember) {
  if (!confirm(`确定移除成员 ${m.username}？`)) return;
  removeLoading.value = m.user_id;
  try {
    await removeMemberApi(groupId, m.user_id);
    await loadMembers();
  } catch (e) {
    infoMsg.value = errMsg(e, "移除失败");
  } finally {
    removeLoading.value = null;
  }
}

async function toggleSync(e: Event) {
  const target = e.target as HTMLInputElement;
  const next = target.checked;
  syncLoading.value = true;
  try {
    const res = await setSync(groupId, next);
    syncEnabled.value = res.data?.sync_enabled ?? next;
  } catch {
    syncEnabled.value = !next;
  } finally {
    syncLoading.value = false;
  }
}

async function publishNotification() {
  const text = publishText.value.trim();
  if (!text) return;
  publishLoading.value = true;
  publishMsg.value = "";
  try {
    const res = await publishGroupNotification(groupId, text);
    const count = res.data?.candidates?.items?.length ?? 0;
    publishMsg.value = `发布成功，解析出 ${count} 个候选事项`;
    publishText.value = "";
    await loadNotifs();
  } catch (e) {
    publishMsg.value = errMsg(e, "发布失败");
  } finally {
    publishLoading.value = false;
  }
}

async function withdrawNotification(n: GroupNotificationItem) {
  if (!confirm("确定撤回该通知？将停止同步提醒。")) return;
  try {
    await withdrawNotificationApi(n.id);
    await loadNotifs();
  } catch (e) {
    publishMsg.value = errMsg(e, "撤回失败");
  }
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
}

async function uploadAttachment() {
  if (!selectedFile.value) return;
  uploadLoading.value = true;
  uploadMsg.value = "";
  try {
    await uploadAttachmentApi(selectedFile.value, groupId);
    uploadMsg.value = "上传成功，正在处理";
    selectedFile.value = null;
    await loadAtts();
  } catch (e) {
    uploadMsg.value = errMsg(e, "上传失败");
  } finally {
    uploadLoading.value = false;
  }
}

async function deleteAttachment(a: Attachment) {
  if (!confirm(`确定删除资料 ${a.filename}？`)) return;
  try {
    await deleteAttachmentApi(a.id);
    await loadAtts();
  } catch (e) {
    uploadMsg.value = errMsg(e, "删除失败");
  }
}

onMounted(loadGroup);
</script>

<style scoped>
.page {
  padding: var(--space-6) var(--space-4);
  max-width: 880px;
  margin: 0 auto;
}
.back-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
  padding: 0;
}
h2 {
  font-size: var(--text-xl);
  margin-bottom: var(--space-2);
}
.desc {
  color: var(--color-text-muted);
  margin-bottom: var(--space-6);
}
.sections {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-4);
}
.card h3 {
  font-size: var(--text-base);
  margin-bottom: var(--space-3);
}
.row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-2);
}
.label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
.token {
  background: var(--color-bg);
  padding: 2px var(--space-2);
  border-radius: 4px;
  font-size: var(--text-xs);
  word-break: break-all;
}
.muted {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.state {
  padding: var(--space-4);
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}
.state.error {
  color: #dc2626;
}
.retry-btn {
  margin-left: var(--space-2);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
}
.btn {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  font-size: var(--text-sm);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-danger {
  background: #dc2626;
}
.btn-sm {
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
}
.member-list,
.notif-list,
.att-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.member-row,
.notif-row,
.att-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
  font-size: var(--text-sm);
}
.member-row:last-child,
.notif-row:last-child,
.att-row:last-child {
  border-bottom: none;
}
.member-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.role {
  font-style: normal;
  font-size: var(--text-xs);
  background: var(--color-bg);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--color-text-muted);
}
.joined {
  margin-left: auto;
  margin-right: var(--space-2);
}
.switch-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  margin-bottom: var(--space-2);
}
.publish-row,
.upload-row {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  align-items: flex-start;
}
.publish-input {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  font-family: inherit;
  resize: vertical;
}
.notif-text {
  flex: 1;
  word-break: break-word;
}
.tag {
  font-size: var(--text-xs);
  padding: 1px 6px;
  border-radius: 4px;
  background: #dcfce7;
  color: #166534;
}
.tag.withdrawn {
  background: #fee2e2;
  color: #991b1b;
}
</style>
