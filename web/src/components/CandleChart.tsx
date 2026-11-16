import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  LineStyle,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import type { Candle } from '../api'
import { formatPrice } from '../lib/format'

// Colors are DEC-V02 tokens (Enmienda 1); lightweight-charts needs literal values.
const INK = '#191D23'
const SOFT = '#5E636B'
const GRID = 'rgba(60, 50, 30, 0.06)'
const UP = '#036340'
const DOWN = '#B04A4A'
const VOLUME = 'rgba(25, 29, 35, 0.12)'
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

function Legend({ c }: { c: Candle | null }) {
  if (!c) return null
  const rise = c.close >= c.open
  return (
    <div className="chart-legend mono" aria-hidden="true">
      <span>A {formatPrice(c.open)}</span>
      <span>M {formatPrice(c.high)}</span>
      <span>m {formatPrice(c.low)}</span>
      <span className="legend-close">
        C {formatPrice(c.close)} <i className={rise ? 'up' : 'down'}>{rise ? '▲' : '▼'}</i>
      </span>
    </div>
  )
}

export function CandleChart({
  candles,
  zoneVal = null,
  zoneVah = null,
}: {
  candles: Candle[]
  zoneVal?: number | null
  zoneVah?: number | null
}) {
  const box = useRef<HTMLDivElement>(null)
  const band = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<Candle | null>(null)
  const last = candles.length ? candles[candles.length - 1] : null
  const hasZone = zoneVal != null && zoneVah != null

  useEffect(() => {
    if (!box.current) return
    const chart = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: SOFT,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        // Attribution moves to the page footer link, as the library allows.
        attributionLogo: false,
      },
      localization: { priceFormatter: (p: number) => formatPrice(p) },
      grid: { vertLines: { visible: false }, horzLines: { color: GRID } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.24 }, minimumWidth: 78, ensureEdgeTickMarksVisible: false },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        rightOffset: 12,
        tickMarkFormatter: (t: UTCTimestamp) => {
          const d = new Date(t * 1000)
          return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
        },
      },
      crosshair: {
        vertLine: { color: 'rgba(25, 29, 35, 0.35)', style: LineStyle.Dotted, labelBackgroundColor: INK },
        horzLine: { visible: false, labelVisible: false },
      },
    })
    const price = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      wickUpColor: 'rgba(3, 99, 64, 0.7)',
      wickDownColor: 'rgba(176, 74, 74, 0.7)',
      borderVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    })
    price.setData(candles.map((c) => ({ ...c, time: c.time as UTCTimestamp })))
    if (candles.length) {
      price.createPriceLine({
        price: candles[candles.length - 1].close,
        color: INK,
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        axisLabelVisible: true,
        axisLabelColor: INK,
        axisLabelTextColor: '#FFFFFF',
        title: '',
      })
    }
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: 'volumen',
      priceFormat: { type: 'volume' },
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('volumen').applyOptions({ scaleMargins: { top: 0.84, bottom: 0.02 }, visible: false })
    volume.setData(
      candles
        .filter((c) => c.volume != null)
        .map((c) => ({ time: c.time as UTCTimestamp, value: c.volume as number, color: VOLUME })),
    )

    // Value zone as a translucent band, repositioned whenever the scale moves.
    const placeBand = () => {
      const el = band.current
      if (!el) return
      const top = zoneVah == null ? null : price.priceToCoordinate(zoneVah)
      const bottom = zoneVal == null ? null : price.priceToCoordinate(zoneVal)
      if (top == null || bottom == null) {
        el.style.display = 'none'
        return
      }
      el.style.display = 'block'
      el.style.top = `${Math.min(top, bottom)}px`
      el.style.height = `${Math.max(1, Math.abs(bottom - top))}px`
      el.style.right = `${chart.priceScale('right').width()}px`
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(placeBand)
    const observer = new ResizeObserver(() =>
      requestAnimationFrame(() => {
        chart.timeScale().fitContent()
        placeBand()
      }),
    )
    observer.observe(box.current)

    chart.subscribeCrosshairMove((param) => {
      const bar = param.seriesData.get(price) as Candle | undefined
      setHover(bar ? { ...bar, time: Number(param.time) } : null)
    })
    chart.timeScale().fitContent()
    requestAnimationFrame(placeBand)
    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [candles, zoneVal, zoneVah])

  return (
    <div className="chart-wrap">
      <Legend c={hover ?? last} />
      <div className="chart-area">
        <div ref={box} className="chart" role="img" aria-label="Gráfico de velas con la zona de valor y el volumen" />
        <div ref={band} className="zone-band" aria-hidden="true" />
      </div>
      {hasZone && <p className="chart-key">Banda bronce: zona de valor, donde se negoció el 70 % del volumen.</p>}
    </div>
  )
}
