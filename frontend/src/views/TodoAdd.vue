<template>
  <main class="page">
    <h2>添加待办</h2>
    <p class="hint">输入文本或上传文件，由 AI 自动解析为待办事项，确认后入库。</p>
    <p class="llm-status" :class="{ configured: isConfigured() }">
      {{ isConfigured() ? "● 已配置 LLM，使用模型解析" : "○ 未配置 LLM，使用规则解析（点击左上角「API 设置」可配置）" }}
    </p>

    <div class="input-section">
      <textarea
        v-model="textInput"
        placeholder="例如：下周三下午3点在会议室A开项目评审会，记得带PPT"
        class="text-input"
        rows="4"
      ></textarea>
      <div class="actions">
        <button class="primary-btn" @click="parseText" :disabled="!textInput.trim() || loading">
          {{ loading ? "解析中..." : "解析文本" }}
        </button>
        <span class="divider">或</span>
        <label class="file-label">
          <input type="file" @change="onFileChange" accept=".txt,.pdf,.docx,.png,.jpg,.jpeg" hidden />
          <span class="file-btn">上传文件</span>
        </label>
      </div>
    </div>

    <div v-if="candidates.length" class="candidates-section">
      <h3>解析结果（可编辑，确认后入库）
        <span class="parser-tag" :class="parserUsed">
          {{ parserUsed === "llm" ? "LLM 解析" : "规则解析" }}
        </span>
      </h3>
      <div class="candidate" v-for="(c, i) in candidates" :key="i">
        <div class="field">
          <label>事件 *</label>
          <input v-model="c.title" class="input" />
        </div>
        <p v-if="c.source_text">原文：{{ c.source_text }}</p>
        <div v-if="c.date_basis && c.date_expression">
          <label>{{ c.date_basis.source === 'source_text' ? '原文日期基准' : '按解析请求发送当天推算，待确认' }}（{{ c.date_basis.timezone }}）</label>
          <input type="date" v-model="c.date_basis.date" @change="updateBasis(i)" />
        </div>
        <p v-if="c.warnings?.length">{{ c.warnings.join('；') }}</p>
        <label v-if="c.time && !c.date"><input type="checkbox" v-model="c.accept_no_deadline" />接受无截止日期，保留原文时间</label>
        <div class="field-row">
          <div class="field">
            <label>日期</label>
            <input
              v-model="c.date"
              type="date"
              class="input"
              @change="updateDueAt(i)"
            />
          </div>
          <div class="field">
            <label>时间</label>
            <input
              v-model="c.time"
              type="time"
              class="input"
            />
          </div>
        </div>
        <div class="field">
          <label>地点</label>
          <input v-model="c.location" class="input" placeholder="可选" />
        </div>
        <div class="field">
          <label>注意事项</label>
          <textarea v-model="c.notes" class="input" rows="2" placeholder="可选"></textarea>
        </div>
        <button class="remove-btn" @click="removeCandidate(i)">删除此项</button>
      </div>
      <div class="confirm-actions">
        <button class="add-btn" @click="addBlankCandidate">+ 添加待办</button>
        <button class="confirm-btn" @click="confirm" :disabled="saving">
          {{ saving ? "保存中..." : "确认并入库" }}
        </button>
      </div>
    </div>

    <p class="success" v-if="savedCount > 0">已成功保存 {{ savedCount }} 条待办！</p>
    <p class="error" v-if="error">{{ error }}</p>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { editableTime, timePayload, rebaseCandidates } from "../utils/time.mjs";
import { useRouter } from "vue-router";
import { parseTodosFromText, parseTodosFromFile, batchCreateTodos, TodoCandidate } from "../api/todos";
import { ApiError } from "../api/client";
import { useLLMConfig } from "../composables/useLLMConfig";

const router = useRouter();
const { config, isConfigured } = useLLMConfig();
const textInput = ref("");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const savedCount = ref(0);

interface EditableCandidate extends TodoCandidate {
  date?: string;
  time?: string;
  date_manually_edited?: boolean;
  accept_no_deadline?: boolean;
}

const candidates = ref<EditableCandidate[]>([]);
const parserUsed = ref<"llm" | "rule" | null>(null);

function updateDueAt(i: number) {
  candidates.value[i].date_manually_edited = true;
}

function updateBasis(i: number) {
  rebaseCandidates(candidates.value, i);
}

