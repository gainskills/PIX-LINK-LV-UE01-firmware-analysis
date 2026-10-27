const fs = require('node:fs');
const path = require('node:path');
const { minify } = require('terser');
(async () => {
  const source = '(function(){' + fs.readFileSync(path.join(__dirname,'login.js'),'utf8') + '\n' + fs.readFileSync(path.join(__dirname,'dashboard.js'),'utf8') + '\n' + fs.readFileSync(path.join(__dirname, 'settings.js'), 'utf8') + '\n}());';
  const result = await minify(source, { compress: true, mangle: true, format: { comments: false } });
  if (!result.code) throw new Error('No controller output');
  fs.writeFileSync(path.join(__dirname, 'settings.min.js'), result.code);
  console.log(`Settings controller: ${Buffer.byteLength(result.code)} bytes`);
})().catch(e => { console.error(e); process.exitCode = 1; });
