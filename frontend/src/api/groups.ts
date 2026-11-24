import { api, ApiEnvelope } from "./client";

export type GroupRole = "owner" | "admin" | "member";

export interface GroupSummary {
  id: string;
  name: string;
  description: string | null;
  my_role: GroupRole;
  my_sync_enabled: boolean;
  member_count: number;
}

export interface GroupDetail {
  id: string;
  name: string;
  description: string | null;
  invite_token: string;
  my_role: GroupRole | null;
  my_sync_enabled: boolean;
}

export interface GroupMember {
  user_id: string;
  username: string;
  role: GroupRole;
  joined_at: string | null;
}

export async function listGroups(): Promise<ApiEnvelope<GroupSummary[]>> {
  return api.get("/groups");
}

export async function getGroup(id: string): Promise<ApiEnvelope<GroupDetail>> {
  return api.get(`/groups/${id}`);
}

export async function createGroup(
  name: string,
  description?: string
): Promise<ApiEnvelope<{ id: string; name: string; invite_token: string }>> {
  return api.post("/groups", { name, description: description || undefined });
}

export async function joinGroup(id: string): Promise<ApiEnvelope<{ group_id: string; role: GroupRole }>> {
  return api.post(`/groups/${id}/join`);
}

export async function joinByToken(
  invite_token: string
): Promise<ApiEnvelope<{ group_id: string; role: GroupRole }>> {
  return api.post("/groups/join-by-token", { invite_token });
}

export async function leaveGroup(id: string): Promise<ApiEnvelope> {
  return api.post(`/groups/${id}/leave`);
}

export async function listMembers(id: string): Promise<ApiEnvelope<GroupMember[]>> {
  return api.get(`/groups/${id}/members`);
}

export async function removeMember(
  groupId: string,
  userId: string
): Promise<ApiEnvelope> {
  return api.delete(`/groups/${groupId}/members/${userId}`);
}

export async function regenerateToken(
  id: string
): Promise<ApiEnvelope<{ invite_token: string }>> {
  return api.post(`/groups/${id}/regenerate-invite-token`);
}

export async function setSync(
  id: string,
  enabled: boolean
): Promise<ApiEnvelope<{ sync_enabled: boolean }>> {
  return api.put(`/groups/${id}/sync`, { enabled });
}
