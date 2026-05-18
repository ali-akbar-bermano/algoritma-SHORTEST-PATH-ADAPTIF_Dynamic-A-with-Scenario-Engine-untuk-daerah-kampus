// ── State ──────────────────────────────────────────────────
let graph=null, mapMode=null, addEdgeFrom=null, routeLayer=null;
let edgeLayers={}, nodeLayers={}, conditions={}, nodeById={}, edgeById={};
let isDrawing=false, drawEdgeId=null, drawPoints=[], drawPolyline=null;
let drawTempLine=null, drawDots=[], drawSnapLine=null;
let pickRouteFrom=null; // for pick_route mode

// ── Map ────────────────────────────────────────────────────
const map = L.map('map',{doubleClickZoom:false}).setView([-3.7590,102.2725],16);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
  attribution:'© OpenStreetMap', maxZoom:19
}).addTo(map);

map.on('click', async e=>{
  if(isDrawing){addDrawPoint(e.latlng);return;}
  // Add node (building)
  if(mapMode==='add_node'){
    const name=prompt('Masukkan nama gedung baru:');
    if(!name)return;
    setStepIndicator('⏳ Menambahkan gedung…');
    try{
      const r=await fetch('/api/nodes',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name,lat:e.latlng.lat,lon:e.latlng.lng,type:'Gedung'})});
      const d=await r.json();
      if(d.ok){
        if(d.connected){
          showAlert(`Gedung "${name}" (${d.id}) ditambahkan & tersambung ke jalan ${d.split_edge}! 🎉`,'success');
        } else {
          showAlert(`Gedung "${name}" (${d.id}) ditambahkan. Tidak ada jalan terdekat — tambahkan jalan manual dengan 🔗 Tambah Jalan.`,'info');
        }
        await loadGraph();
        setStepIndicator('🏢 Klik peta untuk tambah gedung lain');
      } else {
        showAlert(d.error||'Gagal menambah gedung','error');
        setStepIndicator('🏢 Klik peta untuk tambah Gedung');
      }
    }catch(err){showAlert('Gagal menambah gedung: '+err.message,'error');setStepIndicator('🏢 Klik peta untuk tambah Gedung');}
    return;
  }
  // Add edge from map click — auto-create waypoint
  if(mapMode==='add_edge'){
    const lat=e.latlng.lat, lon=e.latlng.lng;
    // Check if near an existing node (snap threshold ~30m)
    let nearNode=null, nearDist=Infinity;
    for(const n of graph.nodes){
      const d=map.latLngToLayerPoint([n.lat,n.lon]).distanceTo(map.latLngToLayerPoint(e.latlng));
      if(d<25 && d<nearDist){nearDist=d;nearNode=n;}
    }
    if(nearNode){
      handleAddEdgeNode(nearNode.id, nearNode.name);
    } else {
      setStepIndicator('⏳ Menyambungkan titik ke jalan terdekat…');
      try{
        const d=await createRoadPoint(lat,lon);
        if(d.ok){
          await loadGraph();
          handleAddEdgeNode(d.id, d.node?.name||d.id);
          if(d.snapped)showAlert(`Titik jalan tersambung ke ${d.split_edge}`,'success');
        }else showAlert(d.error||'Gagal membuat titik jalan','error');
      }catch{showAlert('Gagal membuat titik jalan','error');}
    }
    return;
  }
});
map.on('dblclick',e=>{if(isDrawing){L.DomEvent.stopPropagation(e);finishDraw();}});
map.on('contextmenu',e=>{
  // Right-click cancels chain mode
  if(mapMode==='add_edge'&&addEdgeFrom){
    L.DomEvent.preventDefault(e);
    addEdgeFrom=null;
    setStepIndicator('📍 Klik titik pertama (gedung, ruas jalan, atau peta)');
    showAlert('Chain dibatalkan','info');
  }
});
map.on('mousemove',e=>{
  if(!isDrawing||drawPoints.length===0)return;
  if(drawTempLine)map.removeLayer(drawTempLine);
  drawTempLine=L.polyline([drawPoints[drawPoints.length-1],e.latlng],
    {color:'#f59e0b',weight:2.5,dashArray:'8,6',opacity:.8}).addTo(map);
});

