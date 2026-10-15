// frontend/app.js — redesigned dashboard
(() => {
  const state = { file: null, result: null, networks: { orig: null, gen: null } };

  function qs(id) { return document.getElementById(id); }
  function qsa(selector) { return document.querySelectorAll(selector); }

  // elements
  const dropzone = qs('dropzone');
  const fileInput = qs('file');
  const browse = qs('browse');
  const fileInfo = qs('file-info');
  const analyzeBtn = qs('analyzeBtn');
  const spinner = qs('spinner');
  const stageText = qs('stage-text');
  const progress = qs('progress');
  const dashboard = qs('dashboard');
  const metrics = qs('metrics');
  const originalText = qs('original-text');
  const simplifiedText = qs('simplified-text');
  const origGraphEl = qs('orig-graph');
  const genGraphEl = qs('gen-graph');
  const mismatchList = qs('mismatch-list');
  const termsOriginal = qs('terms-original');
  const termsSimplified = qs('terms-simplified');
  const verificationContent = qs('verification-content');

  // nav
  document.querySelectorAll('.nav-btn').forEach(btn => btn.addEventListener('click', (e) => {
    document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
    e.currentTarget.classList.add('active');
    showSection(e.currentTarget.dataset.section);
  }));

  function showSection(name){
    document.querySelectorAll('.tab-pane').forEach(p => p.hidden = true);
    const el = qs(name);
    if(el) el.hidden = false;
  }
  showSection('overview');

  // drag-drop
  dropzone.addEventListener('click', ()=> fileInput.click());
  browse.addEventListener('click', (e)=>{ e.preventDefault(); fileInput.click(); });

  dropzone.addEventListener('dragover', (e)=>{ e.preventDefault(); dropzone.classList.add('drag'); });
  dropzone.addEventListener('dragleave', (e)=>{ dropzone.classList.remove('drag'); });
  dropzone.addEventListener('drop', (e)=>{
    e.preventDefault(); dropzone.classList.remove('drag');
    const f = e.dataTransfer.files[0]; handleFileSelect(f);
  });

  fileInput.addEventListener('change', (e)=> handleFileSelect(e.target.files[0]));

  function handleFileSelect(file){
    if(!file) return;
    // validate
    const allowed = ['application/pdf','text/plain','text/markdown'];
    const ok = allowed.includes(file.type) || file.name.match(/\.(pdf|txt|md)$/i);
    if(!ok){ fileInfo.innerHTML = '<div class="muted">Unsupported file type</div>'; analyzeBtn.disabled = true; return; }
    if(file.size > 8 * 1024 * 1024){ fileInfo.innerHTML = '<div class="muted">File too large (max 8 MB)</div>'; analyzeBtn.disabled = true; return; }
    state.file = file;
    fileInfo.innerHTML = `<div><strong>${file.name}</strong> • ${(file.size/1024).toFixed(1)} KB</div>`;
    analyzeBtn.disabled = false;
  }

  analyzeBtn.addEventListener('click', async ()=>{
    if(!state.file) return;
    // start UI processing
    dashboard.hidden = true;
    spinner.hidden = false;
    stageText.textContent = 'Uploading file…';
    progress.hidden = false; progress.value = 10;

    try{
      const data = await uploadFileWithProgress(state.file, (p)=>{
        progress.value = 10 + Math.round(p*60);
      });
      progress.value = 100; stageText.textContent = 'Processing complete';
      spinner.hidden = true;
      state.result = data;
      renderDashboard(data);
      dashboard.hidden = false;
      // open overview
      showSection('overview');
    }catch(err){
      spinner.hidden = true; progress.hidden = true; stageText.textContent = 'Error: '+(err.message||err);
      alert('Analysis failed: ' + (err.message || err));
    }
  });

  function uploadFileWithProgress(file, onProgress){
    return new Promise((resolve,reject)=>{
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/simplify');
      xhr.onload = ()=>{
        if(xhr.status >= 200 && xhr.status < 300){
          try{ const json = JSON.parse(xhr.responseText); resolve(json); }catch(e){ reject(e); }
        }else{ reject(new Error(xhr.responseText || 'Upload failed')); }
      };
      xhr.onerror = ()=> reject(new Error('Network error'));
      xhr.upload.onprogress = (e)=>{ if(e.lengthComputable) onProgress(e.loaded / e.total); };
      const fd = new FormData(); fd.append('file', file);
      xhr.send(fd);
    });
  }

  // render dashboard
  function renderDashboard(data){
    // metrics
    metrics.innerHTML = '';
    const filename = state.file ? state.file.name : 'Uploaded document';
    const verified = data.verification && typeof data.verification.verified !== 'undefined' ? String(data.verification.verified) : 'Not available';
    const mismatches = data.verification && data.verification.mismatches ? data.verification.mismatches.length : 'Not available';

    addMetric('Document', filename, '📄');
    addMetric('Status', data.verification && data.verification.verified ? 'Verified' : (data.verification ? 'Issues' : 'Not available'), '🔍');
    addMetric('Verified', verified, '✅');
    addMetric('Mismatches', mismatches, '⚠️');

    // texts
    originalText.textContent = data.original_text || '(No original text returned)';
    simplifiedText.textContent = data.simplified_text || '(No simplified text returned)';

    // graphs
    renderGraphData('orig', data.original_graph);
    renderGraphData('gen', data.generated_graph);

    // mismatches
    renderMismatches(data.verification);

    // terms
    renderTermsFromGraphs(data.original_graph, data.generated_graph);

    // verification content
    renderVerification(data.verification);
  }

  function addMetric(title, value, emoji){
    const el = document.createElement('div'); el.className='metric card';
    el.innerHTML = `<div style="flex:1"><div class="lbl">${title}</div><div class="num">${value}</div></div><div style="font-size:22px">${emoji}</div>`;
    metrics.appendChild(el);
  }

  // graph utilities
  function renderGraphData(kind, graphJson){
    const container = kind === 'orig' ? origGraphEl : genGraphEl;
    container.innerHTML = '';
    if(!graphJson || !graphJson.nodes || !graphJson.links){ container.innerHTML = '<div class="muted" style="padding:16px">No graph data returned</div>'; return; }

    const nodes = new vis.DataSet(graphJson.nodes.map(n=>({id:n.id,label:n.type==='clause' ? (n.text||'clause').slice(0,60) : (n.text||n.id),group:n.type||'node', data:n})));
    const edges = new vis.DataSet(graphJson.links.map(l=>({from:l.source,to:l.target,label:l.relation||'', data:l}))); 
    const network = new vis.Network(container, {nodes, edges}, {physics:{stabilization:true}, groups:{party:{color:{background:'#2ca58d'}},clause:{color:{background:'#B4C7E7'}}}});

    // node click
    network.on('click', function(params){ if(params.nodes && params.nodes.length){ const id = params.nodes[0]; const nd = nodes.get(id); showNodeDetails(nd.data||nd); } });

    state.networks[kind] = { network, nodes, edges };
  }

  function showNodeDetails(data){
    const panel = qs('node-info'); panel.hidden = false;
    const pre = qs('node-details'); pre.textContent = JSON.stringify(data, null, 2);
  }

  // mismatches
  function renderMismatches(verification){
    mismatchList.innerHTML = '';
    if(!verification){ mismatchList.innerHTML = '<div class="muted">No verification data returned.</div>'; return; }
    const ms = verification.mismatches || [];
    if(ms.length===0){ mismatchList.innerHTML = '<div class="muted">No mismatches detected.</div>'; return; }
    ms.forEach((m,i)=>{
      const div = document.createElement('div'); div.className='issue';
      div.innerHTML = `<strong>Issue ${i+1}</strong><div>${escapeHtml(m)}</div>`;
      mismatchList.appendChild(div);
    });
  }

  // terms extraction from graphs
  function renderTermsFromGraphs(origGraph, genGraph){
    termsOriginal.innerHTML=''; termsSimplified.innerHTML='';
    const origTerms = extractTermsFromGraph(origGraph); const genTerms = extractTermsFromGraph(genGraph);
    const preserved = origTerms.filter(t=> genTerms.includes(t));
    const missing = origTerms.filter(t=> !genTerms.includes(t));
    const added = genTerms.filter(t=> !origTerms.includes(t));

    origTerms.forEach(t => { const el = document.createElement('div'); el.className='chip'; el.textContent = t; termsOriginal.appendChild(el); });
    genTerms.forEach(t => { const el = document.createElement('div'); el.className='chip'; el.textContent = t; termsSimplified.appendChild(el); });
  }

  function extractTermsFromGraph(graphJson){
    if(!graphJson || !graphJson.nodes) return [];
    const out = [];
    graphJson.nodes.forEach(n=>{ if(n.type && ['party','obligation','amount','deadline'].includes(n.type) && n.text){ out.push(n.text); } });
    return Array.from(new Set(out));
  }

  function renderVerification(verification){
    verificationContent.innerHTML = '';
    if(!verification){ verificationContent.innerHTML = '<div class="muted">Verification data not provided by backend.</div>'; return; }
    const pre = document.createElement('pre'); pre.textContent = JSON.stringify(verification, null, 2); verificationContent.appendChild(pre);
  }

  // download handlers
  qs('download-original').addEventListener('click', ()=>{ if(!state.result) return alert('No result'); downloadText(state.result.original_text || '', (state.file && state.file.name) ? state.file.name.replace(/\.(pdf|txt|md)$/i,'') + '-original.txt': 'original.txt'); });
  qs('download-simplified').addEventListener('click', ()=>{ if(!state.result) return alert('No result'); downloadText(state.result.simplified_text || '', 'simplified.txt'); });
  qs('open-comparison').addEventListener('click', ()=>{ document.querySelector('.nav-btn[data-section="comparison"]').click(); });

  function downloadText(text, filename){ const blob = new Blob([text||''],{type:'text/plain'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=filename; a.click(); URL.revokeObjectURL(url); }

  function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // init
  // attach reset view
  document.querySelectorAll('.graph-controls button').forEach(btn => btn.addEventListener('click', ()=>{
    const g = btn.dataset.graph; const st = state.networks[g]; if(st && st.network) st.network.setOptions({physics:{stabilization:true}});
  }));

})();
