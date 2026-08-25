import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import {cn} from "@/lib/utils";
import type {ComponentPropsWithoutRef} from "react";

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
const TooltipTrigger = TooltipPrimitive.Trigger;

function TooltipContent({ className, sideOffset = 4, ...props }: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  return <TooltipPrimitive.Content sideOffset={sideOffset} className={cn("z-50 overflow-hidden rounded-xl border border-white/20 bg-white/90 backdrop-blur-xl px-3 py-1.5 text-sm text-slate-800 shadow-card animate-in fade-in-0 zoom-in-95", className)} {...props} />;
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
