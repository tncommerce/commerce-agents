import { useId } from 'react';
import ScentScene, {sceneFor} from './ScentScene';
import styles from './ScentStudy.module.css';
export type ScentMotif = 'blossom' | 'architecture' | 'embers' | 'citrus' | 'botanical' | 'prism';
const motifs: ScentMotif[] = ['blossom','architecture','embers','citrus','botanical','prism'];
export function motifForName(name:string,notes:string[]=[]):ScentMotif {
 const text=notes.join(' ').toLowerCase();
 if(/rose|jasmin|magnolie|iris|blüte|gardenie/.test(text))return 'blossom';
 if(/minze|lavendel|salbei|grün/.test(text))return 'botanical';
 if(/zitrone|mandarine|bergamotte|grapefruit|orange/.test(text))return 'citrus';
 if(/rauch|holz|oud|leder/.test(text))return 'architecture';
 return motifs[Array.from(name).reduce((n,c)=>n+c.charCodeAt(0),0)%motifs.length];
}
/** Original editorial vectors, never a product photograph or bottle replica. */
export default function ScentStudy({name,notes=[],tone='sage',compact=false,motif}:{name:string;notes?:string[];tone?:'sage'|'rose'|'amber';compact?:boolean;motif?:ScentMotif}) {
 const id=useId().replace(/:/g,'');const world=motif||motifForName(name,notes);const url=(k:string)=>`url(#${id}-${k})`;const scene=sceneFor(name);
 return <figure style={scene?{color:scene.ink}:undefined} className={`${styles.art} ${styles[tone]} ${styles[world]} ${compact?styles.compact:''}`} data-scent-artwork data-motif={world}>
 <span className={styles.edition}>DUFYND <span>OLFAKTIVE STUDIEN</span></span>
 {scene?<ScentScene scene={scene} id={id}/>:<svg className={styles.canvas} viewBox="0 0 640 720" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
 <defs>
 <radialGradient id={`${id}-light`} cx=".7" cy=".25" r=".9"><stop stopColor="var(--light)"/><stop offset="1" stopColor="var(--ground)"/></radialGradient>
 <linearGradient id={`${id}-petal`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#fffef8"/><stop offset=".38" stopColor="#fff1df"/><stop offset=".7" stopColor="var(--soft)"/><stop offset="1" stopColor="var(--ink)"/></linearGradient>
 <linearGradient id={`${id}-edge`} x1="0" y1="0" x2="1" y2=".6"><stop stopColor="var(--ink)"/><stop offset=".52" stopColor="var(--soft)"/><stop offset=".57" stopColor="#e9d5ad"/><stop offset="1" stopColor="var(--ink)"/></linearGradient>
 <radialGradient id={`${id}-ember`}><stop stopColor="#f9d2a0"/><stop offset=".2" stopColor="#c66b37"/><stop offset=".7" stopColor="#4c3026"/><stop offset="1" stopColor="#201e1c"/></radialGradient>
 <filter id={`${id}-shadow`} x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="16" stdDeviation="14" floodColor="#201d18" floodOpacity=".2"/></filter>
 </defs>
 <rect width="640" height="720" fill={url('light')}/>
 <g opacity=".13" fill="none" stroke="var(--ink)"><path d="M45 105H595M45 615H595M80 80V645M560 80V645"/><circle cx="320" cy="350" r="245"/></g>
 {world==='blossom'&&<g><circle cx="415" cy="243" r="136" fill="var(--soft)" opacity=".35"/><path d="M290 670Q350 470 312 326" fill="none" stroke="var(--ink)" strokeWidth="3"/><path d="M304 575Q122 564 166 411Q289 440 304 575Z" fill={url('edge')}/><g transform="translate(325 331)" filter={url('shadow')}>
 {[0,60,120,180,240,300].map(angle=><g key={angle} transform={`rotate(${angle})`}><path d="M0 12C-136-48-165-187-73-230C7-250 79-110 0 12Z" fill={url('petal')} stroke="#fdf1de" strokeWidth=".7"/><path d="M-6-4Q-34-110-72-215" fill="none" stroke="var(--ink)" opacity=".2"/></g>)}<circle r="32" fill="#b79b67"/>{Array.from({length:26},(_,i)=><circle key={i} cx={Math.cos(i*2.4)*Math.sqrt(i)*5} cy={Math.sin(i*2.4)*Math.sqrt(i)*5} r="2.2" fill="#fff2c8"/>)}</g></g>}
 {world==='architecture'&&<g><circle cx="417" cy="246" r="137" fill="#c6c99d" opacity=".75"/><g filter={url('shadow')} transform="translate(48 124) scale(.76) rotate(-14 330 280)">{[0,1,2,3,4,5,6].map(i=><g key={i} transform={`translate(${i*34} ${i*-31})`}><path d="M92 325L330 213L513 286L274 399Z" fill={url('petal')}/><path d="M92 325L274 399V463L92 389Z" fill="#294b40"/><path d="M274 399L513 286V350L274 463Z" fill={url('edge')}/><path d="M93 325L274 399L512 286" fill="none" stroke="#e3dda8" strokeWidth="1.5"/></g>)}</g><path d="M479 575Q458 482 516 421M493 518Q539 497 548 456M490 509Q451 491 446 466" fill="none" stroke="#d5d1a4" strokeWidth="2"/></g>}
 {world==='embers'&&<g><ellipse cx="354" cy="391" rx="257" ry="218" fill={url('ember')}/><g transform="translate(332 386) rotate(-22)" fill="none">{Array.from({length:28},(_,i)=><ellipse key={i} rx={37+i*7.8} ry={27+i*5.3} stroke={i%4===0?'#d99059':'#bc80594f'} strokeWidth={i%4===0?1.6:1} transform={`rotate(${i%3*2})`}/>)}<path d="M-238 0L-130 8L-89-8M189-129L114-49L69-42M165 140L82 63L73 15" stroke="#171918" strokeWidth="8"/></g>{[0,1,2].map(i=><path key={i} d={`M${260+i*37} 395C${70+i*70} 250 ${497-i*34} 244 ${326+i*23} 89`} fill="none" stroke="#e9c59a" opacity={.2-i*.04} strokeWidth={14-i*3}/>)}{Array.from({length:18},(_,i)=><circle key={i} cx={125+(i*83)%410} cy={154+(i*53)%430} r={i%3===0?2:1} fill="#efb46e" opacity=".65"/>)}</g>}
 {world==='citrus'&&<g transform="translate(322 359) rotate(-28)" filter={url('shadow')}><circle r="210" fill={url('edge')}/><circle r="192" fill="#eee2be"/>{Array.from({length:10},(_,i)=><g key={i} transform={`rotate(${i*36})`}><path d="M10-17L44-174Q96-167 132-119L26-6Z" fill={url('petal')}/><path d="M22-13L88-148" stroke="var(--ink)" opacity=".25"/></g>)}<circle r="20" fill="#fff8e4"/><path d="M130 164Q276 128 239 24Q146 28 130 164Z" fill={url('edge')}/></g>}
 {world==='botanical'&&<g fill={url('petal')} stroke="var(--ink)" strokeWidth=".8"><path d="M298 635Q289 416 378 118M303 518Q166 353 170 255M324 352Q474 330 493 218" fill="none" strokeWidth="2"/>{[0,1,2,3,4,5].map(i=><g key={i} transform={`translate(${299+i*11} ${532-i*66}) rotate(${i%2?-35:25})`}><path d="M0 0Q-128-18-105-93Q-21-98 0 0Z"/><path d="M2-7Q97-126 140-65Q118-4 2-7Z"/><path d="M-3-3L-91-80M6-10L125-63" fill="none" opacity=".2"/></g>)}</g>}
 {world==='prism'&&<g transform="translate(320 360) rotate(24)" filter={url('shadow')}><circle r="238" fill="var(--soft)" opacity=".22"/>{[-2,-1,0,1,2].map(i=><g key={i} transform={`translate(${i*69} ${Math.abs(i)*30})`}><path d="M-30-185L26-217L26 168L-30 202Z" fill={url('petal')}/><path d="M26-217L50-182V193L26 168Z" fill={url('edge')}/><path d="M-30 202L26 168L50 193L-5 228Z" fill="var(--ink)"/></g>)}</g>}
 <text x="45" y="622" fill="var(--ink)" opacity=".16" fontSize="76" fontFamily="Georgia,serif" fontStyle="italic">{world==='blossom'?'florale':world==='architecture'?'structure':world==='embers'?'boisé':world==='citrus'?'agrume':world==='botanical'?'herbier':'matière'}</text>
 </svg>}<div className={styles.annotation}><span>{notes[0]||name}</span><span>{notes[1]||'Duftkomposition'}</span></div><figcaption>Duftillustration · kein Produktfoto</figcaption></figure>;
}
