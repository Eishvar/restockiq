// Small shared UI kit. Plain Tailwind, no external component library.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

const cx = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(' ')

// ---------- Button ----------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
}
const buttonStyles = {
  primary: 'bg-brand-royal text-white hover:bg-brand-hover',
  secondary: 'bg-white text-slate-800 border border-slate-300 hover:bg-slate-50',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  ghost: 'text-slate-700 hover:bg-slate-100',
}
export function Button({ variant = 'primary', className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50',
        buttonStyles[variant],
        className,
      )}
    />
  )
}

// ---------- Card ----------
export function Card({ title, children, className }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx('rounded-xl border border-slate-200 bg-white p-4 shadow-sm', className)}>
      {title && <h2 className="mb-3 text-base font-semibold">{title}</h2>}
      {children}
    </section>
  )
}

// ---------- Badge ----------
const badgeTones = {
  neutral: 'bg-slate-100 text-slate-700',
  good: 'bg-emerald-100 text-emerald-800',
  warn: 'bg-amber-100 text-amber-800',
  bad: 'bg-red-100 text-red-800',
}
export function Badge({ tone = 'neutral', children }: { tone?: keyof typeof badgeTones; children: ReactNode }) {
  return (
    <span className={cx('inline-block rounded-full px-2 py-0.5 text-xs font-medium', badgeTones[tone])}>
      {children}
    </span>
  )
}

// ---------- Chip (e.g. forecast driver tags) ----------
export function Chip({ children }: { children: ReactNode }) {
  return (
      <span className="inline-block rounded-md border border-brand-sky bg-sky-50 px-2 py-0.5 text-xs text-sky-900">
      {children}
    </span>
  )
}

// ---------- Table ----------
export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            {head.map((h, i) => (
              <th key={i} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 [&_td]:px-3 [&_td]:py-2">{children}</tbody>
      </table>
    </div>
  )
}

// ---------- Modal ----------
export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const previousFocus = useRef<HTMLElement | null>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    if (!open) return
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const first = dialogRef.current?.querySelector<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current()
      if (e.key === 'Tab' && dialogRef.current) {
        const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')]
        if (!focusable.length) return
        const firstItem = focusable[0], lastItem = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === firstItem) { e.preventDefault(); lastItem.focus() }
        else if (!e.shiftKey && document.activeElement === lastItem) { e.preventDefault(); firstItem.focus() }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('keydown', onKey); previousFocus.current?.focus() }
  }, [open])
  if (!open) return null
  return createPortal((
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={() => onCloseRef.current()}>
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 id="modal-title" className="text-lg font-semibold">{title}</h2>
          <button aria-label="Close" className="rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800" onClick={onClose}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  ), document.body)
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-xl bg-slate-200/70 ${className}`} />
}

export function PageSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-label="Loading page" role="status" className="space-y-4">
      <span className="sr-only">Loading page content</span>
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-5 w-80 max-w-full" />
      <div className="grid gap-4 md:grid-cols-2">
        {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-40" />)}
      </div>
    </div>
  )
}

export function ConfirmModal({
  open, title, description, pending, error, onCancel, onConfirm,
}: {
  open: boolean
  title: string
  description: string
  pending?: boolean
  error?: string
  onCancel: () => void
  onConfirm: () => void
}) {
  return <Modal open={open} title={title} onClose={pending ? () => {} : onCancel}>
    <p className="text-sm text-slate-700">{description}</p>
    {error && <p role="alert" className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
    <div className="mt-5 flex justify-end gap-2">
      <Button variant="secondary" onClick={onCancel} disabled={pending}>Cancel</Button>
      <Button variant="danger" onClick={onConfirm} disabled={pending}>{pending ? 'Working…' : 'Confirm'}</Button>
    </div>
  </Modal>
}

// ---------- Stat ----------
export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

// ---------- EmptyState ----------
export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
      <p className="font-medium">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ---------- SegmentedControl ----------
export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  label?: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-slate-300 bg-white p-0.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cx(
            'rounded-md px-3 py-1.5 text-sm font-medium transition',
            o.value === value ? 'bg-brand-royal text-white' : 'text-slate-700 hover:bg-slate-100',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ---------- Tooltip (hover or keyboard focus) ----------
export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex" tabIndex={0}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-1 w-max max-w-xs -translate-x-1/2 rounded-md bg-slate-800 px-2 py-1 text-xs text-white opacity-0 shadow transition group-hover:opacity-100 group-focus:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}

// ---------- Toast ----------
type ToastItem = { id: number; message: string; tone: 'info' | 'success' | 'error' }
const ToastContext = createContext<(message: string, tone?: ToastItem['tone']) => void>(() => {})
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const push = useCallback((message: string, tone: ToastItem['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setItems((prev) => [...prev, { id, message, tone }])
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])
  const tones = { info: 'bg-slate-800', success: 'bg-emerald-700', error: 'bg-red-700' }
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={cx('rounded-lg px-4 py-2 text-sm text-white shadow-lg', tones[t.tone])}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
