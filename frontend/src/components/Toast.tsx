import {type ReactNode, useCallback, useEffect, useRef, useState} from "react";
import {AlertTriangle, CheckCircle, Info as InfoIcon, X, XCircle} from "lucide-react";
import {ToastCtx, type ToastLevel} from "./toast-context";

interface Toast { id: number; message: string; level: ToastLevel; createdAt: number; }

const DURATION = 4000;
const MAX_VISIBLE = 4;

const levelStyles: Record<ToastLevel, { bg: string; border: string; text: string; icon: typeof CheckCircle }> = {
  success: { bg: "bg-green-50", border: "border-green-200", text: "text-green-700", icon: CheckCircle },
  info:    { bg: "bg-blue-50",  border: "border-blue-200",  text: "text-blue-700",  icon: InfoIcon },
  warning: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-700", icon: AlertTriangle },
  error:   { bg: "bg-red-50",   border: "border-red-200",   text: "text-red-700",   icon: XCircle },
};

function ToastItem({ t, onDone }: { t: Toast; onDone: (id: number) => void }) {
  const style = levelStyles[t.level];
  const Icon = style.icon;
  const start = t.createdAt;

  const [progress, setProgress] = useState(100);

  useEffect(() => {
    let frame: number;
    function tick() {
      const remaining = Math.max(0, 100 - ((Date.now() - start) / DURATION) * 100);
      setProgress(remaining);
      if (remaining > 0) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [start]);

  return (
    <div
      className={`flex items-start gap-2.5 rounded-xl border ${style.border} ${style.bg} px-4 py-3 text-sm ${style.text} shadow-lg
        animate-in slide-in-from-right fade-in duration-300 max-w-sm overflow-hidden relative`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">{t.message}</span>
      <button onClick={() => onDone(t.id)}
        className="shrink-0 opacity-50 hover:opacity-100 transition-opacity">
        <X className="h-4 w-4" />
      </button>
      {/* progress bar at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/5">
        <div className="h-full transition-none rounded-full bg-current opacity-30"
          style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextIdRef = useRef(0);

  const addToast = useCallback((message: string, level: ToastLevel = "error") => {
    const id = ++nextIdRef.current;
    setToasts(prev => [...prev.slice(-(MAX_VISIBLE - 1)), { id, message, level, createdAt: Date.now() }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), DURATION);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastCtx.Provider value={{ addToast }}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
        {toasts.map(t => <ToastItem key={t.id} t={t} onDone={removeToast} />)}
      </div>
    </ToastCtx.Provider>
  );
}
