import { useEffect, useState } from 'react'

export type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }

export function useAsync<T>(
  asyncFn: () => Promise<T>,
  deps: React.DependencyList = []
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })

    asyncFn()
      .then((data) => {
        if (!cancelled) setState({ status: 'success', data })
      })
      .catch((err: any) => {
        if (!cancelled) setState({ status: 'error', error: String(err?.message ?? err) })
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}



