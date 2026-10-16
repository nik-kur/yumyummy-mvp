/**
 * Draws a chart kept as plain data (path / circle / rect / text elements with
 * their SVG attributes), extracted 1:1 from the canvas by `scripts/v3_extract.py`.
 * `scale` fits the artboard's fixed width into the device's.
 */
import Svg, { Circle, Defs, Line, LinearGradient, Path, Rect, Stop, Text as SvgText } from 'react-native-svg';

import { F } from '@/onb/theme';

export interface SvgGradient {
  id: string;
  x1?: string;
  y1?: string;
  x2?: string;
  y2?: string;
  stops: { offset: string; stopColor: string; stopOpacity?: string }[];
}

export interface SvgSpecData {
  w: number;
  h: number;
  els: Record<string, string>[];
  grads?: SvgGradient[];
}

function num(v: string | undefined): number | undefined {
  return v === undefined ? undefined : Number(v);
}

export function SvgSpec({ spec, width }: { spec: SvgSpecData; width?: number }) {
  const w = width ?? spec.w;
  const h = (spec.h * w) / spec.w;
  return (
    <Svg width={w} height={h} viewBox={`0 0 ${spec.w} ${spec.h}`}>
      {spec.grads && spec.grads.length > 0 ? (
        <Defs>
          {spec.grads.map((g) => (
            <LinearGradient key={g.id} id={g.id} x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2}>
              {g.stops.map((st, i) => (
                <Stop key={i} offset={st.offset} stopColor={st.stopColor} stopOpacity={st.stopOpacity ?? '1'} />
              ))}
            </LinearGradient>
          ))}
        </Defs>
      ) : null}
      {spec.els.map((e, i) => {
        const common = {
          stroke: e.stroke,
          strokeWidth: num(e.strokeWidth),
          strokeLinecap: e.strokeLinecap as 'round' | undefined,
          strokeLinejoin: e.strokeLinejoin as 'round' | undefined,
          strokeDasharray: e.strokeDasharray,
          fill: e.fill ?? 'none',
          opacity: num(e.opacity),
        };
        switch (e.t) {
          case 'path':
            return <Path key={i} d={e.d} {...common} />;
          case 'circle':
            return <Circle key={i} cx={num(e.cx)} cy={num(e.cy)} r={num(e.r)} {...common} />;
          case 'rect':
            return (
              <Rect key={i} x={num(e.x)} y={num(e.y)} width={num(e.width)} height={num(e.height)} rx={num(e.rx)} {...common} />
            );
          case 'line':
            return <Line key={i} x1={num(e.x1)} y1={num(e.y1)} x2={num(e.x2)} y2={num(e.y2)} {...common} />;
          case 'text':
            return (
              <SvgText
                key={i}
                x={num(e.x)}
                y={num(e.y)}
                textAnchor={(e.textAnchor as 'middle' | 'start' | 'end') ?? 'start'}
                fontFamily={e.fontWeight === '600' ? F.sansSemibold : F.sans}
                fontSize={num(e.fontSize)}
                fill={e.fill}
              >
                {e.children}
              </SvgText>
            );
          default:
            return null;
        }
      })}
    </Svg>
  );
}
