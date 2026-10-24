import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAskHelp, useFaq, useHelpStatus, type HelpAnswer } from './api'

type Message = { from: 'you' | 'bot'; text: string; source?: HelpAnswer['source']; error?: boolean }

const GREETING: Message = {
  from: 'bot',
  text: 'Hi! I can explain how to use RestockAI. Pick a common question below, or type your own.',
}

const SOURCE_NOTE: Record<HelpAnswer['source'], string> = {
  faq: 'Ready-made answer',
  cache: 'Answered before',
  ai: 'AI answer. It can be wrong, so check the page it mentions.',
}

/** Floating help button and panel. Common questions are answered from a stored list, so they cost nothing. */
export default function HelpChat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([GREETING])
  const [text, setText] = useState('')
  const faq = useFaq(open)
  const status = useHelpStatus(open)
  const ask = useAskHelp()
  const page = useLocation().pathname
  const end = useRef<HTMLDivElement>(null)
  const aiOn = status.data?.ai_available ?? false

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages, ask.isPending, open])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const push = (...m: Message[]) => setMessages((all) => [...all, ...m])

  function pickFaq(q: string, a: string) {
    push({ from: 'you', text: q }, { from: 'bot', text: a, source: 'faq' }) // no network call at all
  }

  async function send(e: React.FormEvent) {
    e.preventDefault()
    const question = text.trim()
    if (question.length < 3 || ask.isPending) return
    setText('')
    push({ from: 'you', text: question })
    try {
      const r = await ask.mutateAsync({ question, page })
      push({ from: 'bot', text: r.answer, source: r.source })
    } catch (err) {
      push({ from: 'bot', text: err instanceof Error ? err.message : 'Something went wrong. Please try again.', error: true })
    }
  }

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open help"
          className="fixed bottom-4 right-4 z-40 flex min-h-11 items-center gap-2 rounded-full bg-brand-royal px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:bg-brand-hover"
        >
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01" /></svg>
          Help
        </button>
      )}

      {open && (
        <section
          role="dialog"
          aria-label="Help"
          className="fixed inset-x-2 bottom-2 z-40 flex max-h-[80dvh] flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl sm:inset-x-auto sm:bottom-4 sm:right-4 sm:w-[23rem]"
        >
          <header className="flex items-center justify-between rounded-t-2xl bg-brand-royal px-4 py-3 text-white">
            <div>
              <div className="text-sm font-semibold">Help</div>
              <div className="text-xs opacity-80">How do I use RestockAI?</div>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close help" className="rounded-md p-1 text-lg leading-none hover:bg-brand-hover">✕</button>
          </header>

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 text-sm" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={m.from === 'you' ? 'flex justify-end' : 'flex justify-start'}>
                <div
                  className={`max-w-[88%] rounded-2xl px-3 py-2 ${
                    m.from === 'you' ? 'bg-brand-royal text-white' : m.error ? 'bg-red-50 text-red-800' : 'bg-slate-100 text-slate-800'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.source && <p className="mt-1 text-[11px] text-slate-500">{SOURCE_NOTE[m.source]}</p>}
                </div>
              </div>
            ))}
            {ask.isPending && <p className="text-xs text-slate-500">Looking that up…</p>}
            <div ref={end} />
          </div>

          <details open={messages.length === 1} className="border-t border-slate-200 px-3 py-2 text-sm">
            <summary className="cursor-pointer select-none font-medium text-slate-700">
              Common questions {faq.data ? `(${faq.data.length})` : ''}
            </summary>
            <div className="mt-2 max-h-40 space-y-1 overflow-y-auto">
              {faq.isLoading && <p className="text-xs text-slate-500">Loading…</p>}
              {faq.error && <p className="text-xs text-red-700">Could not load the questions.</p>}
              {faq.data?.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => pickFaq(f.question, f.answer)}
                  className="block w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-slate-800 transition hover:border-brand-royal hover:bg-brand-surface"
                >
                  {f.question}
                </button>
              ))}
            </div>
          </details>

          <form onSubmit={send} className="flex gap-2 border-t border-slate-200 p-3">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={300}
              disabled={!aiOn}
              aria-label="Type your question"
              placeholder={aiOn ? 'Type your own question…' : 'Typing is off: pick a common question'}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
            />
            <button
              type="submit"
              disabled={!aiOn || text.trim().length < 3 || ask.isPending}
              className="rounded-lg bg-brand-royal px-3 py-2 text-sm font-semibold text-white transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              Ask
            </button>
          </form>
          <p className="px-3 pb-3 text-[11px] text-slate-500">You can type 3 questions a minute. Common questions have no limit.</p>
        </section>
      )}
    </>
  )
}
