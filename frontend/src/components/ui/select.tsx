import * as SelectPrimitive from "@radix-ui/react-select";
import {Check, ChevronDown, ChevronUp} from "lucide-react";
import {cn} from "@/lib/utils";
import type {ComponentPropsWithoutRef} from "react";

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

function SelectTrigger({ className, children, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex items-center justify-between gap-1.5 rounded-xl border border-white/20 bg-white/80 backdrop-blur-xl px-3 py-2.5 text-sm text-slate-700 outline-none transition-shadow focus:ring-2 focus:ring-indigo-500/30 data-[placeholder]:text-slate-400 [&>span]:line-clamp-1",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" strokeWidth={1.5} />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({ className, children, position = "popper", ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position={position}
        sideOffset={4}
        className={cn(
          "relative z-50 max-h-60 min-w-[8rem] overflow-hidden rounded-xl border border-white/20 bg-white/95 backdrop-blur-xl shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          position === "popper" && "data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.ScrollUpButton className="flex items-center justify-center py-1 text-slate-400">
          <ChevronUp className="h-3.5 w-3.5" strokeWidth={1.5} />
        </SelectPrimitive.ScrollUpButton>
        <SelectPrimitive.Viewport
          className={cn("p-1", position === "popper" && "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]")}
        >
          {children}
        </SelectPrimitive.Viewport>
        <SelectPrimitive.ScrollDownButton className="flex items-center justify-center py-1 text-slate-400">
          <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} />
        </SelectPrimitive.ScrollDownButton>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

function SelectItem({ className, children, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-lg py-1.5 pl-8 pr-2 text-sm text-slate-600 outline-none transition-colors focus:bg-indigo-50 focus:text-indigo-600 data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className,
      )}
      {...props}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="h-3.5 w-3.5 text-indigo-500" strokeWidth={2} />
        </SelectPrimitive.ItemIndicator>
      </span>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}

function SelectSeparator({ className, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>) {
  return <SelectPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-slate-100", className)} {...props} />;
}

export { Select, SelectGroup, SelectValue, SelectTrigger, SelectContent, SelectItem, SelectSeparator };
