<template>
  <main class="page">
    <div class="header">
      <h2>日程</h2>
      <div class="nav">
        <button class="nav-btn" @click="prevWeek">← 上一周</button>
        <span class="week-label">{{ weekLabel }}</span>
        <button class="nav-btn" @click="nextWeek">下一周 →</button>
        <button class="add-btn" @click="goAdd">+ 添加待办</button>
      </div>
    </div>

    <div class="layout">
      <!-- 周日历 -->
      <section class="calendar">
        <div class="weekday-row">
          <div v-for="d in weekdays" :key="d" class="weekday">{{ d }}</div>
        </div>
        <div class="days-row">
          <div
            v-for="(day, i) in weekDays"
            :key="i"
            class="day-cell"
            :class="{ today: isToday(day), selected: isSelected(day) }"
            @click="selectDay(day)"
          >
            <div class="date-num">{{ day.getDate() }}</div>
            <div class="day-todos">
              <div
                v-for="t in getTodosForDay(day)"
                :key="t.id"
                class="day-todo"
                :class="{ done: t.status === 'done' }"
                @click.stop="selectTodo(t)"
              >
                <span class="todo-time" v-if="t.due_at">{{ formatTime(t.due_at) }}</span>
                <span class="todo-title">{{ t.title }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 待办列表 -->
      <section class="todo-list">
        <h3>全部待办</h3>
        <div v-if="todos.length === 0" class="empty">暂无待办</div>
        <div
          v-for="t in todos"
          :key="t.id"
          class="todo-item"
          :class="{ done: t.status === 'done', active: selectedTodoId === t.id }"
          @click="selectTodo(t)"
        >
          <input
            type="checkbox"
            :checked="t.status === 'done'"
            @click.stop="toggleTodo(t)"
          />
          <div class="todo-main">
            <div class="todo-title">{{ t.title }}</div>
            <div class="todo-meta">
              <span v-if="t.due_at">{{ formatDateTime(t.due_at) }}</span>
              <span v-if="t.location" class="location">📍 {{ t.location }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 待办详情弹窗 -->
    <div v-if="selectedTodo" class="modal-overlay" @click.self="selectedTodo = null">
      <div class="modal">
        <h3>{{ selectedTodo.title }}</h3>
        <div class="detail-row">
          <span class="label">时间：</span>
          <span>{{ selectedTodo.due_at ? formatDateTime(selectedTodo.due_at) : "未设置" }}</span>
        </div>
        <div class="detail-row">
          <span class="label">地点：</span>
          <span>{{ selectedTodo.location || "未设置" }}</span>
        </div>
        <div class="detail-row">
          <span class="label">状态：</span>
          <span>{{ selectedTodo.status === "done" ? "已完成" : "待办" }}</span>
        </div>
        <div v-if="selectedTodo.description" class="detail-row">
          <span class="label">注意事项：</span>
          <span>{{ selectedTodo.description }}</span>
        </div>
        <div class="modal-actions">
          <button class="action-btn" @click="toggleTodo(selectedTodo)">
            {{ selectedTodo.status === "done" ? "恢复" : "标记完成" }}
          </button>
          <button class="close-btn" @click="selectedTodo = null">关闭</button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { listTodos, completeTodo, restoreTodo, Todo } from "../api/todos";

const router = useRouter();
const todos = ref<Todo[]>([]);
const selectedTodo = ref<Todo | null>(null);
const selectedTodoId = ref<string | null>(null);
const weekOffset = ref(0);

const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const weekDays = computed(() => {
  const now = new Date();
  // Get Monday of current week
  const day = now.getDay() || 7; // Sunday = 0 → 7
  const monday = new Date(now);
  monday.setDate(now.getDate() - (day - 1) + weekOffset.value * 7);
  monday.setHours(0, 0, 0, 0);

  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    days.push(d);
  }
  return days;
});

const weekLabel = computed(() => {
  const start = weekDays.value[0];
  const end = weekDays.value[6];
  return `${start.getFullYear()}年${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`;
});

function prevWeek() {
  weekOffset.value--;
}

function nextWeek() {
  weekOffset.value++;
}

function isToday(day: Date) {
  const now = new Date();
  return (
    day.getFullYear() === now.getFullYear() &&
    day.getMonth() === now.getMonth() &&
    day.getDate() === now.getDate()
  );
}

function isSelected(_day: Date) {
  // No persistent day selection needed for now
  return false;
}

function selectDay(_day: Date) {
  // Could filter todos by day; for now just show in calendar
}

function getTodosForDay(day: Date) {
  return todos.value.filter((t) => {
    if (!t.due_at) return false;
    const d = new Date(t.due_at);
    // Compare using UTC to match backend storage
    return (
      d.getUTCFullYear() === day.getFullYear() &&
      d.getUTCMonth() === day.getMonth() &&
      d.getUTCDate() === day.getDate()
    );
  });
}

function formatTime(iso: string) {
  const d = new Date(iso);
  // Use UTC to match backend storage (no timezone offset)
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

function formatDateTime(iso: string) {
  const d = new Date(iso);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()} ${formatTime(iso)}`;
}

function selectTodo(t: Todo) {
  selectedTodo.value = t;
  selectedTodoId.value = t.id;
}

async function toggleTodo(t: Todo) {
  if (t.status === "done") {
    await restoreTodo(t.id);
    t.status = "pending";
  } else {
    await completeTodo(t.id);
    t.status = "done";
  }
  if (selectedTodo.value?.id === t.id) {
    selectedTodo.value = { ...t };
  }
}

function goAdd() {
  router.push("/todos/add");
}

async function load() {
  const res = await listTodos();
  todos.value = res.data || [];
}

onMounted(load);
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-4); flex-wrap: wrap; gap: var(--space-2); }
h2 { font-size: var(--text-lg); }
.nav { display: flex; gap: var(--space-2); align-items: center; }
.nav-btn { background: none; border: 1px solid var(--color-border); padding: var(--space-2) var(--space-3); border-radius: var(--radius); cursor: pointer; font-size: var(--text-sm); }
.week-label { font-size: var(--text-sm); color: var(--color-text-muted); min-width: 200px; text-align: center; }
.add-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-2) var(--space-4); border-radius: var(--radius); cursor: pointer; font-size: var(--text-sm); }

.layout { display: flex; gap: var(--space-4); flex-direction: column; }
@media (min-width: 1024px) {
  .layout { flex-direction: row; }
}

.calendar { flex: 2; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); overflow: hidden; }
.weekday-row { display: grid; grid-template-columns: repeat(7, 1fr); background: var(--color-primary); }
.weekday { padding: var(--space-2); text-align: center; color: white; font-size: var(--text-sm); font-weight: 600; }
.days-row { display: grid; grid-template-columns: repeat(7, 1fr); min-height: 400px; }
.day-cell { border-right: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); padding: var(--space-2); min-height: 100px; cursor: pointer; transition: background 0.15s; }
.day-cell:hover { background: #f8fafc; }
.day-cell:nth-child(7n) { border-right: none; }
.day-cell.today { background: #eff6ff; }
.day-cell.today .date-num { background: var(--color-primary); color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.date-num { font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-2); }
.day-todos { display: flex; flex-direction: column; gap: 2px; }
.day-todo { background: var(--color-primary); color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.day-todo.done { background: #94a3b8; text-decoration: line-through; }
.todo-time { opacity: 0.8; margin-right: 2px; }
.todo-title { overflow: hidden; text-overflow: ellipsis; }

.todo-list { flex: 1; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); max-height: 600px; overflow-y: auto; }
.todo-list h3 { font-size: var(--text-base); margin-bottom: var(--space-3); }
.empty { color: var(--color-text-muted); text-align: center; padding: var(--space-4); }
.todo-item { display: flex; gap: var(--space-2); align-items: flex-start; padding: var(--space-3); border-bottom: 1px solid var(--color-border); cursor: pointer; }
.todo-item:hover { background: #f8fafc; }
.todo-item.active { background: #eff6ff; }
.todo-item.done .todo-title { text-decoration: line-through; color: var(--color-text-muted); }
.todo-main { flex: 1; }
.todo-title { font-size: var(--text-sm); }
.todo-meta { font-size: var(--text-xs); color: var(--color-text-muted); margin-top: 2px; display: flex; gap: var(--space-2); flex-wrap: wrap; }
.location { color: #d97706; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: white; border-radius: var(--radius); padding: var(--space-6); max-width: 500px; width: 90%; }
.modal h3 { font-size: var(--text-lg); margin-bottom: var(--space-4); }
.detail-row { display: flex; margin-bottom: var(--space-2); font-size: var(--text-sm); }
.detail-row .label { color: var(--color-text-muted); min-width: 80px; }
.modal-actions { display: flex; gap: var(--space-3); margin-top: var(--space-4); }
.action-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-2) var(--space-4); border-radius: var(--radius); cursor: pointer; }
.close-btn { background: none; border: 1px solid var(--color-border); padding: var(--space-2) var(--space-4); border-radius: var(--radius); cursor: pointer; }
</style>