// ── Clock ──────────────────────────────────────────────────
function updateClock(){
  document.getElementById('clock').textContent=
    new Date().toLocaleTimeString('id-ID',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
updateClock();setInterval(updateClock,1000);

// ── Tabs ───────────────────────────────────────────────────
function showTab(name,btn){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='jalan')refreshCondTable();
  if(name==='skenario')renderScenarioCards();
}

// ── Alert ──────────────────────────────────────────────────
function showAlert(msg,type='info'){
  const el=document.getElementById('alert');
  el.className='alert-'+type; el.textContent=msg; el.style.display='block';
  if(type!=='error')setTimeout(()=>el.style.display='none',4000);
}

// ── Icons ──────────────────────────────────────────────────
function nodeIcon(type,isStart,isEnd){
  // Waypoint: invisible (no marker)
  if(type==='Waypoint' && !isStart && !isEnd){
    return L.divIcon({
      html:`<div style="width:6px;height:6px;border-radius:50%;background:rgba(148,163,184,0.4)"></div>`,
      className:'',iconSize:[6,6],iconAnchor:[3,3]
    });
  }
  let bg='#1e40af',emoji='🏢';
  if(type==='Gerbang'){bg='#d97706';emoji='🚪';}
  if(type==='Fasilitas'){bg='#0d9488';emoji='⚙';}
  if(type==='Area terbuka'){bg='#059669';emoji='🌿';}
  if(type==='Parkir'){bg='#6366f1';emoji='P';}
  if(isStart){bg='#f59e0b';emoji='🟢';}
  if(isEnd){bg='#ef4444';emoji='🔴';}
  return L.divIcon({
    html:`<div style="background:${bg};width:28px;height:28px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;font-size:13px;
      border:2px solid rgba(255,255,255,.4);box-shadow:0 2px 8px rgba(0,0,0,.4)">${emoji}</div>`,
    className:'',iconSize:[28,28],iconAnchor:[14,14]
  });
}

function edgeColor(id){
  const ec=(conditions.edge_conditions||{})[id];
  if(ec){
    const s=(ec.status||ec.type||'NORMAL').toUpperCase();
    if(s==='CLOSED')return'#ef4444';
    if(s==='BUSY')return'#f59e0b';
    if(s==='POTHOLE')return'#f97316';
    if(s==='CUSTOM')return'#60a5fa';
    if(s==='CONSTRUCTION')return'#a855f7';
  }
  // Check scenario modifiers
  const selSc=document.getElementById('sel-scenario');
  if(selSc&&graph){
    const sc=graph.scenarios.find(s=>s.id===selSc.value);
    if(sc){
      if((sc.blocked_edges||[]).includes(id))return'#ef4444';
      if(sc.edge_modifiers&&sc.edge_modifiers[id])return sc.color||'#d97706';
    }
  }
  return'#38bdf8';
}

// ── Load Graph ─────────────────────────────────────────────
async function loadGraph(){
  try{
    const[gR,cR]=await Promise.all([fetch('/api/graph'),fetch('/api/conditions')]);
    graph=await gR.json(); conditions=await cR.json();
    nodeById={};edgeById={};
    graph.nodes.forEach(n=>nodeById[n.id]=n);
    graph.edges.forEach(e=>edgeById[e.id]=e);
    populateSelects(); populateScenarios(); drawEdges(); drawNodes();
    updateScenarioInfo(); renderScenarioCards();
  }catch(e){console.error('Load failed:',e);}
}

function populateSelects(){
  const s=document.getElementById('sel-start'),e=document.getElementById('sel-end');
  const prevStart=s.value||'G1',prevEnd=e.value||'RK';
  const buildings=graph.nodes.filter(n=>n.type!=='Waypoint'&&!n.name.startsWith('WP_'));
  [s,e].forEach(sel=>{
    sel.innerHTML='';
    buildings.forEach(n=>{const o=document.createElement('option');o.value=n.id;o.textContent=`${n.id} – ${n.name}`;sel.appendChild(o);});
  });
  const buildingIds=new Set(buildings.map(n=>n.id));
  s.value=buildingIds.has(prevStart)?prevStart:(buildingIds.has('G1')?'G1':buildings[0]?.id||'');
  e.value=buildingIds.has(prevEnd)?prevEnd:(buildingIds.has('RK')?'RK':buildings[1]?.id||buildings[0]?.id||'');
}

function populateScenarios(){
  const sel=document.getElementById('sel-scenario');
  const prevScenario=sel.value||'Normal';
  sel.innerHTML='';
  graph.scenarios.forEach(sc=>{const o=document.createElement('option');o.value=sc.id;o.textContent=sc.id;sel.appendChild(o);});
  if(graph.scenarios.some(sc=>sc.id===prevScenario))sel.value=prevScenario;
}

function updateScenarioInfo(){
  const sel=document.getElementById('sel-scenario');
  const info=document.getElementById('scenario-info');
  if(!info||!graph)return;
  const sc=graph.scenarios.find(s=>s.id===sel.value);
  info.querySelector('.si-desc').textContent=sc?sc.description:'—';
  // Show affected edges
  const affDiv=document.getElementById('si-affected');
  const affList=document.getElementById('si-affected-list');
  if(!affDiv||!affList)return;
  const mods=sc?.edge_modifiers||{};
  const blocked=sc?.blocked_edges||[];
  if(Object.keys(mods).length===0&&blocked.length===0){
    affDiv.style.display='none'; return;
  }
  affDiv.style.display='block';
  let html='';
  for(const[eid,mul]of Object.entries(mods)){
    const e=edgeById[eid];
    const label=e?`${eid} (${nodeById[e.from]?.name?.substring(0,12)||e.from} → ${nodeById[e.to]?.name?.substring(0,12)||e.to})`:eid;
    html+=`<span class="si-tag si-tag-mod">×${mul} ${label}</span> `;
  }
  for(const eid of blocked){
    html+=`<span class="si-tag si-tag-block">🚫 ${eid}</span> `;
  }
  affList.innerHTML=html;
  // Redraw edges with scenario colors
  if(graph)drawEdges();
}

function drawEdges(){
  Object.values(edgeLayers).forEach(l=>map.removeLayer(l));
  edgeLayers={};
  const selSc=document.getElementById('sel-scenario');
  const sc=graph.scenarios.find(s=>s.id===(selSc?selSc.value:'Normal'));
  const mods=sc?.edge_modifiers||{};
  const blocked=sc?.blocked_edges||[];
  graph.edges.forEach(e=>{
    const ll=e.geometry.map(p=>[p[0],p[1]]);
    const isAuto=e.source==='auto';
    const c=isAuto && edgeColor(e.id)==='#38bdf8'?'#94a3b8':edgeColor(e.id);
    const isBlocked=blocked.includes(e.id);
    const isMod=!!mods[e.id];
    const w=isBlocked?5:(isMod?4.5:(isAuto?2.5:3.5));
    const op=isBlocked?0.35:(isMod?0.75:(isAuto?0.45:0.55));
    const dash=isBlocked?'8,6':(isAuto?'4,6':null);
    const opts={color:c,weight:w,opacity:op,smoothFactor:.5};
    if(dash)opts.dashArray=dash;
    const line=L.polyline(ll,opts).addTo(map);
    // Invisible wider click target for easier clicking
    const hitLine=L.polyline(ll,{color:'#000',weight:18,opacity:0.001,interactive:true,smoothFactor:.5}).addTo(map);
    const ttMod=isMod?` ⚠×${mods[e.id]}`:'';
    const ttBlock=isBlocked?' 🚫DITUTUP':'';
    const ttAuto=isAuto?' · koneksi otomatis':'';
    const handleClick=()=>onEdgeClick(e);
    line.on('click',handleClick);
    hitLine.on('click',handleClick);
    hitLine.on('mouseover',()=>{if(!mapMode||mapMode==='edit_road')line.setStyle({weight:8,opacity:1});});
    hitLine.on('mouseout',()=>line.setStyle({weight:w,opacity:op}));
    line.on('mouseover',()=>{if(!mapMode||mapMode==='edit_road')line.setStyle({weight:8,opacity:1});});
    line.on('mouseout',()=>line.setStyle({weight:w,opacity:op}));
    hitLine.bindTooltip(`${e.id}: ${e.from} → ${e.to}${ttMod}${ttBlock}${ttAuto}`,{sticky:true});
    line.bindTooltip(`${e.id}: ${e.from} → ${e.to}${ttMod}${ttBlock}${ttAuto}`,{sticky:true});
    edgeLayers[e.id]=line;
    edgeLayers[e.id+'_hit']=hitLine;
  });
}

function drawNodes(){
  Object.values(nodeLayers).forEach(l=>map.removeLayer(l));
  nodeLayers={};
  const start=document.getElementById('sel-start').value;
  const end=document.getElementById('sel-end').value;
  graph.nodes.forEach(n=>{
    // Skip waypoint nodes (WP_ prefix) — routing only, not displayed
    if(n.name && n.name.startsWith('WP_')) return;
    const m=L.marker([n.lat,n.lon],{icon:nodeIcon(n.type,n.id===start,n.id===end)}).addTo(map);
    const isCustom=n.id.startsWith('C');
    const deleteBtn=isCustom?`<button onclick="deleteNode('${n.id}')" style="margin-top:6px;padding:3px 10px;background:#ef4444;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:11px">🗑 Hapus</button>`:'';
    const moveBtn=`<button onclick="enableNodeDrag('${n.id}')" style="margin-top:6px;padding:3px 10px;background:#38bdf8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:11px;margin-right:4px">📍 Pindah Lokasi</button>`;
    m.bindPopup(`<b style="color:#5eead4">${n.id}</b><br>${n.name}<br><small style="color:#7fb4ab">${n.type}</small><br>${moveBtn}${deleteBtn}`);
    m.on('click',async()=>{
      // ── Pick Route mode ──
      if(mapMode==='pick_route'){
        if(!pickRouteFrom){
          pickRouteFrom=n.id;
          document.getElementById('sel-start').value=n.id;
          drawNodes();
          setStepIndicator(`🟢 ${n.name} — klik gedung tujuan`);
          showAlert(`Awal: ${n.name}. Klik gedung tujuan.`,'info');
        }else{
          if(pickRouteFrom!==n.id){
            document.getElementById('sel-end').value=n.id;
            drawNodes();
            setStepIndicator('⏳ Menghitung rute…');
            document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
            document.getElementById('tab-route').classList.add('active');
            document.querySelectorAll('.tab-btn')[0].classList.add('active');
            await findRoute();
            setStepIndicator('✅ Rute ditemukan — klik gedung untuk rute baru');
          }
          pickRouteFrom=null;
        }
        return;
      }
      // ── Add Edge mode ──
      if(mapMode==='add_edge'){
        handleAddEdgeNode(n.id, n.name);
        return;
      }
    });
    nodeLayers[n.id]=m;
  });
}

function enableNodeDrag(id){
  const m=nodeLayers[id];
  if(!m)return;
  m.closePopup();
  m.dragging.enable();
  showAlert('Geser ikon gedung/titik ke lokasi baru, lalu lepaskan untuk menyimpan.','info');
  m.once('dragend', async function(e){
    m.dragging.disable();
    const pos = m.getLatLng();
    if(confirm('Simpan lokasi baru untuk titik ini?')){
      setStepIndicator('⏳ Menyimpan lokasi baru...');
      try {
        const r = await fetch(`/api/nodes/${id}/location`, {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({lat: pos.lat, lon: pos.lng})
        });
        const d = await r.json();
        if(d.ok) {
          showAlert(`Lokasi titik ${id} berhasil diperbarui.`,'success');
        } else {
          showAlert(d.error || 'Gagal mengubah lokasi', 'error');
        }
      } catch(err) {
        showAlert('Error: '+err.message, 'error');
      }
    }
    // Refresh to update edge geometries properly
    await loadGraph();
    setStepIndicator('');
  });
}

// Handle adding edge from a node (building or waypoint)
// Chain mode: after creating A→B, auto-continue from B
async function handleAddEdgeNode(nodeId, nodeName){
  if(!addEdgeFrom){
    addEdgeFrom=nodeId;
    setStepIndicator(`✅ ${nodeName} — klik titik kedua`);
    showAlert(`Klik titik tujuan dari ${nodeName}`,'info');
  }else{
    if(addEdgeFrom!==nodeId){
      setStepIndicator('⏳ Membuat jalan…');
      try{
        const r=await fetch('/api/edges',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({from:addEdgeFrom,to:nodeId})});
        const d=await r.json();
        if(d.ok){
          showAlert('Jalan ditambahkan! Lanjut dari titik ini…','success');
          await loadGraph();
          // Chain: continue from last node
          addEdgeFrom=nodeId;
          setStepIndicator(`🔗 ${nodeName} — klik titik berikutnya (atau klik kanan batal)`);
          return;
        }
      }catch{showAlert('Gagal menambah jalan','error');}
    }
    addEdgeFrom=null;
    setStepIndicator('📍 Klik titik pertama (gedung, ruas jalan, atau peta)');
  }
}

