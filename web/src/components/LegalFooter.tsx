import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../lib/i18n'
import { ImpressumText } from './legal/ImpressumText'
import { DatenschutzText } from './legal/DatenschutzText'

type LegalPanel = 'impressum' | 'datenschutz'

/** Ab dieser Scroll-Distanz blendet die Leiste ein. */
const REVEAL_AFTER_PX = 32

/**
 * Zeigt die Legal-Leiste erst, sobald gescrollt wurde. Passt die Seite nicht
 * auf den Viewport, gibt es nichts zu scrollen — dann ist sie sofort sichtbar,
 * damit Impressum und Datenschutz immer erreichbar bleiben.
 */
function useRevealOnScroll() {
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    const update = () => {
      const scrollable =
        document.documentElement.scrollHeight > window.innerHeight + REVEAL_AFTER_PX
      setRevealed(!scrollable || window.scrollY > REVEAL_AFTER_PX)
    }

    update()
    window.addEventListener('scroll', update, { passive: true })
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update)
      window.removeEventListener('resize', update)
    }
  }, [])

  return revealed
}

export function LegalFooter() {
  const { t } = useI18n()
  const revealed = useRevealOnScroll()
  const [open, setOpen] = useState<LegalPanel | null>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  // Ist die Leiste eingeklappt, gibt es auch kein offenes Panel — abgeleitet
  // statt per Effekt zurückgesetzt, damit kein Kaskaden-Render entsteht.
  const activePanel = revealed ? open : null

  useEffect(() => {
    if (!activePanel) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(null)
    }
    window.addEventListener('keydown', onKeyDown)
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [activePanel])

  const toggle = (panel: LegalPanel) => setOpen((current) => (current === panel ? null : panel))

  return (
    <div className={['legalFooter', revealed ? 'legalFooterRevealed' : ''].filter(Boolean).join(' ')}>
      {activePanel ? (
        <div className="legalPanel" ref={panelRef} role="region" aria-label={t.legalRegion}>
          {activePanel === 'impressum' ? <ImpressumText /> : <DatenschutzText />}
          <button className="legalClose" type="button" onClick={() => setOpen(null)}>
            {t.legalClose}
          </button>
        </div>
      ) : null}

      <nav className="legalLinks" aria-label={t.legalRegion}>
        <button
          className={['legalLink', activePanel === 'impressum' ? 'legalLinkActive' : ''].filter(Boolean).join(' ')}
          type="button"
          aria-expanded={activePanel === 'impressum'}
          onClick={() => toggle('impressum')}
        >
          {t.legalImprint}
        </button>
        <span className="legalSep" aria-hidden="true">
          ·
        </span>
        <button
          className={['legalLink', activePanel === 'datenschutz' ? 'legalLinkActive' : ''].filter(Boolean).join(' ')}
          type="button"
          aria-expanded={activePanel === 'datenschutz'}
          onClick={() => toggle('datenschutz')}
        >
          {t.legalPrivacy}
        </button>
      </nav>
    </div>
  )
}
