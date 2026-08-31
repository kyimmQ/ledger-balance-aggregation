export type FeedbackTone = 'info' | 'error' | 'success'

export interface FeedbackMessageProps {
  tone: FeedbackTone
  message: string
  announce?: boolean
}

function FeedbackMessage({ tone, message, announce = true }: FeedbackMessageProps) {
  const liveProps = tone === 'error'
    ? { role: 'alert' as const, 'aria-live': 'assertive' as const, 'aria-atomic': true }
    : { role: 'status' as const, 'aria-live': 'polite' as const, 'aria-atomic': true }

  return (
    <div className={`feedback feedback-${tone}`} {...(announce ? liveProps : {})}>
      <span className="feedback-label">{tone === 'error' ? 'Error' : tone === 'success' ? 'Success' : 'Note'}</span>
      <p>{message}</p>
    </div>
  )
}

export default FeedbackMessage
