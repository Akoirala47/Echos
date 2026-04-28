const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;
const html = fs.readFileSync('graph.html', 'utf8');

// Load D3 globally inside the JSDOM window
const dom = new JSDOM(html, { runScripts: "dangerously" });

// Polyfill document and window for D3
global.document = dom.window.document;
global.window = dom.window;

const d3 = require('d3');
dom.window.d3 = d3;

dom.window.console.error = (msg) => console.log("ERROR:", msg);
dom.window.console.warn = (msg) => console.log("WARN:", msg);
dom.window.console.log = (msg) => console.log("LOG:", msg);

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
    console.log("Test completed. Node 1 pos:", dom.window._nodeById['file1'].x);
  } catch(e) {
    console.error("CAUGHT EXCEPTION:", e.message);
  }
}, 100);
