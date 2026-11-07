<template>
  <div class="nf">
    <h1>404</h1>
    <p>页面不存在</p>
    <router-link to="/" class="link">返回首页</router-link>
  </div>
</template>

<style scoped>
.nf {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
h1 {
  font-size: 48px;
  color: var(--color-text-muted);
}
.link {
  color: var(--color-primary);
  margin-top: var(--space-4);
}
</style>
