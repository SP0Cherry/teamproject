import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitInstant, editableTime, timePayload, dateKey, formatTodoTime, rebaseCandidate, rebaseCandidates } from '../src/utils/time.mjs';

test('UTC crosses into the business day without using the browser zone', () => {
  assert.deepEqual(splitInstant('2026-11-10T16:30:00Z'), {date:'2026-11-11',time:'00:30'});
  assert.deepEqual(splitInstant('2026-11-11T07:00:00Z'), {date:'2026-11-11',time:'15:00'});
});
test('changing shared basis updates every dependent candidate while retaining manual dates', () => {
  const basis = {date:'2026-11-08',source:'request_time',timezone:'Asia/Shanghai'};
  const candidates = [
    {date_basis:{...basis,date:'2026-11-09'},date_expression:'本周三'},
    {date_basis:{...basis},date_expression:'下周六'},
    {date_basis:{...basis},date_expression:'本周三',date:'2026-12-01',date_manually_edited:true},
  ];
  rebaseCandidates(candidates,0);
  assert.equal(candidates[0].date,'2026-11-11');
  assert.equal(candidates[1].date,'2026-11-21');
  assert.equal(candidates[2].date,'2026-12-01');
});
test('date only remains date only through editing and submission', () => {
  const c = editableTime({title:'提交', due_date:'2026-11-11', due_at:null});
  assert.equal(c.time, ''); assert.equal(timePayload(c).due_at, null);
  assert.equal(timePayload(c).due_date, '2026-11-11');
  assert.equal(dateKey(c), '2026-11-11'); assert.equal(formatTodoTime(c), '2026-11-11（仅日期）');
});
test('clearing time never supplies 09:00, missing date remains missing', () => {
  assert.equal(timePayload({date:'2026-11-11',time:''}).due_precision,'date');
  const p=timePayload({date:'',time:'15:00'}); assert.equal(p.date,null); assert.equal(p.time,'15:00'); assert.equal(p.due_at,null);
});
test('invalid timestamp is explicit and null remains empty', () => {
  assert.throws(()=>splitInstant('not a date'), /时间格式无效/);
  assert.deepEqual(splitInstant(null),{date:'',time:''});
});
test('changing a basis recomputes relative dates and preserves manual dates', () => {
  const c={date_basis:{date:'2026-11-08'},date_expression:'本周三',date:''};
  rebaseCandidate(c); assert.equal(c.date,'2026-11-04');
  c.date_basis.date='2026-11-09'; rebaseCandidate(c); assert.equal(c.date,'2026-11-11');
  c.date_manually_edited=true; c.date='2026-12-01'; rebaseCandidate(c); assert.equal(c.date,'2026-12-01');
});
