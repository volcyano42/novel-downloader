import {test} from "node:test";
import assert from "node:assert/strict";
import {formatIdsAsRanges, formatRanges, parseRanges, parseRangesToIds} from "./chapterRange.ts";

const VALID = [1, 2, 3, 4, 5, 8, 10, 11, 12];

test("单值", () => assert.deepEqual(parseRanges("5", VALID), [5]));
test("闭区间", () => assert.deepEqual(parseRanges("2-4", VALID), [2, 3, 4]));
test("混合分隔符", () => assert.deepEqual(parseRanges("1 3,4", VALID), [1, 3, 4]));
test("混合区间与单值", () =>
  assert.deepEqual(parseRanges("1-5 8 10-12", VALID), [1, 2, 3, 4, 5, 8, 10, 11, 12]));
test("上界越界：只取有效的那些", () =>
  assert.deepEqual(parseRanges("3-999", VALID), [3, 4, 5, 8, 10, 11, 12]));
test("全越界被忽略", () => assert.deepEqual(parseRanges("900-999", VALID), []));
test("倒置区间被忽略", () => assert.deepEqual(parseRanges("20-5", VALID), []));
test("非法字符被忽略", () => assert.deepEqual(parseRanges("abc 3 x-4", VALID), [3]));
test("空串得到空集合", () => assert.deepEqual(parseRanges("", VALID), []));
test("重复值去重", () => assert.deepEqual(parseRanges("3 3 3-4", VALID), [3, 4]));
test("区间内无有效项得到空", () => assert.deepEqual(parseRanges("100-200", VALID), []));

test("格式化折叠连续段", () =>
  assert.equal(formatRanges([1, 2, 3, 4, 5, 8, 10, 11, 12]), "1-5, 8, 10-12"));
test("格式化单章不折叠", () => assert.equal(formatRanges([7]), "7"));
test("格式化空集合", () => assert.equal(formatRanges([]), ""));
test("解析与格式化往返", () => {
  const orders = [1, 2, 3, 8, 10, 11, 12];
  assert.deepEqual(parseRanges(formatRanges(orders), VALID), orders);
});

// ── 输入框 ↔ 勾选集合的联动（组件装配用的纯函数）────────────
const CHAPTERS = [
  {id: "a", order: 1, downloaded: true},
  {id: "b", order: 2, downloaded: true},
  {id: "c", order: 3, downloaded: false}, // 未下载：不可被输入框选中
  {id: "d", order: 4, downloaded: true},
];

test("文本 → id 集合：跳过未下载章节", () =>
  assert.deepEqual(parseRangesToIds("1-4", CHAPTERS), ["a", "b", "d"]));
test("文本 → id 集合：越界与非法忽略", () =>
  assert.deepEqual(parseRangesToIds("2, 99, abc", CHAPTERS), ["b"]));
test("文本 → id 集合：空串得空集合", () =>
  assert.deepEqual(parseRangesToIds("", CHAPTERS), []));
test("id 集合 → 文本：按 order 格式化", () =>
  assert.equal(formatIdsAsRanges(["a", "b", "d"], CHAPTERS), "1-2, 4"));
test("id 集合 → 文本：空集合", () => assert.equal(formatIdsAsRanges([], CHAPTERS), ""));
test("往返一致", () => {
  const ids = ["a", "b", "d"];
  assert.deepEqual(parseRangesToIds(formatIdsAsRanges(ids, CHAPTERS), CHAPTERS), ids);
});
