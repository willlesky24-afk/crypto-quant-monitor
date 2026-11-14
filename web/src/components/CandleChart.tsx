import { CandlestickSeries, ColorType, createChart, type UTCTimestamp } from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Candle } from '../api'
import { formatPrice } from '../lib/format'

// Colors are the DEC-V02 tokens; lightweight-charts needs literal values.
const INK = '#191D23'
const SOFT = '#5E636B'
const LINE = 'rgba(25, 29, 35, 0.04)'
const MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const UP = '#036340'
const DOWN = '#B04A4A'

export function CandleChart({ candles }: { candles: Candle[] }) {
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!box.current) return
    const chart = createChart(box.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#FFFFFF' },
        textColor: SOFT,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 11,
        // Attribution moves to the page footer link, as the library allows.
        attributionLogo: false,
      },
      localization: { priceFormatter: (p: number) => formatPrice(p) },
      grid: { vertLines: { visible: false }, horzLines: { color: LINE } },
      rightPriceScale: { borderColor: LINE, scaleMargins: { top: 0.12, bottom: 0.12 } },
      timeScale: {
        borderColor: LINE,
        timeVisible: true,
        rightOffset: 6,
        tickMarkFormatter: (t: UTCTimestamp) => {
          const d = new Date(t * 1000)
          return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
        },
      },
      crosshair: { vertLine: { color: INK }, horzLine: { color: INK } },
    })
    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      borderVisible: false,
    })
    series.setData(candles.map((c) => ({ ...c, time: c.time as UTCTimestamp })))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [candles])

  return <div ref={box} className="chart" role="img" aria-label="Gráfico de velas" />
}
