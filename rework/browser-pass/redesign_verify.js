// Verify the redesigned SC dashboard + the new Financial Reports "Trade Finance & FX"
// tab against the LIVE stack (build served locally, /api proxied to :8012, real game 10).
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = '/home/ubuntu/projects/globalstrat+/frontend/globalstrat-frontend/build';
const PORT = 4199; const BACKEND = { host: '127.0.0.1', port: 8012 };
const OUT = '/tmp/redesign'; const GAME = 10, USER = 7, TEAM = 10, SCEN = 7;
const SESSION = { user_id: USER, username: 'inst', role: 'instructor', game_id: GAME, team_id: TEAM, scenario_id: SCEN, game_name: 'G10', team_name: 'Cobalt Innovations', language: 'en' };
const MIME = { '.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.map':'application/json','.woff':'font/woff','.woff2':'font/woff2','.ttf':'font/ttf' };
const server = http.createServer((req, res) => {
  const u = req.url.split('?')[0];
  if (req.url.startsWith('/api/')) {
    if (u.startsWith('/api/auth/me')) { res.writeHead(200, {'Content-Type':'application/json'}); return res.end(JSON.stringify(SESSION)); }
    const ch=[]; req.on('data',c=>ch.push(c)); req.on('end',()=>{ const b=Buffer.concat(ch); const h={...req.headers,host:`${BACKEND.host}:${BACKEND.port}`};
      const pr=http.request({host:BACKEND.host,port:BACKEND.port,method:req.method,path:req.url,headers:h},(ps)=>{res.writeHead(ps.statusCode,ps.headers);ps.pipe(res);});
      pr.on('error',e=>{res.writeHead(502);res.end('proxy '+e.message);}); if(b.length)pr.write(b); pr.end(); });
    return;
  }
  let fp = path.join(BUILD, decodeURIComponent(u));
  if (u==='/'||!fs.existsSync(fp)||fs.statSync(fp).isDirectory()){ if(path.extname(u)){res.writeHead(404);return res.end('nf');} fp=path.join(BUILD,'index.html'); }
  res.writeHead(200,{'Content-Type':MIME[path.extname(fp)]||'application/octet-stream'}); fs.createReadStream(fp).pipe(res);
});
const sleep = ms => new Promise(r=>setTimeout(r,ms));
(async () => {
  fs.mkdirSync(OUT,{recursive:true});
  const puppeteer = require('puppeteer-core');
  await new Promise(r=>server.listen(PORT,r));
  const base = `http://localhost:${PORT}`;
  const browser = await puppeteer.launch({executablePath:'/usr/bin/chromium-browser',headless:'new',args:['--no-sandbox','--disable-dev-shm-usage']});
  const page = await browser.newPage(); await page.setViewport({width:1400,height:1500});
  const errs=[]; page.on('console',m=>{if(m.type()==='error')errs.push(m.text());}); page.on('pageerror',e=>errs.push('PAGEERROR '+e.message));
  await page.evaluateOnNewDocument((uid)=>{localStorage.setItem('gs_user',JSON.stringify({user_id:uid}));}, USER);

  // 1) Game dashboard -> Supply Chain tab
  await page.goto(base+'/', {waitUntil:'networkidle0',timeout:45000}); await sleep(2000);
  const scTab = await page.evaluate(()=>{const el=[...document.querySelectorAll('.ant-tabs-tab,[role=tab]')].find(x=>/supply chain/i.test(x.innerText)); if(el){el.click();return true;} return false;});
  await sleep(2500);
  await page.screenshot({path:OUT+'/sc_dashboard_redesigned.png',fullPage:true});
  const body = await page.evaluate(()=>document.body.innerText);
  console.log('[r] sc_tab_found', scTab);
  console.log('[r] has Your Exposure', body.includes('Your Exposure'));
  console.log('[r] has Disruptions & Alerts', body.includes('Disruptions & Alerts'));
  console.log('[r] removed Shipping Lanes in Use', !body.includes('Shipping Lanes in Use'));
  console.log('[r] removed Live Operations', !body.includes('Live Operations'));
  console.log('[r] removed TF&FX card title on SC dash', !body.includes('Trade Finance & FX'));

  // 2) Financial Reports -> Trade Finance & FX tab
  await page.goto(base+`/games/${GAME}/teams/${TEAM}/financial-reports`, {waitUntil:'networkidle0',timeout:45000}); await sleep(2000);
  const tfTab = await page.evaluate(()=>{const el=[...document.querySelectorAll('.ant-tabs-tab,[role=tab]')].find(x=>/trade finance/i.test(x.innerText)); if(el){el.click();return true;} return false;});
  await sleep(2000);
  await page.screenshot({path:OUT+'/financial_tradefinance_tab.png',fullPage:true});
  const body2 = await page.evaluate(()=>document.body.innerText);
  console.log('[r] financial tf tab found', tfTab);
  console.log('[r] tf tab shows FX hedge positions', body2.includes('Open FX hedge positions'));

  await browser.close(); await new Promise(r=>server.close(r));
  console.log('[r] consoleErrors', errs.length, errs.slice(0,3));
  console.log('[r] DONE');
})().catch(e=>{console.error('HARNESS ERR',e);process.exit(1);});
