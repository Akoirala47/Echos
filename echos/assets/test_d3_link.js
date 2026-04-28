const d3 = require('d3');
const nodes = [{id: 'A'}, {id: 'B'}];
const links = [{source: 'A', target: 'MISSING'}];
try {
  d3.forceSimulation(nodes).force('link', d3.forceLink(links).id(d => d.id));
  console.log("No error!");
} catch (e) {
  console.log("ERROR:", e.message);
}
