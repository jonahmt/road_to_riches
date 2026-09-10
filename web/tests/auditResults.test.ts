import assert from "node:assert/strict";
import test from "node:test";
import type { GameState } from "../src/protocol.ts";
import { matchStandings, readCompletedMatch, writeCompletedMatch } from "../src/matchResults.ts";
import { statusResult } from "../src/statusResults.ts";
import { beatTiming, presentedState } from "../src/presentationTiming.ts";
import type { PresentationState } from "../src/presentationQueue.ts";

const state = {
  players: [0, 1, 2].map(player_id => ({player_id,ready_cash: [1900,2400,500][player_id],level:1,owned_properties:player_id===2?[0]:[],statuses:[],owned_stock:player_id===2?{0:10}:{},bankrupt:false})),
  board: {squares:[{id:0,property_owner:2,shop_current_value:200,statuses:[]}],target_networth:1800},
  stock: {stocks:[{district_id:0,value_component:12,fluctuation_component:3}]},
} as unknown as GameState;
test("bank winner leads the standings even when another player is richer",()=>{
  const rows=matchStandings(state,0);
  assert.deepEqual(rows.map(r=>r.player.player_id),[0,1,2]);
  assert.deepEqual([rows[2].propertyValue,rows[2].stockValue,rows[2].worth],[200,150,850]);
  assert.deepEqual(matchStandings(state,null).map(r=>r.player.player_id),[1,0,2]);
});
test("completed snapshots survive reload and can be explicitly cleared",()=>{
  let stored:string|null=null;
  Object.defineProperty(globalThis,"sessionStorage",{configurable:true,value:{getItem:()=>stored,setItem:(_:string,v:string)=>{stored=v},removeItem:()=>{stored=null}}});
  const result={state,winner:0,uri:"ws://localhost:18790",playerId:0};
  writeCompletedMatch(result);assert.deepEqual(readCompletedMatch(),result);
  writeCompletedMatch(null);assert.equal(readCompletedMatch(),null);
  stored="broken";assert.equal(readCompletedMatch(),null);
  Object.defineProperty(globalThis,"sessionStorage",{configurable:true,get:()=>{throw Error("disabled")}});
  assert.doesNotThrow(()=>writeCompletedMatch(result));assert.equal(readCompletedMatch(),null);
  delete (globalThis as any).sessionStorage;
});
test("Boon starts and expires with explicit commission descriptions",()=>{
  const next=structuredClone(state);next.players[0].statuses=[{type:"commission",modifier:20,remaining_turns:5}];
  const start=statusResult(state,next)!;assert.equal(start.title,"Boon!");assert.match(start.lines[0],/20% commission.*5 turns remaining/);
  assert.match(statusResult(next,state)!.lines[0],/commission.*ended/);
});
test("shop closure and reopening group related shops without losing the cause",()=>{
  const next=structuredClone(state);next.board.squares[0].statuses=[{type:"closed",modifier:0,remaining_turns:1}];
  assert.equal(statusResult(state,next)!.title,"Take a break");assert.match(statusResult(next,state)!.lines[0],/rent resumes/);
  assert.equal(statusResult(state,state),null);
});
test("Arcade winnings stay hidden until the final reel settles",()=>{
  const after=structuredClone(state);after.players[0].ready_cash+=50;
  const beat={requestId:"arcade",type:"arcade_result",playerId:0,data:{},before:state,after,requiresAcknowledgment:true,acknowledgmentPending:false} as PresentationState;
  assert.equal(presentedState(beat,2199)!.players[0].ready_cash,1900);
  assert.equal(presentedState(beat,2450)!.players[0].ready_cash,1925);
  assert.equal(presentedState(beat,2700)!.players[0].ready_cash,1950);
  assert(beatTiming(beat).reveal>=2700);
});
