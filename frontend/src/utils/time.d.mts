export const DEFAULT_ZONE: string;
export function splitInstant(iso?: string | null, zone?: string): {date: string; time: string};
export function editableTime<T>(candidate: T): T & {date: string; time: string; due_timezone: string; date_manually_edited: boolean; accept_no_deadline: boolean};
export function timePayload(candidate: any): any;
export function dateKey(todo: any): string;
export function formatTodoTime(todo: any): string;
export function rebaseCandidate(candidate: any): void;
export function rebaseCandidates(candidates: any[], index: number): void;