function setStepIndicator(t){const el=document.getElementById('edge-step-indicator');if(el)el.querySelector('.esi-text').textContent=t;}

async function createRoadPoint(lat,lon){
  const wpName=`WP_${Date.now().toString(36)}`;
  const r=await fetch('/api/road-points',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:wpName,lat,lon})});
  return await r.json();
}

// ── Map Mode ───────────────────────────────────────────────
function setMapMode(mode){
  if(isDrawing)cancelDraw();
  closeEdgeEditor();
  mapMode=(mapMode===mode)?null:mode;
  document.querySelectorAll('.map-tool-btn').forEach(b=>b.classList.remove('active'));
  if(mapMode){
    const btnId='btn-'+mode.replace(/_/g,'-');
    const btn=document.getElementById(btnId);
    if(btn)btn.classList.add('active');
  }
  map.getContainer().style.cursor=mapMode?'crosshair':'';
  addEdgeFrom=null;
  pickRouteFrom=null;
  const ind=document.getElementById('edge-step-indicator');
  if(mapMode==='pick_route'){
    ind&&ind.classList.add('visible');
    setStepIndicator('🟢 Klik gedung awal di peta');
    showAlert('Klik gedung pertama sebagai titik awal','info');
  } else if(mapMode==='edit_road'){
    ind&&ind.classList.add('visible');
    setStepIndicator('✏ Klik garis jalan mana saja untuk edit bobot & arah');
    showAlert('Klik ruas jalan di peta atau baris pada tabel Jalan','info');
  } else if(mapMode==='add_edge'){
    ind&&ind.classList.add('visible');
    setStepIndicator('📍 Klik titik pertama (gedung, ruas jalan, atau peta)');
    showAlert('Klik gedung, ruas jalan, atau titik mana saja di peta','info');
  } else if(mapMode==='add_node'){
    ind&&ind.classList.add('visible');
    setStepIndicator('🏢 Klik peta untuk tambah Gedung');
    showAlert('Klik lokasi gedung baru di peta','info');
  } else {
    ind&&ind.classList.remove('visible');
  }
}

