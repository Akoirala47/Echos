const d3 = require('d3');
const nodes = [{id: 'A', x: 0, y: 0}, {id: 'B', x: 0, y: 1}];
const sim = d3.forceSimulation(nodes)
  .force('charge', d3.forceManyBody().strength(-400).distanceMin(30))
  .stop();

sim.tick();
console.log(nodes[0].x, nodes[0].y);
