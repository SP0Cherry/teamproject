import type { TodoCandidate } from "./todos";
import { api, ApiEnvelope } from "./client";

export interface NotificationCandidate extends Partial<TodoCandidate> {
  date_manually_edited?: boolean;
  accept_no_deadline?: boolean;
  title?: string;
  text?: string;
  deadline?: string | null;
  description?: string;
}

export interface Notification {
  id: string;
  source: string;
  status: "pending" | "confirmed" | "discarded";
  raw_text: string;
  candidates: {
    title: string;
    content: string;
    deadline: string | null;
    items: NotificationCandidate[];
  } | null;
}

export async function listNotifications(): Promise<ApiEnvelope<Notification[]>> {
  return api.get("/notifications");
}

export async function getNotification(id: string): Promise<ApiEnvelope<Notification>> {
  return api.get(`/notifications/${id}`);
}

export async function confirmNotification(
  id: string,
  candidates: NotificationCandidate[]
): Promise<ApiEnvelope<{ id: string; title: string; status: string }[]>> {
  return api.post(`/notifications/${id}/confirm`, { candidates });
}

export async function discardNotification(id: string): Promise<ApiEnvelope> {
  return api.post(`/notifications/${id}/discard`);
}

export interface GroupNotificationItem {
  id: string;
  source: string;
  status: "pending" | "confirmed" | "discarded";
  raw_text: string;
  published: boolean;
}

export async function publishGroupNotification(
  groupId: string,
  text: string
): Promise<
  ApiEnvelope<{
    id: string;
    status: string;
    candidates: Notification["candidates"];
    published: boolean;
  }>
> {
  return api.post(`/notifications/groups/${groupId}/publish`, { text });
}

export async function listGroupNotifications(
  groupId: string
): Promise<ApiEnvelope<GroupNotificationItem[]>> {
  return api.get(`/notifications/groups/${groupId}`);
}

export async function withdrawNotification(id: string): Promise<ApiEnvelope> {
  return api.post(`/notifications/${id}/withdraw`);
}
