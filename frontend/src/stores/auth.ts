import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { login as apiLogin, logout as apiLogout, me, refresh } from "../api/auth";
import { setAccessToken } from "../api/client";

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(null);
  const username = ref<string | null>(null);
  const userId = ref<string | null>(null);

  const isAuthenticated = computed(() => !!token.value);

  async function login(usernameVal: string, password: string) {
    const res = await apiLogin(usernameVal, password);
    if (res.data) {
      token.value = res.data.access_token;
      setAccessToken(token.value);
    }
    await fetchMe();
  }

  async function fetchMe() {
    try {
      const res = await me();
      if (res.data) {
        username.value = res.data.username;
        userId.value = res.data.user_id;
      }
    } catch {
      token.value = null;
      setAccessToken(null);
    }
  }

  async function doLogout() {
    try {
      await apiLogout();
    } catch {
      // ignore
    }
    token.value = null;
    username.value = null;
    userId.value = null;
    setAccessToken(null);
  }

  async function tryRefresh() {
    try {
      const res = await refresh();
      if (res.data) {
        token.value = res.data.access_token;
        setAccessToken(token.value);
        await fetchMe();
      }
      return true;
    } catch {
      return false;
    }
  }

  return { token, username, userId, isAuthenticated, login, fetchMe, doLogout, tryRefresh };
});