async function parseText() {
  loading.value = true;
  error.value = "";
  try {
    const llmConfig = isConfigured()
      ? {
          api_key: config.value.api_key,
          base_url: config.value.base_url,
          model: config.value.model,
        }
      : undefined;
    const res = await parseTodosFromText(textInput.value, llmConfig);
    parserUsed.value = res.data?.parser || null;
    error.value = res.data?.degraded_reason || "";
    candidates.value = (res.data?.candidates || []).map((c) => {
      return editableTime(c);
    });
    if (candidates.value.length === 0) {
      error.value = "未能解析出待办事项，请尝试更明确的描述";
    }
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "解析失败";
  } finally {
    loading.value = false;
  }
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  loading.value = true;
  error.value = "";
  try {
    const llmConfig = isConfigured()
      ? {
          api_key: config.value.api_key,
          base_url: config.value.base_url,
          model: config.value.model,
        }
      : undefined;
    const res = await parseTodosFromFile(file, llmConfig);
    parserUsed.value = res.data?.parser || null;
    error.value = res.data?.degraded_reason || "";
    candidates.value = (res.data?.candidates || []).map((c) => {
      return editableTime(c);
    });
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "文件解析失败";
  } finally {
    loading.value = false;
    input.value = "";
  }
}

function addBlankCandidate() {
  candidates.value.push({ title: "", due_at: null, location: null, notes: null, date: "", time: "" });
}

function removeCandidate(i: number) {
  candidates.value.splice(i, 1);
}

async function confirm() {
  const valid = candidates.value.filter((c) => c.title && c.title.trim());
  if (valid.length === 0) {
    error.value = "至少需要一个有效的待办标题";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const payload = valid.map(timePayload);
    const res = await batchCreateTodos(payload);
    savedCount.value = res.data?.length || 0;
    setTimeout(() => router.push("/schedule"), 1000);
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "保存失败";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.page { padding: var(--space-6) var(--space-4); max-width: 800px; margin: 0 auto; }
h2 { font-size: var(--text-lg); margin-bottom: var(--space-2); }
.hint { font-size: var(--text-sm); color: var(--color-text-muted); margin-bottom: var(--space-1); }
.llm-status { font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: var(--space-4); }
.llm-status.configured { color: #059669; }
.parser-tag {
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
  vertical-align: middle;
}
.parser-tag.llm { background: #dbeafe; color: #1d4ed8; }
.parser-tag.rule { background: #fef3c7; color: #b45309; }
.input-section { margin-bottom: var(--space-6); }
.text-input { width: 100%; padding: var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius); font-size: var(--text-base); resize: vertical; box-sizing: border-box; }
.actions { display: flex; gap: var(--space-3); align-items: center; margin-top: var(--space-3); }
.primary-btn { background: var(--color-primary); color: white; border: none; padding: var(--space-3) var(--space-6); border-radius: var(--radius); font-weight: 600; cursor: pointer; }
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.divider { color: var(--color-text-muted); }
.file-label { cursor: pointer; }
.file-btn { background: none; border: 1px solid var(--color-border); padding: var(--space-3) var(--space-6); border-radius: var(--radius); cursor: pointer; }
.candidates-section { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-4); }
.candidates-section h3 { font-size: var(--text-base); margin-bottom: var(--space-3); }
.candidate { background: white; border: 1px solid var(--color-border); border-radius: var(--radius); padding: var(--space-3); margin-bottom: var(--space-3); }
.field { margin-bottom: var(--space-2); }
.field label { display: block; font-size: var(--text-xs); color: var(--color-text-muted); margin-bottom: 4px; }
.field-row { display: flex; gap: var(--space-2); }
.field-row .field { flex: 1; }
.input { width: 100%; padding: var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius); box-sizing: border-box; font-size: var(--text-sm); }
.remove-btn { background: none; border: 1px solid #dc2626; color: #dc2626; padding: var(--space-1) var(--space-3); border-radius: var(--radius); font-size: var(--text-xs); cursor: pointer; margin-top: var(--space-2); }
.confirm-actions { display: flex; gap: var(--space-3); margin-top: var(--space-4); }
.add-btn { background: none; border: 1px dashed var(--color-border); padding: var(--space-2) var(--space-4); border-radius: var(--radius); cursor: pointer; color: var(--color-text-muted); }
.confirm-btn { background: #059669; color: white; border: none; padding: var(--space-2) var(--space-6); border-radius: var(--radius); font-weight: 600; cursor: pointer; }
.confirm-btn:disabled { opacity: 0.5; }
.success { color: #059669; margin-top: var(--space-3); }
.error { color: #dc2626; margin-top: var(--space-3); }
</style>
