import { useState } from "react";
import type { GameState } from "./protocol";
import { formatGold } from "./format";
import { PLAYER_COLORS } from "./boardColors";
const getPlayerColor = (id: number) => PLAYER_COLORS[id % PLAYER_COLORS.length];
import { PlayerPortrait } from "./board3d/PlayerPortrait";
import { matchStandings } from "./matchResults";
import "./matchResults.css";

export function MatchResults({ state, winner, onLeave }: {
  state: GameState; winner: number | null; onLeave: () => void;
}) {
  const [inspecting, setInspecting] = useState(false);
  const standings = matchStandings(state, winner);
  if (inspecting) return <div className="results-return" data-ui-scope>
    <strong>Final board · {winner === null ? "Match finished" : `Player ${winner} wins!`}</strong>
    <button onClick={() => setInspecting(false)}>Show results</button>
  </div>;
  return <div className="match-results-backdrop">
    <section className="match-results" role="dialog" aria-modal="true" aria-labelledby="results-title">
      <header className="results-celebration">
        <div className="results-stars" aria-hidden="true">✦ ★ ✦</div>
        {winner !== null && <PlayerPortrait color={getPlayerColor(winner)} playerId={winner} />}
        <p className="eyebrow">Match complete</p>
        <h1 id="results-title">{winner === null ? "Thanks for playing!" : `Player ${winner} wins!`}</h1>
        <p>{state.players.filter(p => p.bankrupt).length >= state.board.max_bankruptcies
          ? "The bankruptcy limit was reached."
          : `The race to the bank is over. Target: ${formatGold(state.board.target_networth)}.`}</p>
      </header>
      <div className="results-table-wrap"><table>
        <caption>Final standings</caption>
        <thead><tr><th>Place</th><th>Player</th><th>Net worth</th><th>Cash</th><th>Properties</th><th>Stocks</th><th>Level</th></tr></thead>
        <tbody>{standings.map(({ player, worth, propertyValue, stockValue }, index) => <tr key={player.player_id} className={player.player_id === winner ? "results-winner" : ""}>
          <td>{index + 1}</td><th><span style={{ color: getPlayerColor(player.player_id) }}>●</span> Player {player.player_id}{player.bankrupt && <small>Bankrupt</small>}</th>
          <td><strong>{formatGold(worth)}</strong></td><td>{formatGold(player.ready_cash)}</td><td>{formatGold(propertyValue)}</td><td>{formatGold(stockValue)}</td><td>{player.level}</td>
        </tr>)}</tbody>
      </table></div>
      <p className="results-note">Net worth includes cash, property value and stock holdings.</p>
      <footer><button onClick={() => setInspecting(true)}>Inspect final board</button><button className="secondary" onClick={onLeave}>Leave results</button></footer>
    </section>
  </div>;
}
