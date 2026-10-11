import * as Dialog from '@radix-ui/react-dialog';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
export const cn=(...values:Parameters<typeof clsx>)=>twMerge(clsx(values));
const variants=cva('btn',{variants:{variant:{default:'acc',outline:'out',ghost:'ghost'},size:{default:'',sm:'sm',lg:'lg'}},defaultVariants:{variant:'default',size:'default'}});
export function Button({className,variant,size,asChild=false,...props}:ButtonHTMLAttributes<HTMLButtonElement>&VariantProps<typeof variants>&{asChild?:boolean}) {const Comp=asChild?Slot:'button';return <Comp className={cn(variants({variant,size}),className)} {...props}/>;}
export function Badge({children,tone=''}:{children:ReactNode;tone?:string}){return <span className={`badge ${tone}`}>{children}</span>;}
export function Modal({open,onClose,title,description,children}:{open:boolean;onClose:()=>void;title:string;description?:string;children:ReactNode}){return <Dialog.Root open={open} onOpenChange={v=>!v&&onClose()}><Dialog.Portal><Dialog.Overlay className="modal-overlay"/><Dialog.Content className="modal-content card"><div className="ch"><Dialog.Title>{title}</Dialog.Title><Dialog.Close asChild><Button variant="ghost" size="sm" aria-label="Close dialog">×</Button></Dialog.Close></div><div className="cb"><Dialog.Description className="mut">{description}</Dialog.Description>{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;}
export function ErrorNotice({error}:{error:unknown}){return error?<p className="error-notice" role="alert">{error instanceof Error?error.message:String(error)}</p>:null;}
export function Icon({name='arrow'}:{name?:string}) {
  const paths:Record<string,ReactNode>={arrow:<path d="M5 12h14m-5-5 5 5-5 5"/>,check:<path d="m5 12 4 4L19 6"/>,hw:<><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/></>,infra:<><rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/><path d="M6 7h1m-1 10h1"/></>,sw:<path d="m8 6-6 6 6 6m8-12 6 6-6 6M14 4l-4 16"/>,comm:<path d="M21 11a9 9 0 0 1-9 9H3l2-5a9 9 0 1 1 16-4Z"/>,mic:<><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0m-7 7v5m-4 0h8"/></>};
  return <svg className="ic" viewBox="0 0 24 24" aria-hidden="true">{paths[name]||paths.arrow}</svg>;
}
