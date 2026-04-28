const d3 = require('d3');
const visNodes = [{id: 'A'}, {id: 'B'}];
const visIds = new Set(visNodes.map(n => n.id));
const _allEdges = [{source: 'A', target: 'B'}];
const _hasVis = e => visIds.has(e.source.id || e.source) && visIds.has(e.target.id || e.target);
const visEdges = _allEdges.filter(_hasVis);
const links = visEdges.map(e => ({
  ...e,
  source: e.source.id || e.source,
  target: e.target.id || e.target,
}));
try {
  d3.forceSimulation(visNodes).force('link', d3.forceLink(links).id(d => d.id));
  console.log("No error!");
} catch (e) {
  console.log("ERROR:", e.message);
}
