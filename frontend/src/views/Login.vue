<template>
  <div class="auth-page">
    <form class="auth-card" @submit.prevent="onSubmit">
      <h1>登录</h1>
      <div class="field">
        <label for="username">账号</label>
        <input
          id="username"
          v-model="username"
          type="text"
          autocomplete="username"
          required
        />
      </div>
      <div class="field">
        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </div>
      <p class="error" v-if="error">{{ error }}</p>
      <button type="submit" class="primary-btn" :disabled="loading">
        {{ loading ? "登录中..." : "登录" }}
      </button>
      <p class="hint">
        还没有账号？<router-link to="/register">注册</router-link>
      </p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { ApiError } from "../api/client";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch (e) {
    error.value = e instanceof ApiError ? "账号或密码错误" : "网络错误";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
}
.auth-card {
  width: 100%;
  max-width: 360px;
  background: var(--color-surface);
  padding: var(--space-8);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
h1 {
  font-size: var(--text-xl);
  text-align: center;
}
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
label {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
input {
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  font-size: var(--text-base);
  outline: none;
}
input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.2);
}
.primary-btn {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: var(--space-3);
  border-radius: var(--radius);
  font-size: var(--text-base);
  font-weight: 600;
}
.primary-btn:disabled {
  opacity: 0.6;
}
.error {
  color: #dc2626;
  font-size: var(--text-sm);
}
.hint {
  text-align: center;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
.hint a {
  color: var(--color-primary);
}
</style>
