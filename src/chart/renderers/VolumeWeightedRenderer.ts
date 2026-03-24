import { Renderer } from '../core/Renderer';
import { Viewport } from '../core/Viewport';
import type { OHLCVBar } from '../types';
import { COLORS, BAR_BODY_RATIO } from '../constants';

const VOLUME_EMA_PERIOD = 200;
const MIN_WIDTH_SCALE = 0.2;
const MAX_WIDTH_SCALE = 2.0;
const MIN_CANDLE_GAP_PX = 1;
const MAX_CANDLE_GAP_PX = 3;

/**
 * Volume-Weighted Candlestick Renderer.
 *
 * Encodes volume through candle body WIDTH relative to a 200-period EMA of volume:
 *   - Volume at EMA → normal width (same as regular candlestick)
 *   - Volume above EMA → proportionally wider
 *   - Volume below EMA → proportionally narrower
 *
 * Width is clamped to [20%, 200%] of the normal body width, then capped to the
 * available bar slot so neighboring candles do not overlap.
 * Colors are solid green/red (bullish/bearish) with no alpha modulation.
 */
export class VolumeWeightedRenderer {
  private _cachedBarsRef: OHLCVBar[] | null = null;
  private _cachedBarsLen: number = 0;
  private _volumeEma: Float64Array = new Float64Array(0);

  private computeVolumeEma(bars: OHLCVBar[]): Float64Array {
    if (bars === this._cachedBarsRef && bars.length === this._cachedBarsLen) {
      return this._volumeEma;
    }

    const len = bars.length;
    const ema = new Float64Array(len);
    const k = 2 / (VOLUME_EMA_PERIOD + 1);
    let sum = 0;

    for (let i = 0; i < len; i++) {
      const vol = bars[i].volume;
      if (i < VOLUME_EMA_PERIOD - 1) {
        // Warmup: use running average so early bars get a valid denominator
        sum += vol;
        ema[i] = sum / (i + 1);
      } else if (i === VOLUME_EMA_PERIOD - 1) {
        sum += vol;
        ema[i] = sum / VOLUME_EMA_PERIOD;
      } else {
        ema[i] = vol * k + ema[i - 1] * (1 - k);
      }
    }

    this._cachedBarsRef = bars;
    this._cachedBarsLen = len;
    this._volumeEma = ema;
    return ema;
  }

  updateViewportLayout(viewport: Viewport, bars: OHLCVBar[]) {
    const start = Math.max(0, Math.floor(viewport.startIndex));
    const end = Math.min(bars.length, Math.ceil(viewport.endIndex));
    const blankBarsOnRight = Math.max(0, viewport.endIndex - bars.length);

    if (start >= end || viewport.chartWidth <= 0) {
      viewport.clearVariableBarLayout();
      return;
    }

    const volumeEma = this.computeVolumeEma(bars);
    const widths = new Float64Array(end - start);
    let visibleWeight = 0;

    for (let i = start; i < end; i++) {
      const emaVol = volumeEma[i] > 0 ? volumeEma[i] : 1;
      const ratio = bars[i].volume / emaVol;
      const weight = Math.max(MIN_WIDTH_SCALE, Math.min(MAX_WIDTH_SCALE, ratio));
      widths[i - start] = weight;
      visibleWeight += weight;
    }

    if (visibleWeight <= 0) {
      viewport.clearVariableBarLayout();
      return;
    }

    const leftTrim = Math.max(0, viewport.startIndex - start);
    const rightTrim = Math.max(0, end - viewport.endIndex);
    visibleWeight -= widths[0] * leftTrim;
    visibleWeight -= widths[widths.length - 1] * rightTrim;

    if (visibleWeight <= 0) {
      viewport.clearVariableBarLayout();
      return;
    }

    const totalWeight = visibleWeight + blankBarsOnRight;
    if (totalWeight <= 0) {
      viewport.clearVariableBarLayout();
      return;
    }

    const scale = viewport.chartWidth / totalWeight;
    const lefts = new Float64Array(widths.length);
    let cursor = viewport.chartLeft - widths[0] * leftTrim * scale;

    for (let i = 0; i < widths.length; i++) {
      const width = widths[i] * scale;
      lefts[i] = cursor;
      widths[i] = width;
      cursor += width;
    }

    viewport.setVariableBarLayout(start, lefts, widths);
  }

  render(renderer: Renderer, viewport: Viewport, bars: OHLCVBar[]) {
    const start = Math.max(0, Math.floor(viewport.startIndex));
    const end = Math.min(bars.length, Math.ceil(viewport.endIndex));
    if (start >= end) return;

    const barW = viewport.barWidth;
    const candleGap = Math.min(MAX_CANDLE_GAP_PX, Math.max(MIN_CANDLE_GAP_PX, barW * 0.12));

    for (let i = start; i < end; i++) {
      const bar = bars[i];
      const cx = viewport.barToPixelX(i);
      const slotWidth = viewport.getBarSlotWidth(i);
      const bullish = bar.close >= bar.open;
      const color = bullish ? COLORS.green : COLORS.red;

      const yHigh = viewport.priceToPixelY(bar.high);
      const yLow = viewport.priceToPixelY(bar.low);
      const yOpen = viewport.priceToPixelY(bar.open);
      const yClose = viewport.priceToPixelY(bar.close);

      const bodyTop = Math.min(yOpen, yClose);
      const bodyH = Math.max(1, Math.abs(yOpen - yClose));

      const bodyWidth = Math.max(1, Math.min(slotWidth * BAR_BODY_RATIO, slotWidth - candleGap));

      // Wick — fixed 1px, always full height/low range
      renderer.line(cx, yHigh, cx, yLow, color, 1);

      // Body — solid fill, width encodes volume relative to 200 EMA
      renderer.rect(cx - bodyWidth / 2, bodyTop, bodyWidth, bodyH, color);
    }
  }
}
