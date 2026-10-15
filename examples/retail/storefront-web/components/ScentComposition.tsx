"use client";

import { useId } from "react";

/** Original abstract optical composition. No bottle, ingredient image or intensity scale. */
export default function ScentComposition({ phase = 0 }: { phase?: number }) {
  const id = useId().replace(/:/g, "");
  return <svg className="wow-composition" viewBox="0 0 560 500" aria-hidden="true" style={{ transform: `rotate(${phase * 6}deg)` }}>
    <defs>
      <linearGradient id={`${id}-ribbon`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f4dfb8" /><stop offset=".25" stopColor="#c9a570" /><stop offset=".57" stopColor="#e0b7bd" /><stop offset=".82" stopColor="#95b5aa" /><stop offset="1" stopColor="#e2d6af" /></linearGradient>
      <radialGradient id={`${id}-glass`} cx="29%" cy="16%" r="91%"><stop stopColor="#fffcdf" stopOpacity=".99" /><stop offset=".24" stopColor="#e1ccab" stopOpacity=".9" /><stop offset=".55" stopColor="#9ca9aa" stopOpacity=".7" /><stop offset=".81" stopColor="#536a69" stopOpacity=".93" /><stop offset="1" stopColor="#172c2a" stopOpacity=".96" /></radialGradient>
      <linearGradient id={`${id}-edge`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fff9dc" /><stop offset=".39" stopColor="#ddcba5" /><stop offset=".66" stopColor="#f4f6e3" /><stop offset="1" stopColor="#7d9e95" /></linearGradient>
      <radialGradient id={`${id}-aura`} cx="57%" cy="49%" r="58%"><stop stopColor="#e2c088" stopOpacity=".43" /><stop offset=".45" stopColor="#779f8d" stopOpacity=".23" /><stop offset="1" stopColor="#203630" stopOpacity="0" /></radialGradient>
      <linearGradient id={`${id}-prism`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#e9e4d6" stopOpacity=".6" /><stop offset=".45" stopColor="#ded7c7" stopOpacity=".03" /><stop offset="1" stopColor="#85a99e" stopOpacity=".32" /></linearGradient>
    </defs>
    <ellipse cx="290" cy="255" rx="263" ry="223" fill={`url(#${id}-aura)`} />
    <g className="wow-composition-grid" stroke="#d3ccad" strokeWidth=".7" fill="none" opacity=".25"><path d="M40 250H520M280 30V470" /><circle cx="280" cy="250" r="205" strokeDasharray="2 8" /><path d="M68 50V70M58 60H78M482 430H502M492 420V440" /></g>
    <ellipse cx="290" cy="437" rx="135" ry="13" fill="#394b40" opacity=".07" />
    <g className="wow-ribbon-back" fill="none" stroke={`url(#${id}-ribbon)`}>
      {Array.from({ length: 19 }, (_, i) => <path key={i} d={`M${95+i*3} 394 C${10+i*5} ${205-i*4}, ${465-i*3} ${-50+i*8}, ${454-i*2} 171 S${85+i*6} ${299+i*3}, ${428-i*4} 413`} strokeWidth={1.2+i*.045} opacity={.45+i*.02} />)}
    </g>
    <path d="M161 342C111 276 138 134 237 101C327 71 433 144 427 254C421 357 305 416 214 386C191 378 173 364 161 342Z" fill={`url(#${id}-glass)`} stroke={`url(#${id}-edge)`} strokeWidth="2.4" />
    <path d="M183 341 C150 262 169 164 246 136 C330 110 391 178 391 254 C393 328 325 377 258 370 C229 366 202 357 183 341Z" fill={`url(#${id}-prism)`} opacity=".62" />
    <path d="M157 267C161 180 209 119 280 120C354 121 401 179 405 255" fill="none" stroke="#fff9e7" strokeOpacity=".7" strokeWidth="1.5" />
    <g className="wow-ribbon-front" fill="none" stroke={`url(#${id}-ribbon)`}>
      {Array.from({ length: 15 }, (_, i) => <path key={i} d={`M${91+i*2} ${325+i*3} C${185+i*4} ${445-i*2}, ${448-i*2} ${254-i*5}, ${417-i*2} ${131+i*2}`} strokeWidth={1+i*.065} />)}
    </g>
    <path d="M165 339C200 378 271 389 327 360" fill="none" stroke="#fff8e8" strokeOpacity=".77" />
    <path d="M214 143 C289 93 376 143 398 219" fill="none" stroke="#ffefd0" strokeOpacity=".86" strokeWidth="1.1" />
    <path d="M425 252 C440 343 371 410 288 412" fill="none" stroke="#e6c999" strokeOpacity=".65" strokeWidth="1.2" />
    <g fill="#fff1cb"><circle cx="435" cy="157" r="2.8" opacity=".87" /><circle cx="158" cy="342" r="1.7" opacity=".75" /><circle cx="399" cy="92" r="1.3" opacity=".7" /></g>
  </svg>;
}
