import { api, ApiEnvelope } from "./client";

export type AttachmentStatus = "pending" | "processing" | "succeeded" | "failed";

export interface Attachment {
  id: string;
  filename: string;
  title: string | null;
  mime_type: string;
  file_size: number;
  status: AttachmentStatus;
  group_id: string | null;
  version: number;
}

export interface AttachmentDetail extends Attachment {
  extracted_text: string | null;
  error: string | null;
  task_id: string | null;
}

export async function listAttachments(
  groupId?: string
): Promise<ApiEnvelope<Attachment[]>> {
  const params = groupId ? { group_id: groupId } : undefined;
  return api.get("/attachments", { params });
}

export async function getAttachment(
  id: string
): Promise<ApiEnvelope<AttachmentDetail>> {
  return api.get(`/attachments/${id}`);
}

export async function uploadAttachment(
  file: File,
  groupId?: string
): Promise<ApiEnvelope<{ attachment_id: string; filename: string; size: number; group_id: string | null }>> {
  const form = new FormData();
  form.append("file", file);
  if (groupId) form.append("group_id", groupId);
  return api.post("/attachments", form);
}

export async function deleteAttachment(id: string): Promise<ApiEnvelope> {
  return api.delete(`/attachments/${id}`);
}
