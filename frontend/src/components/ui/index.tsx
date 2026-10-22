// Small shared UI kit. Plain Tailwind, no external component library.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react'

const cx = (...parts: (string | false | undefined)[]) => parts.filter(Boolean).join(' ')

// ---------- Button ----------
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
}
const buttonStyles = {
  primary: 'bg-emerald-600 text-white hover:bg-emerald-700',
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
    <span className="inline-block rounded-md border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs text-sky-800">
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
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button aria-label="Close" className="text-slate-500 hover:text-slate-800" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
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
            o.value === value ? 'bg-emerald-600 text-white' : 'text-slate-700 hover:bg-slate-100',
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
