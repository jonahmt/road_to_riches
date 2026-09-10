import type { CSSProperties } from "react";
import type { GameState } from "./protocol";
import type { PresentationState } from "./presentationQueue";
import { PLAYER_COLORS } from "./boardColors";
import "./venturePresentation.css";

function gridCells(state?: GameState): (number | null)[][] {
  return (state?.venture_grid as {cells?: (number | null)[][]} | undefined)?.cells ?? [];
}
export function VentureBack({small=false}:{small?:boolean}) {
  return <svg className={small ? "venture-back small" : "venture-back"} viewBox="0 0 80 80" aria-hidden="true"><path d="M14 68Q12 40 40 35Q68 40 66 68Z" fill="#7aa5bb" stroke="#31506a" strokeWidth="3"/><ellipse cx="40" cy="35" rx="21" ry="23" fill="#a2cfdd" stroke="#31506a" strokeWidth="3"/><path d="M16 20Q15 3 40 4Q65 3 64 20L68 25Q40 33 12 25Z" fill="#44738e" stroke="#31506a" strokeWidth="3"/><ellipse cx="32" cy="37" rx="4" ry="6" fill="white"/><ellipse cx="49" cy="37" rx="4" ry="6" fill="white"/><circle cx="33" cy="38" r="2" fill="#18354a"/><circle cx="48" cy="38" r="2" fill="#18354a"/><path d="M33 50Q40 55 47 50" fill="none" stroke="#31506a" strokeWidth="3"/></svg>;
}
function BackdropGrid({presentation, reveal=false}:{presentation:PresentationState;reveal?:boolean}) {
  const cells = gridCells(presentation.after);
  const before = gridCells(presentation.before);
  return <div className={`venture-reference-grid ${reveal ? "behind-card" : ""}`} aria-hidden="true">
    {cells.flatMap((row,r)=>row.map((owner,c)=>{
      const selected = reveal ? r===Number(presentation.data.row) && c===Number(presentation.data.col) : owner !== before[r]?.[c];
      return <div key={`${r}:${c}`} className={selected?"selected":""} style={{background:owner===null?undefined:PLAYER_COLORS[owner%PLAYER_COLORS.length]}}>
        {selected && reveal ? <b>{String(presentation.data.card_id ?? "?").replace(/^0+/,"")}</b> : <VentureBack small/>}
      </div>;
    }))}
  </div>;
}
export function VentureSelectionResult({presentation}:{presentation:PresentationState}) {
  return <div className="venture-selection-result" aria-label={`Player ${presentation.playerId} selected a venture card`}><BackdropGrid presentation={presentation}/></div>;
}
function CardArt({id}:{id:number}) {
  const die=<g><rect x="47" y="38" width="106" height="106" rx="18" fill="#fffdf0" stroke="#243a50" strokeWidth="5"/>{[[73,64],[127,64],[100,91],[73,118],[127,118]].map(([x,y])=><circle key={`${x}:${y}`} cx={x} cy={y} r="9" fill="#253749"/>)}</g>;
  return <svg className="venture-card-art" viewBox="0 0 200 210" aria-hidden="true">
    <circle cx="100" cy="100" r="86" fill="#c6dfec"/><path d="M100 8L120 68L183 38L143 95L194 134L129 130L136 194L100 143L56 193L65 128L7 132L57 96L20 40L79 68Z" fill="#fff5c0" opacity=".9"/>
    {id===1?<g fill="#f5c358" stroke="#644720" strokeWidth="4"><path d="M100 30L127 68H111V96H140V80L176 107L140 134V118H111V151H127L100 187L73 151H89V118H59V134L23 107L59 80V96H89V68H73Z"/></g>
    : id===2||id===4?<>{die}<text x="100" y="190" textAnchor="middle" fontSize="36" fontWeight="900" fill="#ae7724" stroke="#fff" strokeWidth="1">{id===4?"× 40":"ROLL!"}</text></>
    : id===3?<><ellipse cx="100" cy="127" rx="76" ry="35" fill="#724b9b" stroke="#d3b5ff" strokeWidth="9"/><ellipse cx="100" cy="127" rx="51" ry="19" fill="#1b3455"/><path d="M100 30L133 71H114V123H86V71H67Z" fill="#ffe298" stroke="#785628" strokeWidth="4"/><circle cx="35" cy="60" r="8" fill="#fff"/><circle cx="157" cy="45" r="6" fill="#fff"/></>
    : <g transform="translate(36 36) rotate(-7 64 67)"><rect width="128" height="140" rx="10" fill="#fffef4" stroke="#35516c" strokeWidth="4"/>{["♠","♥","♦","♣"].map((s,i)=><text key={s} x={i%2?92:35} y={i<2?64:120} fontSize="53" textAnchor="middle" fill={["#37a6da","#e45591","#e4b31f","#56a94b"][i]}>{s}</text>)}</g>}
  </svg>;
}
export function VentureCardReveal({presentation,assignedPlayerId,onContinue}:{presentation:PresentationState;assignedPlayerId:number|null;onContinue:()=>void}) {
  const id=Number(presentation.data.card_id);
  const owner=!presentation.requiresAcknowledgment||presentation.playerId===assignedPlayerId;
  const enabled=owner&&!presentation.acknowledgmentPending&&presentation.canContinue!==false;
  return <div className="venture-cinematic" role="dialog" aria-modal="true" aria-labelledby="venture-card-title" data-phase={presentation.phase}>
    <BackdropGrid presentation={presentation} reveal/>
    <article className="venture-tall-card" style={{"--card-player":PLAYER_COLORS[presentation.playerId%PLAYER_COLORS.length]} as CSSProperties}>
      <div className="venture-number-ribbon">Card No. <strong>{Number.isFinite(id)?id:"?"}</strong></div>
      <CardArt id={id}/><strong id="venture-card-title">{String(presentation.data.name??"Venture Card")}</strong>
      <span className="venture-card-recipient">Player {presentation.playerId}</span>
    </article>
    <button className="venture-explanation" disabled={!enabled} onClick={onContinue}
      aria-label={owner?"Continue from Venture Card":`Waiting for Player ${presentation.playerId}`}>
      <span>{String(presentation.data.description??"")}</span>
      <small>{presentation.acknowledgmentPending?"Continuing…":owner?"Enter / Continue":`Waiting for Player ${presentation.playerId}…`}</small>
    </button>
  </div>;
}