// ── Edge Editor Panel ─────────────────────────────────────
let editingEdgeId=null;
function onEdgeClick(edge){
  // Block only when actively placing nodes/edges or picking route
  if(mapMode==='add_edge'||mapMode==='add_node'||mapMode==='pick_route')return;
  openEdgeEditor(edge);
}

function openEdgeEditor(edge){
  editingEdgeId=edge.id;
  const ec=(conditions.edge_conditions||{})[edge.id];
  const cur=ec?(ec.status||ec.type||'NORMAL'):'NORMAL';
  const sev=ec?.severity??1.0;
  const isBidir=edge.bidirectional!==false; // default true
  const fromName=(nodeById[edge.from]?.name||edge.from).substring(0,22);
  const toName=(nodeById[edge.to]?.name||edge.to).substring(0,22);
  const panel=document.getElementById('edge-editor');

  // Build node options for direction selectors (only non-waypoint nodes)
  const buildingNodes=graph.nodes.filter(n=>n.type!=='Waypoint');
  const optFrom=buildingNodes.map(n=>`<option value="${n.id}" ${n.id===edge.from?'selected':''}>${n.id} – ${n.name.substring(0,18)}</option>`).join('');
  const optTo  =buildingNodes.map(n=>`<option value="${n.id}" ${n.id===edge.to  ?'selected':''}>${n.id} – ${n.name.substring(0,18)}</option>`).join('');

  panel.innerHTML=`
    <div class="ee-header">
      <h4 style="font-size:12px">${edge.id}: ${fromName} → ${toName}</h4>
      <button class="ee-close" onclick="closeEdgeEditor()">✕</button>
    </div>
    <div class="ee-meta">Jarak: <b>${edge.distance}m</b> · Status: <b>${cur}</b>${sev!==1?' (×'+sev+')':''}</div>

    <div class="ee-section">
      <label>Kondisi Jalan</label>
      <div class="cond-btns">
        <button class="cond-btn cb-normal ${cur==='NORMAL'?'active':''}" onclick="setCondition('${edge.id}','NORMAL')">✅ Normal</button>
        <button class="cond-btn cb-busy ${cur==='BUSY'?'active':''}" onclick="setCondition('${edge.id}','BUSY')">🚦 Sibuk</button>
        <button class="cond-btn cb-pothole ${cur==='POTHOLE'?'active':''}" onclick="setCondition('${edge.id}','POTHOLE')">⚠ Berlubang</button>
        <button class="cond-btn cb-closed ${cur==='CLOSED'?'active':''}" onclick="setCondition('${edge.id}','CLOSED')">🚫 Ditutup</button>
      </div>
    </div>

    <div class="ee-section">
      <label>⚖ Bobot Kustom (×multiplier)</label>
      <div class="ee-slider-row">
        <input type="range" id="ee-weight" min="0.5" max="5" step="0.1" value="${sev}"
          oninput="document.getElementById('ee-wval').textContent=parseFloat(this.value).toFixed(1)">
        <span id="ee-wval" class="ee-wval">${parseFloat(sev).toFixed(1)}</span>
        <button class="ep-btn" style="background:var(--teal);color:#fff"
          onclick="setCondition('${edge.id}','CUSTOM',document.getElementById('ee-weight').value)">Simpan</button>
      </div>
      <div style="font-size:10px;color:var(--text-muted);margin-top:3px">Masukkan nilai bebas (0.5 – 5). Atau ketik langsung:
        <div class="ep-row" style="margin-top:4px">
          <input type="number" id="ee-weight-num" min="0.1" max="99" step="0.1" value="${sev}" placeholder="Bobot bebas">
          <button class="ep-btn" style="background:var(--teal);color:#fff"
            onclick="setCondition('${edge.id}','CUSTOM',document.getElementById('ee-weight-num').value)">Simpan</button>
        </div>
      </div>
    </div>

    <div class="ee-section">
      <label>📏 Panjang Jalan (meter)</label>
      <div class="ep-row">
        <input type="number" id="ee-dist" value="${edge.distance}" step="0.1" min="0.1">
        <button class="ep-btn" style="background:var(--amber);color:#fff"
          onclick="updateEdgeDist('${edge.id}',document.getElementById('ee-dist').value)">Simpan</button>
      </div>
      <button class="draw-road-btn" onclick="startDraw('${edge.id}')">✏️ Gambar Jalur di Peta</button>
    </div>

    <div class="ee-section">
      <label>🔀 Arah Jalur</label>
      <div class="ee-dir-row">
        <button id="ee-dir-bi" class="cond-btn ${isBidir?'cb-normal active':'cb-busy'}"
          onclick="setEdgeDir('${edge.id}',true)">⇄ Dua Arah</button>
        <button id="ee-dir-one" class="cond-btn ${!isBidir?'cb-busy active':'cb-normal'}"
          onclick="setEdgeDir('${edge.id}',false)">→ Satu Arah</button>
      </div>
      <div id="ee-dir-detail" style="margin-top:6px;${isBidir?'display:none':''}">
        <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">Pilih arah jalan:</div>
        <select id="ee-dir-from" style="font-size:11px;padding:5px 8px;margin-bottom:4px">${optFrom}</select>
        <div style="text-align:center;color:var(--teal-light);font-size:16px;margin:2px 0">↓</div>
        <select id="ee-dir-to" style="font-size:11px;padding:5px 8px">${optTo}</select>
        <button class="ep-btn" style="background:var(--amber);color:#fff;width:100%;margin-top:6px"
          onclick="updateEdgeDirection('${edge.id}',false,document.getElementById('ee-dir-from').value,document.getElementById('ee-dir-to').value)">💾 Simpan Arah</button>
      </div>
    </div>

    <div class="ee-section" style="text-align:right">
      <button class="cond-btn cb-closed" style="width:100%" onclick="deleteEdge('${edge.id}')">🗑 Hapus Jalan</button>
    </div>
  `;
  panel.classList.add('visible');
  // Highlight the edge
  if(edgeLayers[edge.id])edgeLayers[edge.id].setStyle({weight:8,opacity:1});
}

