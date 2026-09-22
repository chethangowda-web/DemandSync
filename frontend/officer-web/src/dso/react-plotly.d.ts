/**
 * Minimal local typing for react-plotly.js.
 *
 * The published @types package pulls in the full @types/plotly.js surface, which is large and mostly
 * irrelevant here — this project uses one grouped bar chart. Declaring just the props actually used
 * keeps the build honest (no implicit `any` component) without the dependency weight.
 */
declare module 'react-plotly.js' {
  import { Component, CSSProperties } from 'react';

  export interface PlotParams {
    data: Record<string, unknown>[];
    layout?: Record<string, unknown>;
    config?: Record<string, unknown>;
    frames?: Record<string, unknown>[];
    style?: CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: unknown, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: unknown, graphDiv: HTMLElement) => void;
    onPurge?: (figure: unknown, graphDiv: HTMLElement) => void;
    onError?: (err: unknown) => void;
    divId?: string;
  }

  export default class Plot extends Component<PlotParams> {}
}
