import {createContext, useContext} from "react";

// 从 Toast.tsx 拆出：Context 与 hook 属于非组件导出，
// 与组件混在同一文件会让 Vite Fast Refresh 失效
export type ToastLevel = "success" | "info" | "warning" | "error";

export interface ToastCtx { addToast: (msg: string, level?: ToastLevel) => void; }

export const ToastCtx = createContext<ToastCtx>({ addToast: () => {} });

export function useToast() {
  return useContext(ToastCtx).addToast;
}
