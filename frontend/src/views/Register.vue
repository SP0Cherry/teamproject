<template>
  <div class="auth-page">
    <form class="auth-card" @submit.prevent="onSubmit">
      <h1>注册</h1>
      <div class="field">
        <label for="username">账号</label>
        <input
          id="username"
          v-model="username"
          type="text"
          autocomplete="username"
          minlength="3"
          maxlength="64"
          required
        />
      </div>
      <div class="field">
        <label for="password">密码</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          maxlength="128"
          required
        />
      </div>
      <p class="error" v-if="error">{{ error }}</p>
      <button type="submit" class="primary-btn" :disabled="loading">
        {{ loading ? "注册中..." : "注册" }}
      </button>
      <p class="hint">
        已有账号？<router-link to="/login">登录</router-link>
      </p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { register } from "../api/auth";
import { ApiError } from "../api/client";

const router = useRouter();
const username = ref("");
const password = ref("");
const error = ref("");
const loading = ref(false);

async function onSubmit() {
  error.value = "";
  loading.value = true;
  try {
    await register(username.value, password.value);
    router.push("/login");
  } catch (e) {
    error.value =
      e instanceof ApiError && e.code === "CONFLICT_STATE"
        ? "注册失败，请更换账号"
        : "注册失败，请重试";
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
