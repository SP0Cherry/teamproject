<template>
  <div class="layout">
    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="brand">个人助手</div>
      <nav class="nav">
        <router-link to="/" class="nav-item" @click="onNavClick">首页</router-link>
        <router-link to="/notifications" class="nav-item" @click="onNavClick">通知</router-link>
        <router-link to="/schedule" class="nav-item" @click="onNavClick">日程</router-link>
        <router-link to="/todos/add" class="nav-item" @click="onNavClick">添加待办</router-link>
        <router-link to="/qa" class="nav-item" @click="onNavClick">问答</router-link>
        <router-link to="/groups" class="nav-item" @click="onNavClick">小组</router-link>
      </nav>
      <div class="sidebar-footer">
        <span class="username">{{ auth.username }}</span>
        <button class="logout-btn" @click="doLogout">退出</button>
      </div>
    </aside>
    <div class="backdrop" v-if="sidebarOpen && isMobile" @click="sidebarOpen = false"></div>
    <div class="main" :class="{ 'sidebar-collapsed': !sidebarOpen }">
      <header class="topbar">
        <button class="menu-btn" @click="sidebarOpen = !sidebarOpen" :title="sidebarOpen ? '收起侧边栏' : '展开侧边栏'">
          <span v-if="sidebarOpen">◀</span>
          <span v-else>☰</span>
        </button>
        <button class="api-btn" @click="openModal">
          <span class="api-dot" :class="{ active: llmConfigured }"></span>
          API 设置
        </button>
      </header>
      <router-view />
    </div>

    <!-- LLM API Settings Modal -->
    <div class="modal-overlay" v-if="apiModalOpen" @click.self="apiModalOpen = false">
      <div class="modal">
        <h3>LLM API 设置</h3>
        <p class="modal-hint">填写后仅保存在本地浏览器，用于 AI 解析待办。</p>
        <div class="form-group">
          <label>API Base URL</label>
          <input
            v-model="form.base_url"
            type="text"
            placeholder="https://api.deepseek.com/v1"
            class="form-input"
          />
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input
            v-model="form.api_key"
            type="password"
            placeholder="sk-..."
            class="form-input"
            autocomplete="off"
          />
        </div>
        <div class="form-group">
          <label>Model</label>
          <input
            v-model="form.model"
            type="text"
            placeholder="deepseek-chat"
            class="form-input"
          />
        </div>
        <div class="modal-actions">
          <button class="btn-clear" @click="clearConfig">清除</button>
          <button class="btn-cancel" @click="apiModalOpen = false">取消</button>
          <button class="btn-save" @click="saveConfig">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useLLMConfig } from "../composables/useLLMConfig";

const auth = useAuthStore();
const router = useRouter();
const isMobile = ref(false);
const sidebarOpen = ref(true);

function checkMobile() {
  isMobile.value = window.innerWidth < 768;
  if (isMobile.value) {
    sidebarOpen.value = false;
  }
}

onMounted(() => {
  checkMobile();
  window.addEventListener("resize", checkMobile);
});

onUnmounted(() => {
  window.removeEventListener("resize", checkMobile);
});

function onNavClick() {
  if (isMobile.value) {
    sidebarOpen.value = false;
  }
}

const { config, setConfig, clear, isConfigured } = useLLMConfig();
const apiModalOpen = ref(false);
const form = ref({
  base_url: config.value.base_url,
  api_key: config.value.api_key,
  model: config.value.model,
});

const llmConfigured = computed(() => isConfigured());

function openModal() {
  form.value = {
    base_url: config.value.base_url,
    api_key: config.value.api_key,
    model: config.value.model,
  };
  apiModalOpen.value = true;
}

function saveConfig() {
  setConfig({
    base_url: form.value.base_url.trim(),
    api_key: form.value.api_key.trim(),
    model: form.value.model.trim(),
  });
  apiModalOpen.value = false;
}

function clearConfig() {
  clear();
  form.value = { base_url: "", api_key: "", model: "" };
}

async function doLogout() {
  await auth.doLogout();
  router.push("/login");
}
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 240px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  transform: translateX(-100%);
  transition: transform 0.2s;
}
.sidebar.open {
  transform: translateX(0);
}
.main {
  flex: 1;
  margin-left: 0;
  transition: margin-left 0.2s;
}
@media (min-width: 768px) {
  .main:not(.sidebar-collapsed) {
    margin-left: 240px;
  }
  .main.sidebar-collapsed {
    margin-left: 0;
  }
}
.brand {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--color-primary);
  margin-bottom: var(--space-6);
}
.nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1;
}
.nav-item {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  color: var(--color-text);
  text-decoration: none;
  font-size: var(--text-sm);
}
.nav-item:hover,
.nav-item.router-link-active {
  background: var(--color-bg);
  color: var(--color-primary);
}
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}
.username {
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
.logout-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text);
}
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 99;
}
.topbar {
  display: flex;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.menu-btn {
  background: none;
  border: none;
  font-size: var(--text-lg);
  cursor: pointer;
}
.api-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text);
  cursor: pointer;
  margin-left: var(--space-3);
}
.api-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.api-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-muted);
}
.api-dot.active {
  background: #059669;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}
.modal {
  background: white;
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  width: 90%;
  max-width: 440px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}
.modal h3 {
  font-size: var(--text-lg);
  margin-bottom: var(--space-2);
}
.modal-hint {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-4);
}
.form-group {
  margin-bottom: var(--space-3);
}
.form-group label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 600;
  margin-bottom: 4px;
}
.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  box-sizing: border-box;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}
.btn-save {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius);
  font-weight: 600;
  cursor: pointer;
}
.btn-cancel {
  background: none;
  border: 1px solid var(--color-border);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  cursor: pointer;
}
.btn-clear {
  background: none;
  border: 1px solid #dc2626;
  color: #dc2626;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius);
  cursor: pointer;
  margin-right: auto;
}
@media (min-width: 768px) {
  .backdrop {
    display: none;
  }
}
</style>
