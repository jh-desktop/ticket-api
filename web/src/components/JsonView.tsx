/** JSON 을 보기 좋게. 비어 있으면 안내 문구. */
export function JsonView({ value, empty = '(없음)' }: { value: unknown; empty?: string }) {
  if (value === undefined || value === null || value === '') return <div className="muted small">{empty}</div>
  return <pre className="json">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre>
}
