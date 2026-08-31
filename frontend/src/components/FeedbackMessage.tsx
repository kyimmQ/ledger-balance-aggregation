export type FeedbackTone = 'info' | 'error' | 'success'

export interface FeedbackMessageProps {
  tone: FeedbackTone
  message: string
}

function FeedbackMessage({ tone, message }: FeedbackMessageProps) {
  const liveProps = tone === 'error'
    ? { role: 'alert' as const, 'aria-live': 'assertive' as const, 'aria-atomic': true }
    : { role: 'status' as const, 'aria-live': 'polite' as const, 'aria-atomic': true }

  return (
    <div className={`feedback feedback-${tone}`} {...liveProps}>
      <span className="feedback-label">{tone === 'error' ? 'Error' : tone === 'success' ? 'Success' : 'Note'}</span>
      <p>{message}</p>
    </div>
  )
}

export default FeedbackMessage
