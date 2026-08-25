import * as SheetPrimitive from "@radix-ui/react-dialog";
import {cva, type VariantProps} from "class-variance-authority";
import {X} from "lucide-react";
import {cn} from "@/lib/utils";
import type {ComponentPropsWithoutRef, HTMLAttributes} from "react";

const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;
const SheetPortal = SheetPrimitive.Portal;

function SheetOverlay({ className, ...props }: ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>) {
  return <SheetPrimitive.Overlay className={cn("fixed inset-0 z-50 bg-black/20 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0", className)} {...props} />;
}

const sheetVariants = cva(
  "fixed z-50 gap-4 bg-white/90 backdrop-blur-xl p-6 shadow-card transition ease-in-out data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-300 data-[state=open]:duration-300",
  {
    variants: {
      side: {
        top: "inset-x-0 top-0 border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top",
        bottom: "inset-x-0 bottom-0 border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom",
        left: "inset-y-0 left-0 h-full w-72 border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left",
        right: "inset-y-0 right-0 h-full w-72 border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
      },
    },
    defaultVariants: { side: "right" },
  },
);

interface SheetContentProps extends ComponentPropsWithoutRef<typeof SheetPrimitive.Content>, VariantProps<typeof sheetVariants> {}

function SheetContent({ side = "right", className, children, ...props }: SheetContentProps) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Content className={cn(sheetVariants({ side }), className)} {...props}>
        {children}
        <SheetPrimitive.Close className="absolute right-4 top-4 rounded-full opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-indigo-500">
          <X className="h-4 w-4" />
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPortal>
  );
}

function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={cn("flex flex-col space-y-2 text-center sm:text-left", className)} {...props} />; }
function SheetTitle({ className, ...props }: ComponentPropsWithoutRef<typeof SheetPrimitive.Title>) { return <SheetPrimitive.Title className={cn("text-lg font-semibold text-slate-800", className)} {...props} />; }

export { Sheet, SheetPortal, SheetOverlay, SheetTrigger, SheetClose, SheetContent, SheetHeader, SheetTitle };
