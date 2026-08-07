import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

declare global {
  interface Window {
    _paq?: unknown[][]
  }
}

/**
 * Der Tracker wird in index.html geladen, zählt dort aber bewusst keinen
 * Seitenaufruf: In einer SPA wechselt die URL ohne Reload, ein einmaliges
 * trackPageView beim Boot würde jede Navigation danach verschlucken.
 */
export function useMatomoPageViews() {
  const location = useLocation()

  useEffect(() => {
    const paq = window._paq
    if (!paq) return

    const url = location.pathname + location.search
    paq.push(['setCustomUrl', url])
    paq.push(['setDocumentTitle', document.title])
    paq.push(['trackPageView'])
  }, [location.pathname, location.search])
}
