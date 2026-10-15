// frontend/app.js — redesigned dashboard with async job polling and improved redraw
(() => {
  const state = { file: null, job_id: null, result: null, networks: { orig: null, gen: null } };

  function qs(id) { return document.getElementById(id); }

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
  const stepsEl = qs('steps');

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

    // If user opened the graphs tab, ensure vis networks redraw and fit
    if(name === 'graphs') {
      setTimeout(() => {
        try {
          if (state.networks && state.networks.orig && state.networks.orig.network) {
            state.networks.orig.network.redraw();
            state.networks.orig.network.fit();
          }
          if (state.networks && state.networks.gen && state.networks.gen.network) {
            state.networks.gen.network.redraw();
            state.networks.gen.network.fit();
          }
        } catch (e) {
          console.warn('Graph redraw failed', e);
        }
      }, 120);
    }
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
    const allowed = ['application/pdf','text/plain','text/markdown'];
    const ok = allowed.includes(file.type) || file.name.match(/\.(pdf|txt|md)$/i);
    if(!ok){ fileInfo.innerHTML = '<div class="muted">Unsupported file type</div>'; analyzeBtn.disabled = true; return; }
    if(file.size > 20 * 1024 * 1024){ fileInfo.innerHTML = '<div class="muted">File too large (max 20 MB)</div>'; analyzeBtn.disabled = true; return; }
    state.file = file;
    fileInfo.innerHTML = `<div><strong>${file.name}</strong> • ${(file.size/1024).toFixed(1)} KB</div>`;
    analyzeBtn.disabled = false;
  }

  analyzeBtn.addEventListener('click', async ()=>{
    if(!state.file) return;
    dashboard.hidden = true;
    spinner.hidden = false;
    stageText.textContent = 'Uploading file…';
    progress.hidden = false; progress.value = 5;
    stepsEl.hidden = false;

    try{
      const job = await createJob(state.file, (p)=>{ progress.value = 5 + Math.round(p*60); });
      state.job_id = job.job_id;
      stageText.textContent = 'Processing on server…';
      pollStatus(job.job_id);
    }catch(err){
      spinner.hidden = true; progress.hidden = true; stageText.textContent = 'Error: '+(err.message||err);
      alert('Analysis failed: ' + (err.message || err));
    }
  });

  function createJob(file, onProgress){
    return new Promise((resolve,reject)=>{
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/analyze');
      xhr.onload = ()=>{
        if(xhr.status >=200 && xhr.status<300){ resolve(JSON.parse(xhr.responseText)); }
        else reject(new Error(xhr.responseText||'Upload failed'));
      };
      xhr.onerror = ()=> reject(new Error('Network error'));
      xhr.upload.onprogress = (e)=>{ if(e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
      const fd = new FormData(); fd.append('file', file);
      const dis = document.getElementById('disclosing-party').value.trim();
      const rec = document.getElementById('receiving-party').value.trim();
      fd.append('disclosing_party', dis);
      fd.append('receiving_party', rec);
      fd.append('exclude_test_instructions', document.getElementById('exclude-tests').checked ? 'true' : 'false');
      xhr.send(fd);
    });
  }

  async function pollStatus(job_id){
    try{
      const res = await fetch('/status/' + job_id);
      if(!res.ok) throw new Error('Status request failed');
      const data = await res.json();
      updateProgressUI(data);
      if(data.status === 'completed'){
        state.result = data.result;
        renderDashboard(data.result);
        spinner.hidden = true; progress.hidden = true; stepsEl.hidden = true; stageText.textContent = 'Analysis complete';
        dashboard.hidden = false;
      }else if(data.status === 'failed'){
        spinner.hidden = true; progress.hidden = true; stageText.textContent = 'Analysis failed';
        alert('Analysis failed: ' + (data.error || 'unknown'));
      }else{
        setTimeout(()=> pollStatus(job_id), 1500);
      }
    }catch(err){
      spinner.hidden = true; progress.hidden = true; stageText.textContent = 'Error polling status';
      console.error(err);
    }
  }

  function updateProgressUI(job){
    stageText.textContent = `Stage: ${job.stage || 'processing'}`;
    if(typeof job.progress === 'number') progress.value = job.progress;
    document.querySelectorAll('.step').forEach(s=>{
      const stepName = s.dataset.step;
      const statusEl = s.querySelector('.step-status');
      const iconEl = s.querySelector('.step-icon');
      if(job.stage === stepName || (job.stage === 'post_simplification' && stepName==='simplification')){
        statusEl.textContent = 'In Progress...'; s.classList.add('in-progress'); s.classList.remove('completed'); iconEl.textContent = '●';
      } else if(isStageCompleted(stepName, job)){
        statusEl.textContent = 'Completed'; s.classList.add('completed'); s.classList.remove('in-progress'); iconEl.textContent = '✔';
      } else {
        statusEl.textContent = 'Pending'; s.classList.remove('completed'); s.classList.remove('in-progress'); iconEl.textContent = '○';
      }
    });
  }

  function isStageCompleted(stepName, job){
    const order = ['upload','extraction','graph_generation','constraints','simplification','verification','completed'];
    const idxJob = order.indexOf(job.stage);
    const idxStep = order.indexOf(stepName);
    return idxJob > idxStep || job.status === 'completed';
  }

  // render dashboard
  function renderDashboard(data){
    metrics.innerHTML = '';
    const filename = state.file ? state.file.name : 'Uploaded document';
    const verified = data.verification && typeof data.verification.verified !== 'undefined' ? (data.verification.verified ? 'Verified' : 'Warnings') : 'Not available';
    const mismatches = data.verification && data.verification.mismatches ? data.verification.mismatches.length : 'Not available';

    addMetric('Document', filename, '📄');
    addMetric('Verification', verified, '🔍');
    addMetric('Mismatches', mismatches, '⚠️');
    addMetric('Clauses', (data.generated_graph && data.generated_graph.nodes) ? data.generated_graph.nodes.filter(n=>n.type==='clause').length : 'Not available', '📑');

    originalText.textContent = data.original_text || '(No original text returned)';
    simplifiedText.textContent = data.simplified_text || '(No simplified text returned)';

    renderGraphData('orig', data.original_graph);
    renderGraphData('gen', data.generated_graph);

    renderMismatches(data.verification);
    renderTermsFromGraphs(data.original_graph, data.generated_graph);
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

  // terms
  function renderTermsFromGraphs(origGraph, genGraph){
    termsOriginal.innerHTML=''; termsSimplified.innerHTML='';
    const origTerms = extractTermsFromGraph(origGraph); const genTerms = extractTermsFromGraph(genGraph);
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

  // downloads
  qs('download-original').addEventListener('click', ()=>{ if(!state.result) return alert('No result'); downloadText(state.result.original_text || '', (state.file && state.file.name) ? state.file.name.replace(/\.(pdf|txt|md)$/i,'') + '-original.txt': 'original.txt'); });
  qs('download-simplified').addEventListener('click', ()=>{ if(!state.result) return alert('No result'); downloadText(state.result.simplified_text || '', 'simplified.txt'); });

  qs('export-pdf').addEventListener('click', async ()=>{
    if(!state.job_id) return alert('No analysis job available');
    const url = '/export/' + state.job_id;
    window.open(url, '_blank');
  });

  function downloadText(text, filename){ const blob = new Blob([text||''],{type:'text/plain'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=filename; a.click(); URL.revokeObjectURL(url); }
  function escapeHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

  // init: attach reset view
  document.querySelectorAll('.graph-controls button').forEach(btn => btn.addEventListener('click', ()=>{
    const g = btn.dataset.graph; const st = state.networks[g]; if(st && st.network) st.network.setOptions({physics:{stabilization:true}});
  }));

})();
