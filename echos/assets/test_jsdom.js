const fs = require('fs');
const d3 = require('d3');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;
const html = fs.readFileSync('graph.html', 'utf8');

const dom = new JSDOM(html, { runScripts: "dangerously" });
dom.window.d3 = d3;
dom.window.console.error = (msg) => console.log("ERROR:", msg);
dom.window.console.warn = (msg) => console.log("WARN:", msg);
dom.window.console.log = (msg) => console.log("LOG:", msg);

setTimeout(() => {
  try {
    const data = {
      nodes: [
        {id: 'dir1', kind: 'dir'},
        {id: 'file1', kind: 'file', dir_id: 'dir1'}
      ],
      edges: []
    };
    dom.window.loadGraph(data);
    dom.window.expandDirectory('dir1');
    console.log("expandDirectory completed without throwing.");
  } catch(e) {
    console.error("CAUGHT EXCEPTION:", e);
  }
}, 500);