function setEdgeDir(edgeId, bidir){
  const detail=document.getElementById('ee-dir-detail');
  const btnBi=document.getElementById('ee-dir-bi');
  const btnOne=document.getElementById('ee-dir-one');
  if(bidir){
    detail.style.display='none';
    btnBi.className='cond-btn cb-normal active';
    btnOne.className='cond-btn cb-busy';
    // Immediately save bidirectional
    updateEdgeDirection(edgeId,true,null,null);
  }else{
    detail.style.display='block';
    btnBi.className='cond-btn cb-normal';
    btnOne.className='cond-btn cb-busy active';
  }
}

async function updateEdgeDirection(edgeId, bidir, fromNode, toNode){
  try{
    const body={bidirectional:bidir};
    if(fromNode)body.from=fromNode;
    if(toNode)body.to=toNode;
    const r=await fetch(`/api/edges/${edgeId}/direction`,{
      method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    if(d.ok){
      const label=bidir?'Dua Arah':'Satu Arah';
      showAlert(`${edgeId} → ${label}${fromNode?` (${fromNode}→${toNode})`:''}`, 'success');
      await loadGraph();
      // Reopen editor with refreshed data
      const refreshed=edgeById[edgeId];
      if(refreshed&&editingEdgeId===edgeId)openEdgeEditor(refreshed);
    }else showAlert(d.error||'Gagal mengubah arah','error');
  }catch(e){showAlert('Error: '+e.message,'error');}
}

function closeEdgeEditor(){
  const panel=document.getElementById('edge-editor');
  if(panel)panel.classList.remove('visible');
  // Reset edge highlight
  if(editingEdgeId&&edgeLayers[editingEdgeId]){
    const sc=graph?.scenarios?.find(s=>s.id===document.getElementById('sel-scenario')?.value);
    const mods=sc?.edge_modifiers||{};
    const blocked=sc?.blocked_edges||[];
    const isMod=!!mods[editingEdgeId];
    const isBlocked=blocked.includes(editingEdgeId);
    const w=isBlocked?5:(isMod?4.5:3.5);
    const op=isBlocked?0.35:(isMod?0.75:0.55);
    edgeLayers[editingEdgeId].setStyle({weight:w,opacity:op});
  }
  editingEdgeId=null;
}

// ── Conditions API ─────────────────────────────────────────
async function setCondition(id,status,cs=null){
  let sev={NORMAL:1,BUSY:2,POTHOLE:1.6,CLOSED:999}[status]||1;
  if(status==='CUSTOM'&&cs!==null)sev=parseFloat(cs);
  const r=await fetch('/api/conditions',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({edge_id:id,status,severity:sev})});
  const d=await r.json(); conditions=d.conditions;
  if(edgeLayers[id])edgeLayers[id].setStyle({color:edgeColor(id)});
  showAlert(`${id} → ${status} (×${sev})`,'success'); refreshCondTable();
  // Refresh editor if open
  if(editingEdgeId===id && edgeById[id])openEdgeEditor(edgeById[id]);
}

async function updateEdgeDist(id,nd){
  const d=parseFloat(nd);
  if(isNaN(d)||d<=0){showAlert('Jarak harus positif','error');return;}
  try{
    const r=await fetch(`/api/edges/${id}/distance`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({distance:d})});
    const res=await r.json();
    if(res.ok){if(edgeById[id])edgeById[id].distance=d;const eg=graph.edges.find(e=>e.id===id);if(eg)eg.distance=d;showAlert(`${id} → ${d}m`,'success');refreshCondTable();
      if(editingEdgeId===id && edgeById[id])openEdgeEditor(edgeById[id]);
    }
    else showAlert(res.error||'Gagal','error');
  }catch(e){showAlert('Error: '+e.message,'error');}
}

async function deleteEdge(id){
  if(!confirm(`Hapus jalan ${id}?`))return; closeEdgeEditor();
  try{const r=await fetch(`/api/edges/${id}`,{method:'DELETE'});const d=await r.json();if(d.ok){showAlert(`${id} dihapus!`,'success');loadGraph();}}
  catch{showAlert('Gagal menghapus','error');}
}

