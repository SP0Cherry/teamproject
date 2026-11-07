import { api, ApiEnvelope } from "./client";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  location: string | null;
  due_at: string | null;
  status: "pending" | "done";
}

export interface TodoCandidate {
  title: string;
  due_at: string | null;
  location: string | null;
  notes: string | null;
}

export async function listTodos(): Promise<ApiEnvelope<Todo[]>> {
  return api.get("/todos");
}

export async function getTodo(id: string): Promise<ApiEnvelope<Todo>> {
  return api.get(`/todos/${id}`);
}

export async function completeTodo(id: string): Promise<ApiEnvelope<{ id: string; status: string }>> {
  return api.post(`/todos/${id}/complete`);
}

export async function restoreTodo(id: string): Promise<ApiEnvelope<{ id: string; status: string }>> {
  return api.post(`/todos/${id}/restore`);
}

export interface LLMConfigPayload {
  api_key: string;
  base_url: string;
  model: string;
}

export interface ParseResult {
  candidates: TodoCandidate[];
  parser: "llm" | "rule";
  extracted_text?: string;
}

export async function parseTodosFromText(
  text: string,
  llmConfig?: LLMConfigPayload
): Promise<ApiEnvelope<ParseResult>> {
  const body: any = { text };
  if (llmConfig) body.llm_config = llmConfig;
  return api.post("/todos/parse-text", body);
}

export async function parseTodosFromFile(
  file: File,
  llmConfig?: LLMConfigPayload
): Promise<ApiEnvelope<ParseResult>> {
  const form = new FormData();
  form.append("file", file);
  if (llmConfig) form.append("llm_config", JSON.stringify(llmConfig));
  return api.post("/todos/parse-file", form);
}

export async function batchCreateTodos(todos: TodoCandidate[]): Promise<ApiEnvelope<Todo[]>> {
  return api.post("/todos/batch-create", { todos });
}
