'use client';
import {useState} from 'react';
import {brandKey} from '@/lib/brandIdentity';
import styles from '@/app/marken/brands.module.css';
export default function BrandDirectory({brands}:{brands:{slug:string;name:string;count:number}[]}){
 const [query,setQuery]=useState('');const visible=brands.filter(b=>brandKey(b.name).includes(brandKey(query)));
 const letters=[...new Set(visible.map(b=>brandKey(b.name)[0].toUpperCase()))];
 return <><label className={styles.search}>Marke finden<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Chanel, Prada, Yves Saint Laurent …" autoComplete="off"/></label><p role="status" className={styles.count}>{visible.length} Marken · {visible.reduce((n,b)=>n+b.count,0)} öffentliche Duftprofile</p><nav className={styles.alphabet} aria-label="Alphabet">{letters.map(l=><a key={l} href={`#marke-${l}`}>{l}</a>)}</nav>{letters.map(l=><section key={l} id={`marke-${l}`} className={styles.group}><h2>{l}</h2><div>{visible.filter(b=>brandKey(b.name)[0].toUpperCase()===l).map(b=><a data-brand-slug={b.slug} key={b.slug} href={`/marken/${b.slug}`}><span>{b.name}</span><small>{b.count} {b.count===1?'Duftprofil':'Duftprofile'} <b>↗</b></small></a>)}</div></section>)}{!visible.length&&<p>Keine passende Marke. Versuche einen anderen Namen.</p>}</>;
}
