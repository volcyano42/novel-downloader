import {Slot} from "@radix-ui/react-slot";
import {cva, type VariantProps} from "class-variance-authority";
import {cn} from "@/lib/utils";
import type {ButtonHTMLAttributes} from "react";

const buttonVariants = cva(
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

export { buttonVariants };
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean; }

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
