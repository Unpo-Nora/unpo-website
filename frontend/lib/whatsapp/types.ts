// Tipos centralizados del contrato del inbox multiagente de WhatsApp (Etapa 1H).
// Reflejan los schemas de respuesta del backend (schemas_whatsapp_inbox). No incluyen
// campos sensibles (raw_payload, external_message_id, phone_number_id, waba_id, etc.):
// el backend no los expone y el frontend no los reconstruye.

export interface LineOut {
  id: number;
  label: string;
  display_number: string;
  provider: string;
  is_active: boolean;
  can_view: boolean;
  can_send: boolean;
}

export interface LineRef {
  id: number;
  label: string;
  display_number: string;
}

export interface ContactOut {
  id: number;
  display_name: string | null;
  phone_masked: string | null;
}

export interface AssignedUserOut {
  id: number;
  full_name: string | null;
  role: string | null;
}

export interface ConversationListItem {
  conversation_id: number;
  line: LineRef;
  status: string;
  contact: ContactOut;
  assigned_user: AssignedUserOut | null;
  last_message_at: string | null;
  last_message_direction: string | null;
  last_message_type: string | null;
  last_message_preview: string | null;
  unread_count: number;
}

export interface ConversationListResponse {
  items: ConversationListItem[];
  limit: number;
  offset: number;
  count: number;
  has_more: boolean;
}

export interface ConversationDetail {
  conversation_id: number;
  line: LineRef;
  contact: ContactOut;
  lead_id: number | null;
  assigned_user: AssignedUserOut | null;
  status: string;
  unread_count: number;
  last_message_at: string | null;
  last_inbound_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface MessageOut {
  id: number;
  conversation_id: number;
  direction: string;
  message_type: string;
  text_body: string | null;
  current_status: string;
  provider_timestamp: string | null;
  sender_user_id: number | null;
  created_at: string | null;
}

export interface MessagesResponse {
  items: MessageOut[];
  limit: number;
  count: number;
  has_more: boolean;
  next_cursor: string | null;
  offset: number | null;
  older_cursor: string | null;
  newer_cursor: string | null;
  direction: MessageDirectionParam;
}

export interface LineUnread {
  line_id: number;
  label: string;
  unread_count: number;
}

export interface UnreadCountsResponse {
  total_unread: number;
  lines: LineUnread[];
}

export interface AssignmentHistoryOut {
  id: number;
  from_user_id: number | null;
  to_user_id: number | null;
  assigned_by_user_id: number | null;
  assignment_source: string;
  reason: string | null;
  created_at: string | null;
}

export interface AssignmentHistoryResponse {
  items: AssignmentHistoryOut[];
}

export interface AssignmentResponse {
  conversation_id: number;
  assigned_user_id: number | null;
  changed: boolean;
  assignment: AssignmentHistoryOut | null;
}

export interface AssignableUser {
  id: number;
  full_name: string | null;
  role: string;
}

export type MessageDirectionParam = "forward" | "backward";

export type InboxBucket = "all" | "mine" | "unassigned";

export interface InboxFilterState {
  lineId: number | null;
  bucket: InboxBucket;
  unreadOnly: boolean;
  status: string; // "" = todas
  search: string;
}

export interface ConversationFilters {
  line_id?: number | null;
  assigned_to_me?: boolean;
  unassigned?: boolean;
  unread_only?: boolean;
  status?: string | null;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface GetMessagesParams {
  direction?: MessageDirectionParam;
  cursor?: string | null;
  limit?: number;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
