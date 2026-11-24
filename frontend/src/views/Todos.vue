<template>
  <main class="page">
    <h2>待办</h2>
    <div class="list" v-if="todos.length">
      <div class="todo" v-for="t in todos" :key="t.id" :class="{ done: t.status === 'done' }">
        <input type="checkbox" :checked="t.status === 'done'" @change="toggle(t)" />
        <div class="todo-body">
          <div class="title">{{ t.title }}</div>
          <div class="meta">{{ formatTodoTime(t) }}</div>
        </div>
      </div>
    </div>
    <p class="empty" v-else>暂无待办</p>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { formatTodoTime } from "../utils/time.mjs";
import { listTodos, completeTodo, restoreTodo, Todo } from "../api/todos";

const todos = ref<Todo[]>([]);

async function toggle(t: Todo) {
  if (t.status === "done") {
    await restoreTodo(t.id);
    t.status = "pending";
  } else {
    await completeTodo(t.id);
    t.status = "done";
  }
}

onMounted(async () => {
  const res = await listTodos();
  todos.value = res.data || [];
});
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.list { display: flex; flex-direction: column; gap: var(--space-2); }
.todo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
}
.todo.done .title { text-decoration: line-through; color: var(--color-text-muted); }
.todo-body { flex: 1; }
.title { font-size: var(--text-base); }
.meta { font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px; }
.empty { color: var(--color-text-muted); }
</style>
