/** 浏览器通知 — 参考 main.py 的 nldlder.utils.notify */

let _permission: NotificationPermission = "default";

function ensurePermission(): Promise<boolean> {
  if (!("Notification" in window)) return Promise.resolve(false);
  if (_permission === "granted") return Promise.resolve(true);
  if (_permission === "denied") return Promise.resolve(false);
  return Notification.requestPermission().then(p => {
    _permission = p;
    return p === "granted";
  });
}

export function notify(title: string, body?: string) {
  ensurePermission().then(granted => {
    if (!granted) return;
    new Notification(title, { body, icon: "/favicon.ico" });
  });
}
