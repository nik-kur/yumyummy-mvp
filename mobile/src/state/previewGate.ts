/**
 * Preview mode (21): one place that sends the person to Last offer when the
 * backend says an action needs a subscription — a 402 "preview" from any
 * endpoint, or a `paywall` answer to a meal log. The tabs layout registers the
 * handler (it knows the router and whether this is a preview session).
 */
type Handler = (from: string) => void;

let handler: Handler | null = null;

export function setPreviewGateHandler(next: Handler | null): void {
  handler = next;
}

export function openPreviewGate(from: string): void {
  handler?.(from);
}
