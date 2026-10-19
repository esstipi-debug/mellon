const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
  const [,, htmlPath, outDir, mode, a, b]=process.argv;
  fs.mkdirSync(outDir,{recursive:true});
  const br=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox']});
  const p=await br.newPage({viewport:{width:1920,height:1080}});
  p.on('pageerror',e=>{console.error('PAGEERR',e.message);process.exitCode=2});
  await p.goto('file://'+path.resolve(htmlPath));
  await p.waitForFunction('window.__ready===true');
  let list;
  if(mode==='range'){list=[];for(let i=+a;i<+b;i++)list.push([i,i/30,'jpg'])}
  else list=a.split(',').map(s=>[s,Number(s),'png']);
  for(const [i,t,ext] of list){
    await p.evaluate(t=>window.render(t),t);
    const name=ext==='jpg'?`f_${String(i).padStart(5,'0')}.jpg`:`still_${i}.png`;
    await p.screenshot(ext==='jpg'?{path:path.join(outDir,name),type:'jpeg',quality:92}:{path:path.join(outDir,name)});
  }
  await br.close();
})();
