"use client";

import { useId } from "react";

/** Original abstract optical composition. No bottle, ingredient image or intensity scale. */
export default function ScentComposition({ phase = 0 }: { phase?: number }) {
  const id = useId().replace(/:/g, "");
  return <svg className="wow-composition" viewBox="0 0 560 500" aria-hidden="true" style={{ transform: `rotate(${phase * 6}deg)` }}>
    <defs>
      <linearGradient id={`${id}-ribbon`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#c79060" /><stop offset=".32" stopColor="#edcf9f" /><stop offset=".6" stopColor="#b4a7be" /><stop offset="1" stopColor="#61796e" /></linearGradient>
      <radialGradient id={`${id}-glass`} cx="28%" cy="16%" r="90%"><stop stopColor="#fffef8" stopOpacity=".95" /><stop offset=".36" stopColor="#e9dbca" stopOpacity=".7" /><stop offset=".7" stopColor="#a49baf" stopOpacity=".35" /><stop offset="1" stopColor="#4b625b" stopOpacity=".8" /></radialGradient>
      <linearGradient id={`${id}-edge`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fffcf0" /><stop offset=".4" stopColor="#b7aba2" /><stop offset=".7" stopColor="#f6e8c9" /><stop offset="1" stopColor="#4a5e58" /></linearGradient>
    </defs>
    <g className="wow-composition-grid" stroke="currentColor" strokeWidth=".6" fill="none" opacity=".16"><path d="M40 250H520M280 30V470" /><circle cx="280" cy="250" r="205" strokeDasharray="2 8" /><path d="M68 50V70M58 60H78M482 430H502M492 420V440" /></g>
    <ellipse cx="290" cy="437" rx="135" ry="13" fill="#394b40" opacity=".07" />
    <g className="wow-ribbon-back" fill="none" stroke={`url(#${id}-ribbon)`}>
      {Array.from({ length: 19 }, (_, i) => <path key={i} d={`M${95+i*3} 394 C${10+i*5} ${205-i*4}, ${465-i*3} ${-50+i*8}, ${454-i*2} 171 S${85+i*6} ${299+i*3}, ${428-i*4} 413`} strokeWidth={1.2+i*.045} opacity={.45+i*.02} />)}
    </g>
    <path d="M161 342C111 276 138 134 237 101C327 71 433 144 427 254C421 357 305 416 214 386C191 378 173 364 161 342Z" fill={`url(#${id}-glass)`} stroke={`url(#${id}-edge)`} strokeWidth="2" />
    <path d="M157 267C161 180 209 119 280 120C354 121 401 179 405 255" fill="none" stroke="#fff9e7" strokeOpacity=".7" strokeWidth="1.5" />
    <g className="wow-ribbon-front" fill="none" stroke={`url(#${id}-ribbon)`}>
      {Array.from({ length: 15 }, (_, i) => <path key={i} d={`M${91+i*2} ${325+i*3} C${185+i*4} ${445-i*2}, ${448-i*2} ${254-i*5}, ${417-i*2} ${131+i*2}`} strokeWidth={1+i*.065} />)}
    </g>
    <path d="M165 339C200 378 271 389 327 360" fill="none" stroke="#fff8e8" strokeOpacity=".7" />
  </svg>;
}
