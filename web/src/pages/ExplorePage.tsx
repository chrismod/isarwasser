import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { TrendingUp, Circle, BarChart2, Activity } from 'react-feather'
import * as d3 from 'd3'
import { getDailyRange, getHourlyRange, getRawRange, type ParameterKey, type SeriesPoint } from '../lib/isarQueries'
import { useAsync } from '../lib/useAsync'
import { DataMissing } from '../components/DataMissing'
import { useI18n } from '../lib/i18n'

// German locale for D3 time formatting
const deLocale = d3.timeFormatLocale({
  dateTime: '%A, der %e. %B %Y, %X',
  date: '%d.%m.%Y',
  time: '%H:%M:%S',
  periods: ['AM', 'PM'], // Not used in 24h format
  days: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
  shortDays: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
  months: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
  shortMonths: ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'],
})

type DatePreset = 'today' | 'week' | 'month' | '1y' | '5y' | 'all'
type ChartType = 'line' | 'area' | 'bars' | 'dots'
type Resolution = 'daily' | 'hourly' | 'raw'

function getPresetDates(preset: DatePreset): { start: string; end: string } {
  const end = new Date()
  const start = new Date(end)

  switch (preset) {
    case 'today':
      // Today: start and end are the same
      break
    case 'week':
      start.setDate(end.getDate() - 7)
      break
    case 'month':
      start.setMonth(end.getMonth() - 1)
      break
    case '1y':
      start.setFullYear(end.getFullYear() - 1)
      break
    case '5y':
      start.setFullYear(end.getFullYear() - 5)
      break
    case 'all':
      start.setFullYear(1973)
      break
  }

  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  }
}

// Helper function to parse dates safely
function parseDate(dateStr: string): Date {
  // Handle: "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
  // Replace space with T for ISO format
  const isoStr = dateStr.includes(' ') ? dateStr.replace(' ', 'T') : dateStr
  return new Date(isoStr)
}

