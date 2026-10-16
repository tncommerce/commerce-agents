"use client";

import { useEffect, useId, useRef, useState, type PointerEvent } from "react";
import styles from "./PerfumeObject.module.css";

/** An original, unbranded glass study. No product photograph or WebGL dependency. */
export default function PerfumeObject({ className = "" }: { className?: string }) {
  const id = `perfume-${useId().replace(/:/g, "")}`;
  const object = useRef<HTMLDivElement>(null);
  const canTilt = useRef(false);
  const [explored, setExplored] = useState(false);
  const fill = (name: string) => `url(#${id}-${name})`;

  useEffect(() => {
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const pointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    const update = () => {
      canTilt.current = !motion.matches && pointer.matches;
      if (!canTilt.current && object.current) {
        object.current.style.setProperty("--tilt-x", "0deg");
        object.current.style.setProperty("--tilt-y", "0deg");
      }
    };
    update();
    motion.addEventListener("change", update);
    pointer.addEventListener("change", update);
    return () => {
      motion.removeEventListener("change", update);
      pointer.removeEventListener("change", update);
    };
  }, []);

  function tilt(event: PointerEvent<HTMLDivElement>) {
    if (!canTilt.current || event.pointerType === "touch" || !object.current) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, ((event.clientX - bounds.left) / bounds.width - 0.5) * 2));
    const y = Math.max(-1, Math.min(1, ((event.clientY - bounds.top) / bounds.height - 0.5) * 2));
    object.current.style.setProperty("--tilt-x", `${(-y * 3).toFixed(2)}deg`);
    object.current.style.setProperty("--tilt-y", `${(x * 5).toFixed(2)}deg`);
  }

  function resetTilt() {
    object.current?.style.setProperty("--tilt-x", "0deg");
    object.current?.style.setProperty("--tilt-y", "0deg");
  }

  return (
    <figure
      className={`${styles.figure} ${className}`}
      data-perfume-object="original"
      data-dufynd-bottle="original"
      data-explored={explored ? "true" : "false"}
    >
      <noscript><style>{"[data-dufynd-bottle-control]{display:none}"}</style></noscript>
      <div className={styles.scene} onPointerMove={tilt} onPointerLeave={resetTilt}>
        <div className={styles.halo} aria-hidden="true" />
        <div className={styles.floor} aria-hidden="true" />
        <div className={styles.object} ref={object}>
          <svg
            className={styles.drawing}
            viewBox="0 0 600 620"
            role="img"
            aria-labelledby={`${id}-title ${id}-description`}
          >
            <title id={`${id}-title`}>Ein Parfumflakon. Glas, Licht und Bernstein.</title>
            <desc id={`${id}-description`}>
              Eine originale, generische Flakonstudie von DUFYND. Facettiertes Glas
              umschließt bernsteinfarbene Flüssigkeit unter einem metallischen Verschluss.
              {explored ? " Der Verschluss ist angehoben und gibt den Sprühkopf frei." : ""}
            </desc>
            <defs>
              <linearGradient id={`${id}-back`} x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="#fffdf7" stopOpacity=".93" />
                <stop offset=".48" stopColor="#e6ddc7" stopOpacity=".65" />
                <stop offset="1" stopColor="#9c8358" stopOpacity=".6" />
              </linearGradient>
              <linearGradient id={`${id}-front`} x1="0" y1="0" x2="1" y2=".12">
                <stop stopColor="#fffdf5" stopOpacity=".84" />
                <stop offset=".08" stopColor="#b9ae8c" stopOpacity=".42" />
                <stop offset=".17" stopColor="#fffef9" stopOpacity=".78" />
                <stop offset=".45" stopColor="#fffcf0" stopOpacity=".38" />
                <stop offset=".79" stopColor="#eee4ca" stopOpacity=".25" />
                <stop offset=".94" stopColor="#9f8b5d" stopOpacity=".57" />
                <stop offset="1" stopColor="#fffdf3" stopOpacity=".96" />
              </linearGradient>
              <linearGradient id={`${id}-side`} x1="0" y1="0" x2="1" y2=".2">
                <stop stopColor="#75684b" stopOpacity=".62" />
                <stop offset=".16" stopColor="#f5edd8" stopOpacity=".77" />
                <stop offset=".4" stopColor="#d4c49d" stopOpacity=".76" />
                <stop offset=".74" stopColor="#a18d64" stopOpacity=".58" />
                <stop offset="1" stopColor="#fbf8ec" stopOpacity=".93" />
              </linearGradient>
              <linearGradient id={`${id}-shoulder`} x1="0" y1="0" x2=".2" y2="1">
                <stop stopColor="#fdfbf3" />
                <stop offset=".4" stopColor="#d8ceb0" stopOpacity=".63" />
                <stop offset=".63" stopColor="#fffcf2" stopOpacity=".9" />
                <stop offset="1" stopColor="#aa9870" stopOpacity=".58" />
              </linearGradient>
              <linearGradient id={`${id}-amber`} x1="0" y1="0" x2=".9" y2="1">
                <stop stopColor="#edd09a" stopOpacity=".56" />
                <stop offset=".37" stopColor="#d5a864" stopOpacity=".68" />
                <stop offset=".74" stopColor="#b57b34" stopOpacity=".77" />
                <stop offset="1" stopColor="#f3dba4" stopOpacity=".88" />
              </linearGradient>
              <linearGradient id={`${id}-amber-side`} x1="0" y1="0" x2="1" y2=".4">
                <stop stopColor="#8b571e" stopOpacity=".78" />
                <stop offset=".49" stopColor="#d8ad63" stopOpacity=".8" />
                <stop offset="1" stopColor="#f1d79a" stopOpacity=".54" />
              </linearGradient>
              <linearGradient id={`${id}-liquid-top`} x1="0" y1="0" x2="0" y2="1">
                <stop stopColor="#f9e8bd" stopOpacity=".9" />
                <stop offset="1" stopColor="#a6793d" stopOpacity=".64" />
              </linearGradient>
              <linearGradient id={`${id}-base`} x1="0" y1="0" x2="0" y2="1">
                <stop stopColor="#b8a478" stopOpacity=".78" />
                <stop offset=".24" stopColor="#fffdf1" stopOpacity=".95" />
                <stop offset=".57" stopColor="#e8d7ab" stopOpacity=".74" />
                <stop offset=".84" stopColor="#7e6b47" stopOpacity=".65" />
                <stop offset="1" stopColor="#fff8dd" stopOpacity=".95" />
              </linearGradient>
              <linearGradient id={`${id}-metal`} x1="0" y1="0" x2="1" y2=".03">
                <stop stopColor="#756348" />
                <stop offset=".04" stopColor="#c8b38b" />
                <stop offset=".14" stopColor="#f1e6ca" />
                <stop offset=".24" stopColor="#aa9167" />
                <stop offset=".42" stopColor="#e4d4b2" />
                <stop offset=".57" stopColor="#fff9e7" />
                <stop offset=".66" stopColor="#d3bc91" />
                <stop offset=".83" stopColor="#b09870" />
                <stop offset=".94" stopColor="#796548" />
                <stop offset="1" stopColor="#c7b18a" />
              </linearGradient>
              <linearGradient id={`${id}-metal-side`} x1="0" y1="0" x2="1" y2=".2">
                <stop stopColor="#806c4f" />
                <stop offset=".46" stopColor="#bca57e" />
                <stop offset="1" stopColor="#e3d3b2" />
              </linearGradient>
              <linearGradient id={`${id}-metal-top`} x1="0" y1="0" x2=".8" y2="1">
                <stop stopColor="#faf3dd" />
                <stop offset=".45" stopColor="#dfceaa" />
                <stop offset="1" stopColor="#a78e65" />
              </linearGradient>
              <linearGradient id={`${id}-glare`} x1="0" y1="0" x2="1" y2="0">
                <stop stopColor="#fffdf5" stopOpacity="0" />
                <stop offset=".5" stopColor="#fffdf5" stopOpacity=".74" />
                <stop offset="1" stopColor="#fffdf5" stopOpacity="0" />
              </linearGradient>
              <linearGradient id={`${id}-label`} x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="#fcf9ee" />
                <stop offset=".55" stopColor="#f1ebda" />
                <stop offset="1" stopColor="#dfd4bc" />
              </linearGradient>
              <clipPath id={`${id}-front-clip`}>
                <path d="M199 257 Q179 266 179 293 V520 Q179 550 207 554 H375 Q408 551 408 521 V289 Q408 266 386 257Z" />
              </clipPath>
            </defs>

            <g className={styles.flacon}>
              {/* Rear wall, oblique shoulder, and the substantial right-hand glass facet. */}
              <path d="M232 230H415Q443 230 446 259V498Q445 527 418 535H233Q209 528 209 505V258Q209 238 232 230Z" fill={fill("back")} stroke="#c9bda2" strokeWidth="1.1" />
              <path d="M386 257 426 233Q446 242 446 262V499Q446 522 424 534L384 555Q408 543 408 521V289Q408 270 386 257Z" fill={fill("side")} stroke="#d3c9af" strokeWidth="1" />
              <path d="M199 257 232 230Q239 226 252 226H413Q431 227 439 238L386 269 206 275Z" fill={fill("shoulder")} stroke="#fffdf4" strokeOpacity=".8" />
              <path d="M207 254 241 233H411L382 253Z" fill="#fffdf6" fillOpacity=".73" />
              <path d="M219 260 251 238H390L373 258" fill="none" stroke="#b4a17a" strokeOpacity=".36" strokeWidth="3" />

              {/* Liquid has a visible surface and a darker refracted side, not a flat fill. */}
              <path d="M200 332 235 309H424V494Q424 512 408 518L381 533H213Q197 531 197 514Z" fill={fill("amber-side")} />
              <path d="M199 332Q288 340 387 331L424 309Q327 315 235 309Z" fill={fill("liquid-top")} />
              <path d="M199 332Q289 340 387 331V513Q385 535 364 536H222Q199 536 199 513Z" fill={fill("amber")} />
              <path d="M201 332Q288 342 386 331" fill="none" stroke="#fff3d4" strokeWidth="2" strokeOpacity=".85" />
              <path d="M386 332 423 310V493Q424 509 408 515L386 526Z" fill="#9a6c32" fillOpacity=".23" />

              {/* The dip tube remains visible through the glass above and below the label. */}
              <path d="M302 239 305 509Q305 522 313 527" fill="none" stroke="#fcf4d9" strokeOpacity=".55" strokeWidth="3" />
              <path d="M305 240 308 509" fill="none" stroke="#a68858" strokeOpacity=".18" strokeWidth="1" />

              <path d="M199 257Q179 266 179 293V520Q179 550 207 554H375Q408 551 408 521V289Q408 266 386 257Z" fill={fill("front")} stroke="#f8f4e5" strokeWidth="2" />
              <path d="M203 268Q190 277 190 296V517Q190 542 212 543H373Q397 540 397 519V292Q397 278 382 269" fill="none" stroke="#a29472" strokeOpacity=".42" strokeWidth="1" />
              <path d="M199 281V517Q198 536 214 539" fill="none" stroke="#fffdf4" strokeOpacity=".82" strokeWidth="4" />
              <path d="M395 282V516Q395 537 377 542" fill="none" stroke="#fffdf2" strokeOpacity=".68" strokeWidth="3" />
              <path d="M184 305V514" fill="none" stroke="#fefcf1" strokeWidth="2" />
              <path d="M437 265V491Q438 511 421 521" fill="none" stroke="#fffcf0" strokeOpacity=".74" strokeWidth="3" />
              <path d="M431 272V486" fill="none" stroke="#8d7b54" strokeOpacity=".25" strokeWidth="2" />

              {/* Thick heel with caustic bands. */}
              <path d="M190 518Q194 540 216 540H369Q392 538 399 518V528Q396 548 373 550H210Q191 546 190 531Z" fill={fill("base")} />
              <path d="M201 545H376" fill="none" stroke="#fffbe9" strokeWidth="1.5" />
              <path d="M211 548H366" fill="none" stroke="#8e7a52" strokeOpacity=".38" />

              {/* Restrained ivory paper inset, original geometry and typography. */}
              <path d="M232 366H359V474H232Z" fill="#745d35" fillOpacity=".14" transform="translate(1 2)" />
              <path d="M231 364H359V472H231Z" fill={fill("label")} stroke="#fffaf0" strokeOpacity=".7" />
              <path d="M236 369H354V467H236Z" fill="none" stroke="#a99571" strokeOpacity=".35" strokeWidth=".7" />
              <text x="295" y="395" textAnchor="middle" fill="#7f6c4d" fontFamily="Arial, sans-serif" fontSize="8" letterSpacing="3.5">DUFYND</text>
              <text x="295" y="433" textAnchor="middle" fill="#55452f" fontFamily="Georgia, serif" fontSize="34" fontStyle="italic">n° 01</text>
              <path d="M281 446H309" stroke="#9f8960" strokeWidth=".7" />
              <text x="295" y="459" textAnchor="middle" fill="#8b7857" fontFamily="Arial, sans-serif" fontSize="5.8" letterSpacing="2.1">ÉTUDE DE PARFUM</text>

              <g clipPath={fill("front-clip")} aria-hidden="true">
                <path d="M210 246 231 246 273 560 245 560Z" fill={fill("glare")} opacity=".5" />
                <path d="M335 254 349 254 382 553 369 553Z" fill={fill("glare")} opacity=".22" />
                <path d="M186 294 404 269" stroke="#fffdf5" strokeWidth="1" strokeOpacity=".52" />
              </g>

              {/* Metal collar and atomizer. Always present, exposed by the optional control. */}
              <path d="M270 218 289 205H333L348 217V249Q313 261 270 248Z" fill={fill("metal")} stroke="#b6a07a" strokeWidth=".7" />
              <ellipse cx="309" cy="216" rx="39" ry="9" fill={fill("metal-top")} />
              <path d="M288 193 299 187H322L329 192V218Q309 224 288 217Z" fill={fill("metal")} />
              <path d="M288 193 299 187H322L329 192 317 198H298Z" fill="#f6eed8" />
              <ellipse cx="300" cy="205" rx="3.1" ry="2.7" fill="#665b47" />
              <ellipse cx="299.6" cy="204.8" rx="1.3" ry="1.1" fill="#302d26" />
              <path d="M274 243Q310 254 344 242" fill="none" stroke="#f8ecd0" strokeWidth="1" />

              <g className={styles.cap} data-perfume-cap="true">
                <path d="M251 151 281 134H354L370 145V211L341 230H252Z" fill={fill("metal-side")} stroke="#ae956c" strokeWidth=".7" />
                <path d="M251 151H341V230H251Z" fill={fill("metal")} />
                <path d="M251 151 281 134H354L370 145 341 162Z" fill={fill("metal-top")} />
                <path d="M251 151 341 162V230H251Z" fill={fill("metal")} />
                <path d="M341 162 370 145V211L341 230Z" fill={fill("metal-side")} />
                <path d="M254 153 341 164 367 148" fill="none" stroke="#fff7df" strokeOpacity=".86" strokeWidth="1.2" />
                <path d="M256 157V225M263 159V225M328 166V225" stroke="#fff4d7" strokeOpacity=".24" strokeWidth=".7" />
                <path d="M251 220H341L370 202" fill="none" stroke="#705c3d" strokeOpacity=".5" strokeWidth=".8" />
                <path d="M252 224H341L369 207" fill="none" stroke="#f8eac9" strokeOpacity=".66" strokeWidth=".7" />
                <path d="M281 137H352L363 145 340 158 259 151Z" fill="none" stroke="#b29b73" strokeOpacity=".52" strokeWidth=".7" />
              </g>
            </g>
          </svg>
        </div>
        <span className={styles.studyLabel} aria-hidden="true">DUFYND / Flakonstudie</span>
      </div>
      <figcaption className={styles.controls}>
        <span className={styles.caption}>Ein Duft. Viele Facetten.</span>
        <button
          type="button"
          className={styles.control}
          aria-pressed={explored}
          aria-label={explored ? "Flakon schließen" : "Flakon erkunden: Verschluss anheben"}
          onClick={() => setExplored((current) => !current)}
          data-perfume-explore="true"
          data-dufynd-bottle-control="true"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.2" className={styles.controlIcon} />
            <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeOpacity=".35" />
          </svg>
          {explored ? "Flakon schließen" : "Flakon erkunden"}
        </button>
      </figcaption>
    </figure>
  );
}
