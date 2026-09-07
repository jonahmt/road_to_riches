import assert from 'node:assert/strict';
import test from 'node:test';
import { navigationDirection, nextControl } from '../src/uiNavigation.ts';

test('WASD and arrow keys use the same UI directions, other keys remain native', () => {
  for (const [letter, arrow, direction] of [['W','ArrowUp','up'],['s','ArrowDown','down'],['a','ArrowLeft','left'],['D','ArrowRight','right']]) {
    assert.equal(navigationDirection(letter), direction);
    assert.equal(navigationDirection(arrow), direction);
  }
  for (const key of ['Enter', 'Escape', 'Tab', '9']) assert.equal(navigationDirection(key), null);
});
test('vertical menus wrap and horizontal action rows follow their visible direction', () => {
  const vertical = [0,1,2].map(y => ({x:0,y:y*50,width:100,height:40}));
  assert.equal(nextControl(vertical,0,'up'),2);
  assert.equal(nextControl(vertical,2,'down'),0);
  assert.equal(nextControl(vertical,1,'down'),2);
  const horizontal = [0,1,2].map(x => ({x:x*120,y:0,width:100,height:40}));
  assert.equal(nextControl(horizontal,0,'right'),1);
  assert.equal(nextControl(horizontal,0,'left'),2);
});
test('two-column forms navigate aligned controls before diagonal controls', () => {
  const grid = [{x:0,y:0,width:100,height:40},{x:120,y:0,width:100,height:40},
    {x:0,y:60,width:100,height:40},{x:120,y:60,width:100,height:40}];
  assert.equal(nextControl(grid,0,'down'),2);
  assert.equal(nextControl(grid,0,'right'),1);
  assert.equal(nextControl(grid,3,'up'),1);
  assert.equal(nextControl(grid,3,'left'),2);
  assert.equal(nextControl([],0,'up'),-1);
  assert.equal(nextControl(grid,-1,'down'),0);
});