async function deleteNode(id){
  const node=graph.nodes.find(n=>n.id===id);
  const isWP=node&&node.type==='Waypoint';
  const msg=isWP
    ?`Hapus waypoint ${id}? Jalan akan digabungkan otomatis.`
    :`Hapus gedung ${node?.name||id}? Semua jalan terhubung juga akan dihapus.`;
  if(!confirm(msg))return;
  map.closePopup();
  try{
    const r=await fetch(`/api/nodes/${id}`,{method:'DELETE'});
    const d=await r.json();
    if(d.ok){showAlert(isWP?`Waypoint ${id} dihapus, jalan digabung!`:`${id} dihapus!`,'success');loadGraph();}
    else showAlert(d.error||'Gagal menghapus','error');
  }catch{showAlert('Gagal menghapus node','error');}
}

// ── Draw Road ──────────────────────────────────────────────
function _calcDD(){let t=0;for(let i=1;i<drawPoints.length;i++)t+=drawPoints[i-1].distanceTo(drawPoints[i]);return Math.round(t*10)/10;}

function _updateDP(){
  const d=_calcDD(),n=drawPoints.length;
  document.getElementById('drp-dist-val').textContent=d.toFixed(1);
  const sub=document.getElementById('drp-subtitle');
  sub.textContent=n===0?'Klik pada peta mengikuti jalur jalan':n===1?'1 titik — lanjutkan klik':`${n} titik — double-klik atau ✓ Terapkan`;
  const ab=document.getElementById('drp-apply');ab.disabled=n<2;ab.style.opacity=n<2?'.4':'1';
  const ub=document.getElementById('drp-undo');ub.disabled=n===0;ub.style.opacity=n===0?'.4':'1';
}

function startDraw(id){
  closeEdgeEditor(); drawPoints=[]; drawEdgeId=id; isDrawing=true;
  [drawPolyline,drawTempLine,drawSnapLine].forEach(l=>{if(l)map.removeLayer(l);});
  drawPolyline=drawTempLine=drawSnapLine=null; drawDots.forEach(d=>map.removeLayer(d)); drawDots=[];
  if(edgeLayers[id]){
    drawSnapLine=L.polyline(edgeLayers[id].getLatLngs(),{color:'#f59e0b',weight:6,opacity:.35,dashArray:'12,8'}).addTo(map);
    map.fitBounds(edgeLayers[id].getBounds(),{padding:[60,60],maxZoom:18});
  }
  document.getElementById('draw-road-panel').classList.add('visible');
  document.getElementById('drp-edge-id').textContent=id;
  map.getContainer().classList.add('map-drawing-cursor'); _updateDP();
}

function addDrawPoint(ll){
  drawPoints.push(ll);
  const dot=L.circleMarker(ll,{radius:6,color:'#f59e0b',fillColor:'#fbbf24',fillOpacity:1,weight:2.5}).addTo(map);
  dot.bindTooltip(`${drawPoints.length}`,{permanent:true,direction:'top',className:'measure-label',offset:[0,-10]});
  drawDots.push(dot);
  if(drawPolyline)map.removeLayer(drawPolyline);
  if(drawPoints.length>1)drawPolyline=L.polyline(drawPoints,{color:'#f59e0b',weight:4,opacity:.95}).addTo(map);
  _updateDP();
}

function undoDraw(){
  if(!drawPoints.length)return; drawPoints.pop();
  const d=drawDots.pop();if(d)map.removeLayer(d);
  if(drawPolyline){map.removeLayer(drawPolyline);drawPolyline=null;}
  if(drawTempLine){map.removeLayer(drawTempLine);drawTempLine=null;}
  if(drawPoints.length>1)drawPolyline=L.polyline(drawPoints,{color:'#f59e0b',weight:4,opacity:.95}).addTo(map);
  _updateDP();
}

function finishDraw(){
  if(drawPoints.length<2){showAlert('Min 2 titik','error');return;}
  const d=_calcDD(),tid=drawEdgeId; cancelDraw(true);
  if(tid&&confirm(`Jarak: ${d}m\nTerapkan ke ${tid}?`))updateEdgeDist(tid,d);
  else showAlert(`Jarak: ${d}m (tidak diterapkan)`,'info');
}

function cancelDraw(keepId=false){
  isDrawing=false; if(!keepId)drawEdgeId=null;
  [drawPolyline,drawTempLine,drawSnapLine].forEach(l=>{if(l)map.removeLayer(l);});
  drawPolyline=drawTempLine=drawSnapLine=null;
  drawDots.forEach(d=>map.removeLayer(d)); drawDots=[]; drawPoints=[];
  document.getElementById('draw-road-panel').classList.remove('visible');
  map.getContainer().classList.remove('map-drawing-cursor');
  map.getContainer().style.cursor=mapMode?'crosshair':'';
}

