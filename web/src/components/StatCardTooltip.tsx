import { TrendingUp, TrendingDown, Calendar } from 'react-feather'
import type { DayOfYearHistory } from '../lib/isarQueries'

type Props = {
  history: DayOfYearHistory | null
  unit: string
}

export function StatCardTooltip({ history, unit }: Props) {
  if (!history) return null

  return (
    <div className="stat-tooltip">
      {history.recentYears.length > 0 && (
        <div className="stat-tooltip__section">
          <div className="stat-tooltip__heading">
            <Calendar size={12} />
            Gleicher Tag
          </div>
          {history.recentYears.map((yr) => (
            <div className="stat-tooltip__row" key={yr.year}>
              <span className="stat-tooltip__year">{yr.year}</span>
              <span className="stat-tooltip__val">{yr.mean} {unit}</span>
              <span className="stat-tooltip__range">
                {yr.min}–{yr.max}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="stat-tooltip__section stat-tooltip__extremes">
        <div className="stat-tooltip__row">
          <TrendingDown size={13} color="var(--accent2)" />
          <span className="stat-tooltip__extreme-label">All-time Min</span>
          <span className="stat-tooltip__val">{history.allTimeMin.value} {unit}</span>
          <span className="stat-tooltip__year">{history.allTimeMin.year}</span>
        </div>
        <div className="stat-tooltip__row">
          <TrendingUp size={13} color="var(--accent)" />
          <span className="stat-tooltip__extreme-label">All-time Max</span>
          <span className="stat-tooltip__val">{history.allTimeMax.value} {unit}</span>
          <span className="stat-tooltip__year">{history.allTimeMax.year}</span>
        </div>
      </div>
    </div>
  )
}
