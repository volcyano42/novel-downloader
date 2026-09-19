import {Slot} from "@radix-ui/react-slot";
import type {VariantProps} from "class-variance-authority";
import {cn} from "@/lib/utils";
import type {ButtonHTMLAttributes} from "react";
import {buttonVariants} from "./button-variants";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean; }

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