// ── Find Route (with loading + animation) ──────────────────
async function findRoute(){
  const start=document.getElementById('sel-start').value;
  const end=document.getElementById('sel-end').value;
  const scen=document.getElementById('sel-scenario').value;
  const tfac=parseFloat(document.getElementById('time-factor').value)||1.0;
  const btn=document.getElementById('btn-find-route');
  btn.classList.add('loading'); btn.textContent='⏳ Menghitung…';
  drawNodes();
  try{
    const r=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({start,end,scenario:scen,time_factor:tfac})});
    const data=await r.json();
    if(data.error){showAlert(data.detail||data.error,'error');return;}
    if(routeLayer){routeLayer.forEach(l=>map.removeLayer(l));routeLayer=null;}

    const layers=[];
    const allGeom=data.edges_geometry||[];
    const routeLines=allGeom
      .map(eg=>(eg.geometry||[]).map(p=>[p[0],p[1]]))
      .filter(ll=>ll.length>1);
    if(routeLines.length){
      const glow=L.polyline(routeLines,{color:'#fbbf24',weight:12,opacity:.2,smoothFactor:.1}).addTo(map);
      const line=L.polyline(routeLines,{color:'#f59e0b',weight:6,opacity:1,smoothFactor:.1}).addTo(map);
      layers.push(glow,line);
    }
    routeLayer=layers;

    const routePts=routeLines.flat();
    if(routePts.length>1){
      map.fitBounds(L.latLngBounds(routePts),{padding:[50,50]});
    }else if(data.path&&data.path.length>1){
      const pts=data.path.filter(id=>nodeById[id]).map(id=>[nodeById[id].lat,nodeById[id].lon]);
      map.fitBounds(L.latLngBounds(pts),{padding:[50,50]});
    }
    document.getElementById('m-dist').textContent=data.total_dist_m??'-';
    document.getElementById('m-eta').textContent=data.eta_minutes??'-';
    document.getElementById('m-iter').textContent=data.iterations??'-';
    document.getElementById('m-ms').textContent=data.execution_ms??'-';

    const ul=document.getElementById('path-list'); ul.innerHTML='';
    (data.path||[]).forEach((id,i)=>{
      const li=document.createElement('li');
      li.textContent=`${id} – ${nodeById[id]?.name||id}`;
      if(i===0)li.classList.add('start');
      if(i===data.path.length-1)li.classList.add('end');
      ul.appendChild(li);
    });
    document.getElementById('metrics').style.display='block';
    showAlert(`Rute: ${data.total_dist_m}m, ETA ${data.eta_minutes} menit`,'success');
  }catch(e){showAlert('Error: '+e.message,'error');}
  finally{btn.classList.remove('loading');btn.textContent='🔍 Cari Rute Tercepat';}
}

function clearRoute(){
  if(routeLayer){routeLayer.forEach(l=>map.removeLayer(l));routeLayer=null;}
  document.getElementById('metrics').style.display='none';
  document.getElementById('alert').style.display='none';
}
// ── Auto-Generate OSM Roads ──────────────────────────────
async function generateOSMRoads(){
  if(!confirm("Fitur ini akan mengunduh semua jalan kaki/kendaraan dari OpenStreetMap di area kampus UNIB dan menjadikannya jalur di aplikasi.\n\nLanjutkan?")) return;
  const btn = document.getElementById('btn-osm-sync');
  const oldText = btn.textContent;
  btn.textContent = '⏳ Mengunduh...';
  btn.style.pointerEvents = 'none';
  btn.style.opacity = '0.7';
  
  try {
    const r = await fetch('/api/osm-sync', {method: 'POST'});
    const d = await r.json();
    if(d.ok) {
      showAlert(`Berhasil! ${d.nodes_added} titik (waypoint) dan ${d.edges_added} jalan baru ditambahkan dari OSM.`,'success');
      await loadGraph();
    } else {
      showAlert(d.error || 'Gagal mengunduh OSM', 'error');
    }
  } catch(e) {
    showAlert('Error: ' + e.message, 'error');
  } finally {
    btn.textContent = oldText;
    btn.style.pointerEvents = 'auto';
    btn.style.opacity = '1';
  }
}

async function clearOSMRoads(){
  if(!confirm("Apakah Anda yakin ingin menghapus semua titik dan jalan yang di-generate dari OSM?")) return;
  const btn = document.getElementById('btn-osm-clear');
  const oldText = btn.textContent;
  btn.textContent = '⏳ Menghapus...';
  try {
    const r = await fetch('/api/osm-sync', {method: 'DELETE'});
    const d = await r.json();
    if(d.ok) {
      showAlert('Semua jalan dari OSM telah dihapus!','success');
      await loadGraph();
    }
  } catch(e) {
    showAlert('Error: ' + e.message, 'error');
  } finally {
    btn.textContent = oldText;
  }
}

// ── Compare Scenarios ──────────────────────────────────────
async function compareScenarios(){
  const start=document.getElementById('sel-start').value;
  const end=document.getElementById('sel-end').value;
  const tfac=parseFloat(document.getElementById('time-factor').value)||1.0;
  const overlay=document.getElementById('compare-overlay');
  const grid=document.getElementById('compare-grid');
  grid.innerHTML='<div style="text-align:center;padding:24px;color:#7fb4ab">⏳ Menghitung semua skenario…</div>';
  overlay.classList.add('visible');

  try{
    const entries=await Promise.all(graph.scenarios.map(async sc=>{
      const r=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({start,end,scenario:sc.id,time_factor:tfac})});
      return [sc.id,await r.json()];
    }));
    const results=Object.fromEntries(entries);
    // Find best
    let bestId=null,bestCost=Infinity;
    for(const[k,v]of Object.entries(results)){
      if(!v.error&&v.total_cost<bestCost){bestCost=v.total_cost;bestId=k;}
    }
    grid.innerHTML='';
    for(const sc of graph.scenarios){
      const r=results[sc.id];
      const isBest=sc.id===bestId;
      const card=document.createElement('div');
      card.className='compare-card'+(isBest?' best':'');
      if(r.error){
        card.innerHTML=`<div class="cc-name" style="color:${sc.color||'#5eead4'}">${sc.id}</div><div class="cc-error">❌ ${r.detail||r.error}</div>`;
      }else{
        card.innerHTML=`<div class="cc-name" style="color:${sc.color||'#5eead4'}">${sc.id} ${isBest?'<span class="cc-badge cc-best">TERBAIK</span>':''}</div>
          <div class="cc-metrics">
            <div class="cc-metric"><div class="cc-val">${r.total_dist_m}</div><div class="cc-lbl">Jarak (m)</div></div>
            <div class="cc-metric"><div class="cc-val">${r.eta_minutes}</div><div class="cc-lbl">ETA (min)</div></div>
            <div class="cc-metric"><div class="cc-val">${r.iterations}</div><div class="cc-lbl">Iterasi</div></div>
            <div class="cc-metric"><div class="cc-val">${r.execution_ms}</div><div class="cc-lbl">Waktu (ms)</div></div>
          </div>`;
      }
      grid.appendChild(card);
    }
  }catch(e){grid.innerHTML=`<div class="cc-error">Error: ${e.message}</div>`;}
}

