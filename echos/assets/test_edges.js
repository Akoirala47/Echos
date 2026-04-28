const fs = require('fs');
const d3 = require('d3');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;

const html = fs.readFileSync('graph.html', 'utf8');

const dom = new JSDOM(html, { runScripts: "dangerously" });
global.document = dom.window.document;
global.window = dom.window;
dom.window.d3 = d3;

setTimeout(() => {
  try {
    const data = {
      nodes: [
        {id: 'dir1', kind: 'dir'},
        {id: 'file1', kind: 'file', dir_id: 'dir1'},
        {id: 'file2', kind: 'file', dir_id: 'dir1'}
      ],
      edges: []
    };
    dom.window.loadGraph(data);
    dom.window.expandDirectory('dir1');
    
    const edges = dom.window.document.querySelectorAll('.edge');
    console.log("Number of edges:", edges.length);
    edges.forEach((e, i) => {
      console.log(`Edge ${i}: class='${e.getAttribute('class')}', d='${e.getAttribute('d')}'`);
    });
  } catch(e) {
    console.error("CAUGHT EXCEPTION:", e.message);
  }
}, 100);