export function ExplorePage() {
  const { t, language } = useI18n()
  const [searchParams, setSearchParams] = useSearchParams()
  
  const [parameter, setParameter] = useState<ParameterKey>(() => {
    const p = searchParams.get('p') as ParameterKey
    return p === 'water_temperature_c' ? p : 'water_level_cm'
  })
  const [preset, setPreset] = useState<DatePreset>(() => {
    const hasCustomDates = searchParams.has('start') || searchParams.has('end')
    return hasCustomDates ? 'all' : '1y'
  })
  const [startDate, setStartDate] = useState(() => {
    const fromParam = searchParams.get('start')
    return fromParam || getPresetDates('1y').start
  })
  const [endDate, setEndDate] = useState(() => {
    const fromParam = searchParams.get('end')
    return fromParam || getPresetDates('1y').end
  })
  const [chartType, setChartType] = useState<ChartType>('area')
  const [resolution, setResolution] = useState<Resolution>('daily')

  const svgRef = useRef<SVGSVGElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const brushSvgRef = useRef<SVGSVGElement>(null)

  const state = useAsync(
    () => {
      if (resolution === 'raw') {
        return getRawRange(parameter, startDate, endDate)
      } else if (resolution === 'hourly') {
        return getHourlyRange(parameter, startDate, endDate)
      }
      return getDailyRange(parameter, startDate, endDate)
    },
    [parameter, startDate, endDate, resolution]
  )

  const unit = parameter === 'water_level_cm' ? t.unitCm : t.unitCelsius
  const label = parameter === 'water_level_cm' ? t.waterLevelLabel : t.waterTempLabel

  useEffect(() => {
    setSearchParams({ p: parameter }, { replace: true })
  }, [parameter, setSearchParams])

  const handlePresetChange = (newPreset: DatePreset) => {
    setPreset(newPreset)
    const dates = getPresetDates(newPreset)
    setStartDate(dates.start)
    setEndDate(dates.end)
    
    // Reset resolution to daily if switching to long-range preset and currently on raw
    if (resolution === 'raw' && newPreset !== 'today' && newPreset !== 'week' && newPreset !== 'month') {
      setResolution('daily')
    }
  }

  useEffect(() => {
    if (state.status !== 'success' || !svgRef.current || !tooltipRef.current || !brushSvgRef.current) return

    const data: SeriesPoint[] = state.data
    if (data.length === 0) return

    const svg = d3.select(svgRef.current)
    const brushSvg = d3.select(brushSvgRef.current)
    const tooltip = d3.select(tooltipRef.current)
    svg.selectAll('*').remove()
    brushSvg.selectAll('*').remove()

    const margin = { top: 20, right: 30, bottom: 50, left: 60 }
    const bbox = svgRef.current.getBoundingClientRect()
    const width = bbox.width - margin.left - margin.right
    const mainHeight = 400 - margin.top - margin.bottom
    const brushHeight = 60

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const brushG = brushSvg.append('g').attr('transform', `translate(${margin.left},10)`)

    // Scales
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(data, (d) => parseDate(d.x)) as [Date, Date])
      .range([0, width])

    const xScaleBrush = xScale.copy()

    const yScale = d3
      .scaleLinear()
      .domain([
        d3.min(data, (d) => d.y)! * 0.95,
        d3.max(data, (d) => d.y)! * 1.05,
      ])
      .nice()
      .range([mainHeight, 0])

    const yScaleBrush = d3
      .scaleLinear()
      .domain(yScale.domain())
      .range([brushHeight, 0])

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(yScale.ticks(6))
      .join('line')
      .attr('x1', 0)
      .attr('x2', width)
      .attr('y1', (d) => yScale(d))
      .attr('y2', (d) => yScale(d))
      .attr('stroke', 'var(--line)')
      .attr('stroke-dasharray', '2,2')
      .attr('opacity', 0.5)

    // Axes with locale-specific and dynamic formatting based on time range and resolution
    const [startTime, endTime] = xScale.domain()
    const timeRangeMs = endTime.getTime() - startTime.getTime()
    const daysInRange = timeRangeMs / (1000 * 60 * 60 * 24)
    
    let timeFormat: (date: Date) => string
    
    // For hourly or raw resolution, prioritize showing times
    if (resolution === 'hourly' || resolution === 'raw') {
      if (daysInRange < 1) {
        // Less than 1 day: show only hours
        timeFormat = language === 'de'
          ? deLocale.format('%H:%M') // "14:30"
          : d3.timeFormat('%H:%M')    // "14:30"
      } else if (daysInRange <= 7) {
        // 1-7 days: show day + time
        timeFormat = language === 'de'
          ? deLocale.format('%d. %H:%M') // "24. 14:30"
          : d3.timeFormat('%d %H:%M')     // "24 14:30"
      } else {
        // More than 7 days: show date only
        timeFormat = language === 'de'
          ? deLocale.format('%d. %b') // "24. Dez"
          : d3.timeFormat('%b %d')     // "Dec 24"
      }
    } else {
      // For daily resolution, use date-based formatting
      if (daysInRange < 60) {
        // Less than 2 months: show day and month
        timeFormat = language === 'de'
          ? deLocale.format('%d. %b') // "24. Dez"
          : d3.timeFormat('%b %d')     // "Dec 24"
      } else {
        // More than 2 months: show month and year
        timeFormat = language === 'de'
          ? deLocale.format('%b %Y')   // "Dez 2024"
          : d3.timeFormat('%b %Y')      // "Dec 2024"
      }
    }
    
    const xAxis = d3.axisBottom(xScale).ticks(6).tickFormat(timeFormat as any)
    const yAxis = d3.axisLeft(yScale).ticks(6)

    g.append('g')
      .attr('class', 'x-axis')
      .attr('transform', `translate(0,${mainHeight})`)
      .call(xAxis)
      .attr('color', 'var(--fg2)')
      .selectAll('text')
      .attr('fill', 'var(--fg2)')

    g.append('g')
      .attr('class', 'y-axis')
      .call(yAxis)
      .attr('color', 'var(--fg2)')
      .selectAll('text')
      .attr('fill', 'var(--fg2)')

    // Y-axis label
    g.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('y', 0 - margin.left)
      .attr('x', 0 - mainHeight / 2)
      .attr('dy', '1em')
      .style('text-anchor', 'middle')
      .style('fill', 'var(--fg1)')
      .style('font-size', '13px')
      .text(`${label} (${unit})`)

    // Draw chart based on type
    let mainPath: d3.Selection<SVGPathElement, SeriesPoint[], null, undefined> | null = null
    
    if (chartType === 'line' || chartType === 'area') {
      const line = d3
        .line<SeriesPoint>()
        .x((d) => xScale(parseDate(d.x)))
        .y((d) => yScale(d.y))

      mainPath = g.append('path')
        .datum(data)
        .attr('class', 'main-line')
        .attr('fill', 'none')
        .attr('stroke', 'var(--accent)')
        .attr('stroke-width', 2)
        .attr('d', line)
    }

    if (chartType === 'area') {
      const area = d3
        .area<SeriesPoint>()
        .x((d) => xScale(parseDate(d.x)))
        .y0(mainHeight)
        .y1((d) => yScale(d.y))

      g.append('path')
        .datum(data)
        .attr('class', 'main-area')
        .attr('fill', 'var(--accent)')
        .attr('opacity', 0.15)
        .attr('d', area)
    }

    if (chartType === 'bars') {
      const barWidth = Math.max(1, width / data.length)
      g.selectAll('.bar')
        .data(data)
        .join('rect')
        .attr('class', 'bar')
        .attr('x', (d) => xScale(parseDate(d.x)) - barWidth / 2)
        .attr('y', (d) => yScale(d.y))
        .attr('width', barWidth)
        .attr('height', (d) => mainHeight - yScale(d.y))
        .attr('fill', 'var(--accent)')
        .attr('opacity', 0.7)
    }

    if (chartType === 'dots') {
      g.selectAll('.dot')
        .data(data)
        .join('circle')
        .attr('class', 'dot')
        .attr('cx', (d) => xScale(parseDate(d.x)))
        .attr('cy', (d) => yScale(d.y))
        .attr('r', 2)
        .attr('fill', 'var(--accent)')
    }

    // Tooltip interaction overlay
    const overlay = g
      .append('rect')
      .attr('width', width)
      .attr('height', mainHeight)
      .attr('fill', 'transparent')

    const focus = g
      .append('circle')
      .attr('r', 5)
      .attr('fill', 'var(--accent)')
      .attr('stroke', 'var(--bg0)')
      .attr('stroke-width', 2)
      .style('opacity', 0)

    const focusLine = g
      .append('line')
      .attr('stroke', 'var(--accent)')
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '3,3')
      .style('opacity', 0)

    const bisect = d3.bisector<SeriesPoint, Date>((d) => parseDate(d.x)).left

    overlay
      .on('mousemove', function (event) {
        const [mx] = d3.pointer(event, this)
        const x0 = xScale.invert(mx)
        const i = bisect(data, x0, 1)
        const d0 = data[i - 1]
        const d1 = data[i]
        const d = d1 && x0.getTime() - new Date(d0.x).getTime() > new Date(d1.x).getTime() - x0.getTime() ? d1 : d0

        if (!d) return

        const xPos = xScale(parseDate(d.x))
        const yPos = yScale(d.y)

        focus
          .attr('cx', xPos)
          .attr('cy', yPos)
          .style('opacity', 1)

        focusLine
          .attr('x1', xPos)
          .attr('x2', xPos)
          .attr('y1', 0)
          .attr('y2', mainHeight)
          .style('opacity', 0.5)

        tooltip
          .style('opacity', '1')
          .html(`<strong>${d.x}</strong><br/>${d.y.toFixed(2)} ${unit}`)
          .style('left', `${event.pageX + 10}px`)
          .style('top', `${event.pageY - 28}px`)
      })
      .on('mouseout', () => {
        focus.style('opacity', 0)
        focusLine.style('opacity', 0)
        tooltip.style('opacity', '0')
      })

    // Brush overview
    const brushLine = d3
      .line<SeriesPoint>()
      .x((d) => xScaleBrush(parseDate(d.x)))
      .y((d) => yScaleBrush(d.y))

    brushG.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent2)')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.6)
      .attr('d', brushLine)

    const brushArea = d3
      .area<SeriesPoint>()
      .x((d) => xScaleBrush(parseDate(d.x)))
      .y0(brushHeight)
      .y1((d) => yScaleBrush(d.y))

    brushG.append('path')
      .datum(data)
      .attr('fill', 'var(--accent2)')
      .attr('opacity', 0.2)
      .attr('d', brushArea)

    const brush = d3
      .brushX()
      .extent([
        [0, 0],
        [width, brushHeight],
      ])
      .on('end', (event) => {
        if (!event.selection) {
          xScale.domain(d3.extent(data, (d) => parseDate(d.x)) as [Date, Date])
          yScale.domain([0, d3.max(data, (d) => d.y) || 1])
        } else {
          const [x0, x1] = event.selection.map(xScaleBrush.invert)
          xScale.domain([x0, x1])
          
          // Filter data to visible range and recalculate y-domain
          const visibleData = data.filter((d) => {
            const date = parseDate(d.x)
            return date >= x0 && date <= x1
          })
          const yMax = d3.max(visibleData, (d) => d.y) || 1
          yScale.domain([0, yMax])
        }

        // Recreate axis generators with updated scales and dynamic locale-aware formatting
        const [updatedStartTime, updatedEndTime] = xScale.domain()
        const updatedTimeRangeMs = updatedEndTime.getTime() - updatedStartTime.getTime()
        const updatedDaysInRange = updatedTimeRangeMs / (1000 * 60 * 60 * 24)
        
        let updatedTimeFormat: (date: Date) => string
        
        // For hourly or raw resolution, prioritize showing times
        if (resolution === 'hourly' || resolution === 'raw') {
          if (updatedDaysInRange < 1) {
            // Less than 1 day: show only hours
            updatedTimeFormat = language === 'de'
              ? deLocale.format('%H:%M') // "14:30"
              : d3.timeFormat('%H:%M')    // "14:30"
          } else if (updatedDaysInRange <= 7) {
            // 1-7 days: show day + time
            updatedTimeFormat = language === 'de'
              ? deLocale.format('%d. %H:%M') // "24. 14:30"
              : d3.timeFormat('%d %H:%M')     // "24 14:30"
          } else {
            // More than 7 days: show date only
            updatedTimeFormat = language === 'de'
              ? deLocale.format('%d. %b') // "24. Dez"
              : d3.timeFormat('%b %d')     // "Dec 24"
          }
        } else {
          // For daily resolution, use date-based formatting
          if (updatedDaysInRange < 60) {
            // Less than 2 months: show day and month
            updatedTimeFormat = language === 'de'
              ? deLocale.format('%d. %b') // "24. Dez"
              : d3.timeFormat('%b %d')     // "Dec 24"
          } else {
            // More than 2 months: show month and year
            updatedTimeFormat = language === 'de'
              ? deLocale.format('%b %Y')   // "Dez 2024"
              : d3.timeFormat('%b %Y')      // "Dec 2024"
          }
        }
        
        const updatedXAxis = d3.axisBottom(xScale).ticks(6).tickFormat(updatedTimeFormat as any)
        const updatedYAxis = d3.axisLeft(yScale).ticks(6)

        // Update axes
        g.select<SVGGElement>('.x-axis').call(updatedXAxis as any)
        g.select<SVGGElement>('.y-axis').call(updatedYAxis as any)

        // Update main chart
        if (chartType === 'line' || chartType === 'area') {
          const line = d3
            .line<SeriesPoint>()
            .x((d) => xScale(parseDate(d.x)))
            .y((d) => yScale(d.y))
          g.select<SVGPathElement>('.main-line').attr('d', line)
          
          if (chartType === 'area') {
            const area = d3
              .area<SeriesPoint>()
              .x((d) => xScale(parseDate(d.x)))
              .y0(mainHeight)
              .y1((d) => yScale(d.y))
            g.select<SVGPathElement>('.main-area').attr('d', area)
          }
        }
        
        if (chartType === 'bars') {
          const barWidth = Math.max(1, width / data.length)
          g.selectAll<SVGRectElement, SeriesPoint>('.bar')
            .attr('x', (d) => xScale(parseDate(d.x)) - barWidth / 2)
        }
        
        if (chartType === 'dots') {
          g.selectAll<SVGCircleElement, SeriesPoint>('.dot')
            .attr('cx', (d) => xScale(parseDate(d.x)))
        }
      })

    brushG.append('g').attr('class', 'brush').call(brush)

    // Store axis reference
    g.select('g').filter(function() { return d3.select(this).attr('transform')?.includes(`translate(0,${mainHeight})`) }).attr('class', 'x-axis')

  }, [state, label, unit, chartType, language, resolution])

  return (
    <div className="container section">
      <h2 className="sectionTitle">{t.exploreTitle}</h2>
      <p className="muted">{t.exploreSubtitle}</p>

      <div style={{ marginTop: '20px' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            marginBottom: '16px',
            alignItems: 'center',
          }}
        >
          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreParameter}
            </label>
            <select
              value={parameter}
              onChange={(e) => setParameter(e.target.value as ParameterKey)}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid var(--line)',
                background: 'var(--card)',
                color: 'var(--fg0)',
                fontSize: '14px',
              }}
            >
              <option value="water_level_cm" style={{ background: 'var(--bg1)', color: 'var(--fg0)' }}>
                {t.exploreWaterLevel}
              </option>
              <option value="water_temperature_c" style={{ background: 'var(--bg1)', color: 'var(--fg0)' }}>
                {t.exploreWaterTemp}
              </option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreChartType}
            </label>
            <div style={{ display: 'inline-flex', gap: '4px' }}>
              <button
                onClick={() => setChartType('line')}
                title={t.exploreChartLine}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: chartType === 'line' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: chartType === 'line' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: chartType === 'line' ? 'var(--accent)' : 'var(--fg1)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Activity size={16} />
              </button>
              <button
                onClick={() => setChartType('area')}
                title={t.exploreChartArea}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: chartType === 'area' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: chartType === 'area' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: chartType === 'area' ? 'var(--accent)' : 'var(--fg1)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <TrendingUp size={16} />
              </button>
              <button
                onClick={() => setChartType('bars')}
                title={t.exploreChartBars}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: chartType === 'bars' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: chartType === 'bars' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: chartType === 'bars' ? 'var(--accent)' : 'var(--fg1)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <BarChart2 size={16} />
              </button>
              <button
                onClick={() => setChartType('dots')}
                title={t.exploreChartDots}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: chartType === 'dots' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: chartType === 'dots' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: chartType === 'dots' ? 'var(--accent)' : 'var(--fg1)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Circle size={16} />
              </button>
            </div>
          </div>

          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreResolution}
            </label>
            <div style={{ display: 'inline-flex', gap: '4px' }}>
              <button
                onClick={() => setResolution('daily')}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: resolution === 'daily' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: resolution === 'daily' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: resolution === 'daily' ? 'var(--accent)' : 'var(--fg1)',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                {t.exploreResolutionDaily}
              </button>
              <button
                onClick={() => setResolution('hourly')}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: resolution === 'hourly' ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: resolution === 'hourly' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: resolution === 'hourly' ? 'var(--accent)' : 'var(--fg1)',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                {t.exploreResolutionHourly}
              </button>
              {(preset === 'today' || preset === 'week' || preset === 'month') && (
                <button
                  onClick={() => setResolution('raw')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: resolution === 'raw' ? '1px solid var(--accent)' : '1px solid var(--line)',
                    background: resolution === 'raw' ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                    color: resolution === 'raw' ? 'var(--accent)' : 'var(--fg1)',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  {t.exploreResolutionRaw}
                </button>
              )}
            </div>
          </div>

          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreQuick}
            </label>
            {(['today', 'week', 'month', '1y', '5y', 'all'] as DatePreset[]).map((p) => (
              <button
                key={p}
                onClick={() => handlePresetChange(p)}
                style={{
                  padding: '6px 12px',
                  marginRight: '4px',
                  borderRadius: '6px',
                  border: preset === p ? '1px solid var(--accent)' : '1px solid var(--line)',
                  background: preset === p ? 'rgba(77, 214, 255, 0.1)' : 'var(--card)',
                  color: preset === p ? 'var(--accent)' : 'var(--fg1)',
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                {p === 'today' ? t.exploreToday : 
                 p === 'week' ? t.exploreWeek : 
                 p === 'month' ? t.exploreMonth :
                 p === '1y' ? t.explore1Year : 
                 p === '5y' ? t.explore5Years : 
                 t.exploreAll}
              </button>
            ))}
          </div>

          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreStart}
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value)
                setPreset('all')
              }}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid var(--line)',
                background: 'var(--card)',
                color: 'var(--fg0)',
                fontSize: '13px',
              }}
            />
          </div>

          <div>
            <label style={{ fontSize: '13px', color: 'var(--fg2)', marginRight: '6px' }}>
              {t.exploreEnd}
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value)
                setPreset('all')
              }}
              style={{
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid var(--line)',
                background: 'var(--card)',
                color: 'var(--fg0)',
                fontSize: '13px',
              }}
            />
          </div>
        </div>

        <div style={{ position: 'relative' }}>
          {state.status === 'loading' && (
            <div className="card">
              <div className="muted">{t.exploreLoading}</div>
            </div>
          )}

          {state.status === 'error' && <DataMissing error={state.error} />}

          {state.status === 'success' && state.data.length === 0 && (
            <div className="card">
              <div className="muted">{t.exploreNoData}</div>
            </div>
          )}

          {state.status === 'success' && state.data.length > 0 && (
            <>
              <svg
                ref={svgRef}
                style={{
                  width: '100%',
                  height: '400px',
                  background: 'var(--card)',
                  borderRadius: '12px 12px 0 0',
                  border: '1px solid var(--line)',
                  borderBottom: 'none',
                }}
              />
              <svg
                ref={brushSvgRef}
                style={{
                  width: '100%',
                  height: '80px',
                  background: 'rgba(0,0,0,0.2)',
                  borderRadius: '0 0 12px 12px',
                  border: '1px solid var(--line)',
                  borderTop: 'none',
                }}
              />
              <div
                ref={tooltipRef}
                style={{
                  position: 'absolute',
                  opacity: 0,
                  background: 'rgba(0, 0, 0, 0.9)',
                  color: 'white',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  pointerEvents: 'none',
                  transition: 'opacity 0.2s',
                  border: '1px solid var(--accent)',
                }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