function closeCompare(){document.getElementById('compare-overlay').classList.remove('visible');}

// ── Conditions Table (clickable rows) ──────────────────────
async function refreshCondTable(){
  const r=await fetch('/api/conditions'); conditions=await r.json();
  const ec=conditions.edge_conditions||{};
  const tbody=document.getElementById('cond-tbody'); tbody.innerHTML='';
  graph.edges.forEach(e=>{
    const c=ec[e.id];
    const st=c?(c.status||c.type||'NORMAL').toUpperCase():'NORMAL';
    const cls={NORMAL:'normal',BUSY:'busy',POTHOLE:'pothole',CLOSED:'closed',CUSTOM:'custom'}[st]||'normal';
    const from=nodeById[e.from]?.name?.substring(0,18)||e.from;
    const to=nodeById[e.to]?.name?.substring(0,18)||e.to;
    const tr=document.createElement('tr');
    tr.innerHTML=`<td><b>${e.id}</b></td><td style="font-size:10px">${from}<br>→ ${to}</td><td>${e.distance}m</td><td><span class="badge badge-${cls}">${st}</span></td>`;
    tr.addEventListener('click',()=>{
      if(edgeLayers[e.id]){
        map.fitBounds(edgeLayers[e.id].getBounds(),{padding:[80,80],maxZoom:18});
        edgeLayers[e.id].setStyle({weight:9,opacity:1});
        setTimeout(()=>edgeLayers[e.id].setStyle({weight:3.5,opacity:.55}),1500);
      }
      openEdgeEditor(e);
    });
    tbody.appendChild(tr);
  });
  if(graph)drawEdges();
}

async function resetConditions(){
  if(!confirm('Reset semua kondisi?'))return;
  await fetch('/api/conditions/reset',{method:'POST'});
  conditions={edge_conditions:{},edge_directions:{}};
  drawEdges();refreshCondTable();showAlert('Semua kondisi direset','success');
}

// ── Scenario Management ────────────────────────────────────
function renderScenarioCards(){
  const container=document.getElementById('scenario-cards');
  if(!container||!graph)return;
  container.innerHTML='';
  graph.scenarios.forEach(sc=>{
    const mods=sc.edge_modifiers||{};
    const blocked=sc.blocked_edges||[];
    const isBuiltin=['Normal','Wisuda','UTBK','Event Besar'].includes(sc.id);
    let tags='';
    for(const[eid,mul]of Object.entries(mods))tags+=`<span class="sc-tag">×${mul} ${eid}</span>`;
    for(const eid of blocked)tags+=`<span class="sc-tag sc-tag-blocked">🚫 ${eid}</span>`;
    if(!tags)tags='<span style="font-size:10px;color:#7fb4ab">Tidak ada modifikasi</span>';
    const deleteBtn=isBuiltin?'':`<button class="sc-card-delete" onclick="deleteScenario('${sc.id}')" title="Hapus">✕</button>`;
    container.innerHTML+=`<div class="sc-card" style="border-left-color:${sc.color}">
      <div class="sc-card-header"><span class="sc-card-name" style="color:${sc.color}">${sc.id}</span>${deleteBtn}</div>
      <div class="sc-card-desc">${sc.description||'—'}</div>
      <div class="sc-card-tags">${tags}</div>
    </div>`;
  });
}

async function addScenario(){
  const name=document.getElementById('new-sc-name').value.trim();
  const desc=document.getElementById('new-sc-desc').value.trim();
  const color=document.querySelector('input[name="sc-color"]:checked')?.value||'#14b8a6';
  const modsRaw=document.getElementById('new-sc-mods').value.trim();
  const blockedRaw=document.getElementById('new-sc-blocked').value.trim();
  if(!name){showAlert('Nama skenario wajib diisi','error');return;}
  // Parse modifiers: "E01:2.0, E02:1.5"
  const edge_modifiers={};
  if(modsRaw)modsRaw.split(',').forEach(p=>{const[k,v]=p.trim().split(':');if(k&&v)edge_modifiers[k.trim()]=parseFloat(v);});
  const blocked_edges=blockedRaw?blockedRaw.split(',').map(s=>s.trim()).filter(Boolean):[];
  try{
    const r=await fetch('/api/scenarios',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,description:desc,color,edge_modifiers,blocked_edges})});
    const d=await r.json();
    if(d.error){showAlert(d.error,'error');return;}
    showAlert(`Skenario "${name}" ditambahkan!`,'success');
    // Clear form
    document.getElementById('new-sc-name').value='';
    document.getElementById('new-sc-desc').value='';
    document.getElementById('new-sc-mods').value='';
    document.getElementById('new-sc-blocked').value='';
    loadGraph();
  }catch(e){showAlert('Gagal: '+e.message,'error');}
}

async function deleteScenario(id){
  if(!confirm(`Hapus skenario "${id}"?`))return;
  try{
    const r=await fetch('/api/scenarios',{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    const d=await r.json();
    if(d.ok){showAlert(`Skenario "${id}" dihapus`,'success');loadGraph();}
  }catch(e){showAlert('Gagal: '+e.message,'error');}
}

// ── Events ─────────────────────────────────────────────────
document.getElementById('sel-start').addEventListener('change',drawNodes);
document.getElementById('sel-end').addEventListener('change',drawNodes);
document.getElementById('sel-scenario').addEventListener('change',()=>{updateScenarioInfo();drawEdges();});

document.addEventListener('keydown',e=>{if(e.key==='Enter'&&!isDrawing&&document.getElementById('tab-route').classList.contains('active'))findRoute();});

// ── Init ───────────────────────────────────────────────────
loadGraph();
setTimeout(()=>map.invalidateSize(),200);
window.addEventListener('resize',()=>map.invalidateSize());
