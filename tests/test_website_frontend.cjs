const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor(tag) {this.tag = tag; this.children = []; this.style = {setProperty(){}}; this.classList = {toggle(){return false},add(){},remove(){}}; this.value = ''; this.hidden = false;}
  set textContent(value) {this.text = String(value); this.children = [];}
  get textContent() {return (this.text || '') + this.children.map(x => x.textContent).join(' ');}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this.text = ''; this.children = items;}
  addEventListener() {}
  setAttribute() {}
  querySelector() {return new Element('source');}
  pause() {}
}
const ids = new Map();
const document = {
  getElementById(id) {if (!ids.has(id)) ids.set(id, new Element('div')); return ids.get(id);},
  createElement(tag) {return new Element(tag);},
  querySelectorAll() {return [];},
  addEventListener() {},
  documentElement: {style: {setProperty(){}}, scrollHeight: 1000},
  hidden: false
};
const location = {hash:'#home', pathname:'/'};
const context = vm.createContext({document, location, window: {
  addEventListener(){}, scrollTo(){}, matchMedia(){return {matches:true}}
}, fetch: async () => ({ok:false}), AbortSignal, setInterval(){}, console, innerHeight:800, scrollY:0});
vm.runInContext(fs.readFileSync('website/static/app.js','utf8'), context);
const run = code => vm.runInContext(code, context);
run('renderVoice({channels:[{name:"General", members:[{name:"Alice",avatar_url:null}]}],queue:{state:"Queue open",capacity:10,players:[{name:"Alice",rank:"Gold IV"}],waitlist:[{name:"Bob",rank:"Silver I"}]}})');
assert.match(ids.get('voice-channels').textContent, /Alice/);
assert.match(ids.get('queue-display').textContent, /Gold IV/);
assert.match(ids.get('queue-display').textContent, /Bob/);
assert.match(ids.get('queue-display').textContent, /9 spots open/);
run('renderVoice({channels:[],queue:{state:"Ready check",capacity:10,players:[],waitlist:[]}})');
assert.equal(ids.get('queue-state').textContent, 'Ready check');
run('standingsLoaded=true;standings={stats_hidden:true,leaderboard:[{name:"Hidden player"}],matches:[]};renderStandings()');
assert.equal(ids.get('leader-table').hidden, true);
assert.equal(ids.get('rows').children.length, 0);
assert.match(ids.get('notice-title').textContent, /coming soon/);
run('standings={stats_hidden:false,leaderboard:[{name:"Alice",rank:"Gold IV",rating:1200,role:"ADC",wins:2,losses:1}],matches:[]};renderStandings()');
assert.match(ids.get('rows').textContent, /Alice/);
assert.match(ids.get('rows').textContent, /Bot/);
run('location.hash="#matches";route()');
assert.equal(ids.get('leaders').hidden, true);
assert.equal(ids.get('matches').hidden, false);
console.log('Frontend queue, avatars, waitlist, privacy and routing checks passed.');
