import { useEffect, useState } from 'react'

export type FeedbackTone = 'info' | 'error' | 'success'

const FLASH_DURATION_MS = 3000

export interface FeedbackMessageProps {
  tone: FeedbackTone
  message: string
  announce?: boolean
}

function FeedbackMessage({ tone, message, announce = true }: FeedbackMessageProps) {
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDismissed(true)
    }, FLASH_DURATION_MS)
    return () => window.clearTimeout(timeout)
  }, [])

  if (dismissed) {
    return null
  }

  const liveProps = tone === 'error'
    ? { role: 'alert' as const, 'aria-live': 'assertive' as const, 'aria-atomic': true }
    : { role: 'status' as const, 'aria-live': 'polite' as const, 'aria-atomic': true }

  return (
    <div className={`feedback feedback-${tone}`} {...(announce ? liveProps : {})}>
      <span className="feedback-label">{tone === 'error' ? 'Error' : tone === 'success' ? 'Success' : 'Note'}</span>
      <p>{message}</p>
      <span className="feedback-timer" aria-hidden="true" />
    </div>
  )
}

export default FeedbackMessage
