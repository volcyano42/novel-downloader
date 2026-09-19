import {cva} from "class-variance-authority";

// 从 button.tsx 拆出：组件与变体定义分文件，
// 避免 Vite Fast Refresh 因同文件混合导出组件与非组件而整页刷新
export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-indigo-500 text-white hover:bg-indigo-600",
        ghost: "hover:bg-white/20 hover:text-slate-800",
        outline: "border border-white/20 bg-white/80 backdrop-blur-xl hover:bg-slate-50",
      },
      size: { default: "h-9 px-4 py-2", sm: "h-8 px-3 text-xs", icon: "h-9 w-9" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);
