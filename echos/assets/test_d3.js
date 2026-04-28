const fs = require('fs');
const html = fs.readFileSync('graph.html', 'utf8');
const match = html.match(/function _updateEdgePaths\(\) \{[\s\S]*?\}/);
console.log("updateEdgePaths logic present:", !!match);
