const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
  const [,, htmlPath, outDir, times]=process.argv;
  fs.mkdirSync(outDir,{recursive:true});
  const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox']});
  const p=await b.newPage({viewport:{width:1920,height:1080}});
  await p.goto('file://'+path.resolve(htmlPath));
  await p.waitForFunction('window.__ready===true');
  const list=times.includes(':')?(()=>{const [fps,dur]=times.split(':').map(Number);return Array.from({length:Math.round(fps*dur)},(_,i)=>[i,i/fps])})():times.split(',').map(s=>[s,Number(s)]);
  for(const [i,t] of list){
    await p.evaluate(t=>window.render(t),t);
    const name=typeof i==='number'?`f_${String(i).padStart(4,'0')}.png`:`still_${i}.png`;
    await p.screenshot({path:path.join(outDir,name)});
  }
  await b.close();
})();
