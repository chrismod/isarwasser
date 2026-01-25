import { NavLink, Outlet } from 'react-router-dom'
import { useI18n } from '../lib/i18n'

function navLinkClassName({ isActive }: { isActive: boolean }) {
  return ['navLink', isActive ? 'navLinkActive' : ''].filter(Boolean).join(' ')
}

export function AppLayout() {
  const { language, setLanguage, t } = useI18n()

  return (
    <div className="app">
      <header className="appHeader">
        <div className="container appHeaderInner">
          <div className="brand">
            <div className="brandMark" aria-hidden="true" />
            <div className="brandText">
              <div className="brandName">{t.appName}</div>
              <div className="brandSub">{t.appSubtitle}</div>
            </div>
          </div>

          <nav className="nav" aria-label="Primary">
            <NavLink to="/" end className={navLinkClassName}>
              {t.navStory}
            </NavLink>
            <NavLink to="/explore" className={navLinkClassName}>
              {t.navExplore}
            </NavLink>
            <NavLink to="/records" className={navLinkClassName}>
              {t.navRecords}
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="appMain">
        <Outlet />
      </main>

      <footer className="appFooter">
        <div className="container appFooterInner">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
            <div className="muted">{t.footerSource}</div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <button
                onClick={() => setLanguage('de')}
                style={{
                  padding: '4px 8px',
                  fontSize: '13px',
                  background: language === 'de' ? 'rgba(77, 214, 255, 0.15)' : 'transparent',
                  color: language === 'de' ? 'var(--accent)' : 'var(--fg2)',
                  border: language === 'de' ? '1px solid rgba(77, 214, 255, 0.3)' : '1px solid transparent',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: language === 'de' ? 600 : 400,
                }}
              >
                DE
              </button>
              <button
                onClick={() => setLanguage('en')}
                style={{
                  padding: '4px 8px',
                  fontSize: '13px',
                  background: language === 'en' ? 'rgba(77, 214, 255, 0.15)' : 'transparent',
                  color: language === 'en' ? 'var(--accent)' : 'var(--fg2)',
                  border: language === 'en' ? '1px solid rgba(77, 214, 255, 0.3)' : '1px solid transparent',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: language === 'en' ? 600 : 400,
                }}
              >
                EN
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
