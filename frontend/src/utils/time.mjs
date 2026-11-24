export const DEFAULT_ZONE = 'Asia/Shanghai';

export function splitInstant(iso, zone = DEFAULT_ZONE) {
  if (!iso) return { date: '', time: '' };
  const instant = new Date(iso);
  if (!Number.isFinite(instant.getTime())) throw new Error('时间格式无效，请修正后重试');
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(instant).map(p => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

export function editableTime(candidate) {
  const fallback = splitInstant(candidate.due_at || candidate.deadline, candidate.due_timezone || DEFAULT_ZONE);
  return { ...candidate, date: candidate.date ?? candidate.due_date ?? fallback.date,
    time: candidate.time ?? fallback.time, due_timezone: candidate.due_timezone || DEFAULT_ZONE,
    date_manually_edited: false, accept_no_deadline: false };
}

export function timePayload(candidate) {
  const day = candidate.date || null, clock = candidate.time || null;
  return { title: candidate.title, date: day, time: clock,
    due_at: null, deadline: null, due_date: day && !clock ? day : null,
    due_precision: day ? clock ? 'datetime' : 'date' : 'unknown',
    due_timezone: candidate.due_timezone || DEFAULT_ZONE, location: candidate.location || null,
    notes: candidate.notes || candidate.description || null, accept_no_deadline: candidate.accept_no_deadline === true };
}

export function dateKey(todo) {
  return todo.due_date || splitInstant(todo.due_at, todo.due_timezone || DEFAULT_ZONE).date;
}

export function formatTodoTime(todo) {
  if (todo.due_date) return `${todo.due_date}（仅日期）`;
  if (!todo.due_at) return '未设置';
  const p = splitInstant(todo.due_at, todo.due_timezone || DEFAULT_ZONE);
  return `${p.date} ${p.time}`;
}

export function rebaseCandidate(candidate) {
  if (candidate.date_manually_edited || !candidate.date_basis?.date || !candidate.date_expression) return;
  const text = candidate.date_expression;
  const base = new Date(`${candidate.date_basis.date}T12:00:00Z`);
  if (!Number.isFinite(base.getTime())) throw new Error('日期基准无效');
  let offset;
  const m = text.match(/(下|本|这)?(?:周|星期|礼拜)([一二三四五六日天])/);
  if (m) offset = '一二三四五六日'.indexOf(m[2].replace('天','日')) - ((base.getUTCDay()+6)%7) + (m[1] === '下' ? 7 : 0);
  else if (/后天|the day after tomorrow/i.test(text)) offset = 2;
  else if (/明天|明日|tomorrow/i.test(text)) offset = 1;
  else if (/今天|今日|today/i.test(text)) offset = 0;
  else {
    const en = text.match(/\b(this|next)\s+(mon|tue|wed|thu|fri|sat|sun)\w*/i);
    if (en) offset = ['mon','tue','wed','thu','fri','sat','sun'].indexOf(en[2].toLowerCase()) - ((base.getUTCDay()+6)%7) + (en[1].toLowerCase() === 'next' ? 7 : 0);
  }
  if (offset !== undefined) { base.setUTCDate(base.getUTCDate()+offset); candidate.date = base.toISOString().slice(0,10); }
}

export function rebaseCandidates(candidates, index) {
  const basis = candidates[index].date_basis;
  if (!basis) return;
  for (const candidate of candidates) {
    if (candidate.date_basis?.source === basis.source && candidate.date_basis?.timezone === basis.timezone) {
      candidate.date_basis = { ...candidate.date_basis, date: basis.date };
      rebaseCandidate(candidate);
    }
  }
}
