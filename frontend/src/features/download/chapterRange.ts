/**
 * 章节范围文本 ↔ order 集合。
 *
 * 语义：`parseRanges` 的结果是**完整选中集合**（覆盖），不是增量 ——
 * 这样输入框和列表永远表达同一个状态，不会出现「输入框写着 5-20
 * 但实际还勾着第 300 章」的错位。
 *
 * 输入容错：越界、非数字、倒置区间（如 `20-5`）一律静默忽略，不报错。
 */

/** token 分隔符：空白 / 半角逗号 / 全角逗号 / 顿号。 */
const TOKEN_SPLIT = /[\s,，、]+/;

/** 单个 token：`5` 或 `5-20`。 */
const RANGE_RE = /^(\d+)(?:-(\d+))?$/;

/** 单次展开的跨度保护，避免手滑输入 `1-99999999` 把浏览器卡死。 */
const MAX_SPAN = 20000;

/** 把范围文本解析成升序去重的合法 order 列表。 */
export function parseRanges(text: string, validOrders: readonly number[]): number[] {
  const valid = new Set(validOrders);
  const picked = new Set<number>();

  for (const raw of text.split(TOKEN_SPLIT)) {
    const token = raw.trim();
    if (!token) continue;
    const m = RANGE_RE.exec(token);
    if (!m) continue;

    const start = Number(m[1]);
    const end = m[2] === undefined ? start : Number(m[2]);
    if (end < start) continue; // 倒置区间：忽略，不猜用户意图
    if (end - start > MAX_SPAN) continue; // 跨度过大：同样忽略

    for (let n = start; n <= end; n++) {
      if (valid.has(n)) picked.add(n);
    }
  }

  return [...picked].sort((a, b) => a - b);
}

/** 把 order 列表格式化成范围文本，连续段折叠成 `a-b`。 */
export function formatRanges(orders: readonly number[]): string {
  const sorted = [...new Set(orders)].sort((a, b) => a - b);
  if (sorted.length === 0) return "";

  const parts: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];

  for (let i = 1; i <= sorted.length; i++) {
    const cur: number | undefined = i < sorted.length ? sorted[i] : undefined;
    if (cur !== undefined && cur === prev + 1) {
      prev = cur;
      continue;
    }
    parts.push(start === prev ? String(start) : `${start}-${prev}`);
    if (cur !== undefined) {
      start = cur;
      prev = cur;
    }
  }

  return parts.join(", ");
}
