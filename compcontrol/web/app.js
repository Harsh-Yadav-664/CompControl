'use strict';
const $ = (id) => document.getElementById(id);
const defaults = [
  {title:'Liked Songs List', command:'play my liked songs list', icon:'🎵', note:'Open Spotify collection directly'},
  {title:'Launch VS Code', command:'open Visual Studio Code', icon:'💻', note:'Auto-discovered background launch'},
  {title:'Install VLC Player', command:'install VLC', icon:'📦', note:'Native Winget package installer'},
  {title:'System Telemetry', command:'system info', icon:'📊', note:'Live CPU, RAM & storage health'},
];
const skillData = [
  ['01 / Autonomous App Discovery','Launch any installed Windows app','Automatically scans Start menu AppIDs and installation directories in the background. No manual picker required.', ['open Visual Studio Code','open Discord','open Calculator','open Task Manager']],
  ['02 / Spotify & Liked Songs','Natural media intent recognition','Open your Spotify liked songs list, playlists, or artist searches directly via desktop URI handler.', ['play my liked songs list','open Spotify and play my liked playlist','play sad Hindi songs on Spotify']],
  ['03 / Native Winget Installer','One-command software installation','Install desktop software natively via Windows Package Manager (winget) with verified package IDs.', ['install VLC','install Blender','winget install Discord','install Obsidian']],
  ['04 / System Controls & Telemetry','Hardware diagnostics & settings','Inspect live CPU/RAM/storage health, lock workstation, take screenshots, or open Windows settings pages.', ['system info','disk space','battery status','open bluetooth settings','lock screen']],
  ['05 / Folder & Web Navigation','Instant workspace access','Jump directly to user folders, search YouTube/Google/Maps, or open HTTPS destinations.', ['open downloads','open documents','open yt and search for mr whose the boss','search Maps for coffee near Delhi']],
  ['06 / Media & Volume Keys','Zero-latency playback control','Dispatch hardware media keys directly to the active Windows audio session.', ['toggle playback','next track','volume up','volume down','toggle mute']],
];
const viewNames = {command:'Command center', skills:'Capability hub', activity:'Activity & logs', settings:'Engine settings'};
let prefs = {persona:'jarvis', browser:'default', autoApprove:true, shortcuts:structuredClone(defaults)};
try {
  const saved = JSON.parse(localStorage.getItem('compcontrol.preferences') || 'null');
  if (saved && ['jarvis','friday'].includes(saved.persona)) prefs.persona = saved.persona;
  if (saved && ['default','chrome','brave','edge'].includes(saved.browser)) prefs.browser = saved.browser;
  if (saved && typeof saved.autoApprove === 'boolean') prefs.autoApprove = saved.autoApprove;
  if (saved && Array.isArray(saved.shortcuts) && saved.shortcuts.length === 4 && saved.shortcuts.every(x=>x && typeof x.title === 'string' && x.title.length <= 30 && typeof x.command === 'string' && x.command.length <= 300)) {
    prefs.shortcuts = saved.shortcuts.map((x,i)=>({...defaults[i], title:x.title, command:x.command}));
  }
} catch (_) { /* Storage is optional */ }
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
if (location.hash) history.replaceState(null, '', location.pathname);
const demoToken = document.querySelector('meta[name="compcontrol-demo"]').content;
if (!token && demoToken !== 'PRIVATE_SESSION') token = demoToken;
let state = {demo:false, paused:false, activity:[], provider:{enabled:false}};
let mode = 'command', busy = false, pending = null, deadline = 0, connected = false;

function savePrefs(){try{localStorage.setItem('compcontrol.preferences', JSON.stringify(prefs));}catch(_){}}
function node(tag, cls, text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function notify(text){$('notice').textContent=text;$('notice').hidden=!text;}
function showView(name){
  if(!viewNames[name])return;
  document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==`view-${name}`);
  document.querySelectorAll('.nav-item').forEach(b=>{b.classList.toggle('selected',b.dataset.view===name);if(b.dataset.view===name)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  $('page-label').textContent=viewNames[name];
}
function setPersona(name){
  prefs.persona=name;document.body.classList.toggle('friday',name==='friday');
  document.querySelectorAll('[data-persona]').forEach(b=>{const active=b.dataset.persona===name;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('assistant-name').textContent=name==='jarvis'?'Jarvis':'Friday';$('active-avatar').textContent=name==='jarvis'?'J':'F';
  $('welcome-text').textContent=name==='jarvis'?'What are we getting done right now?':"All systems online. Give the word.";
}
function addMessage(speaker,text,type='assistant'){
  const wrap=node('div',`message ${type}`);wrap.append(node('span','speaker',speaker),node('p','',text));
  $('conversation').append(wrap);while($('conversation').children.length>40)$('conversation').children[1].remove();
  $('conversation').scrollTop=$('conversation').scrollHeight;
}
function setBusy(value){busy=value;$('send-button').disabled=value||!connected;$('approve-button').disabled=value;$('cancel-button').disabled=value;$('clear-session').disabled=value;$('assistant-status').textContent=value?'Executing command…':(state.paused?'Actions are paused':'Autonomous engine ready');}
async function api(path, body){
  const options={headers:{Authorization:`Bearer ${token}`},cache:'no-store',credentials:'omit'};
  if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch(path,options);let data;try{data=await response.json();}catch(_){throw new Error('Server unavailable.');}
  if(!response.ok)throw new Error(data.error||'Request failed.');return data;
}
function resetApproval(){pending=null;$('approval').hidden=true;}
function statusClass(status){return ['executed','simulated','resumed'].includes(status)?'green':['awaiting approval','paused','failed','expired'].includes(status)?'amber':'';}
function activityRow(event){
  const row=node('div','activity-row');row.append(node('time','',event.time),node('strong','',event.title),node('span',`tag ${statusClass(event.status)}`,event.status.toUpperCase()));return row;
}
function renderActivity(){
  $('activity-count').textContent=state.activity.length;$('log-total').textContent=`/ ${state.activity.length} events`;
  $('activity-list').replaceChildren(...(state.activity.length?state.activity.map(activityRow):[node('div','empty-state','No actions yet in this session.')]));
  if(state.activity.length){const event=state.activity[0];$('recent-activity').replaceChildren(node('span','empty-icon','⚡'));const detail=node('div');detail.append(node('strong','',event.title),node('p','',`${event.time} · ${event.status.toUpperCase()} · session log`));$('recent-activity').append(detail);}
  else{$('recent-activity').replaceChildren(node('span','empty-icon','⚡'));const d=node('div');d.append(node('strong','','Ready for action.'),node('p','','Executed commands and telemetry appear here in real time.'));$('recent-activity').append(d);}
}
function renderState(){
  $('mode-badge').replaceChildren(node('i'),document.createTextNode(state.demo?'Live Preview · Simulation':'Windows · Autonomous'));
  $('pause-button').textContent=state.paused?'▶ Resume':'Ⅱ Pause';
  $('pause-button').setAttribute('aria-pressed',String(state.paused));
  $('provider-summary').textContent=state.provider.enabled?`${state.provider.kind} · ${state.provider.model} · ${state.provider.host}`:'No AI provider configured. Local & discovery skills ready.';
  $('provider-tag').textContent=state.provider.enabled?(state.provider.cloud?'CLOUD AI ACTIVE':'LOCAL AI ACTIVE'):'LOCAL ENGINE';
  if(pending && state.pending_id!==pending.approval_id){resetApproval();}
  renderActivity();
  if(!busy)$('assistant-status').textContent=state.paused?'Actions are paused':'Autonomous engine ready';
}
async function refresh(){state=await api('/api/state');renderState();}
function renderShortcuts(){
  $('shortcuts').replaceChildren(...prefs.shortcuts.map((item,i)=>{const button=node('button','shortcut');button.type='button';const top=node('span','shortcut-top');top.append(node('span','shortcut-icon',defaults[i].icon),node('span','shortcut-arrow','⚡'));button.append(top,node('strong','',item.title),node('small','',item.command===defaults[i].command?defaults[i].note:item.command));button.addEventListener('click',()=>runQuickCommand(item.command));return button;}));
}
async function executePlan(text){
  if(!text||busy||!connected)return;
  setBusy(true);addMessage('You',text,'user');$('command-input').value='';
  try{
    resetApproval();
    const plan=await api('/api/plan',{text,browser:prefs.browser});
    if(plan.approval_id){
      const autoApprove = $('auto-approve-toggle') ? $('auto-approve-toggle').checked : true;
      if(autoApprove && !plan.requires_popup){
        const outcome=await api('/api/confirm',{approval_id:plan.approval_id});
        addMessage(
          `${$('assistant-name').textContent} · ⚡ Auto-Executed`,
          `${plan.title}\nDestination: ${plan.destinations.join(', ')}\n\n${outcome.message}`
        );
      }else{
        showApproval(plan);
      }
    }else{
      addMessage($('assistant-name').textContent,`${plan.title}\n${plan.message}`);
    }
    await refresh();
  }catch(error){addMessage('Attention',error.message,'error');}finally{setBusy(false);$('command-input').focus();}
}
function runQuickCommand(text){
  showView('command');setMode('command');
  executePlan(text);
}
function setMode(value){
  mode=value;$('ai-consent-row').hidden=value!=='ai';
  document.querySelectorAll('[data-mode]').forEach(b=>{const active=b.dataset.mode===value;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('engine-label').textContent=value==='ai'?'AI ASSISTANT':'AUTONOMOUS DISPATCH';
  $('command-input').placeholder=value==='ai'?'Ask a question…':'Try “play my liked songs list”, “open Visual Studio Code”, “install VLC”, or “system info”';
}
function showApproval(plan){
  pending=plan;deadline=Date.now()+plan.expires_in*1000;$('approval-title').textContent=plan.title;$('approval-detail').textContent=plan.message;
  $('approval-destination').textContent=plan.destinations.join('\n');
  $('approval-mode-note').textContent=plan.requires_popup?'⚠️ High-impact action requires confirmation before execution.':'Auto-Approve is paused; click Execute action to run.';
  $('approve-button').textContent='Execute action ⚡';$('approval').hidden=false;$('approval-clock').textContent='02:00';
}
$('command-form').addEventListener('submit',async(event)=>{
  event.preventDefault();const text=$('command-input').value.trim();if(!text||busy||!connected)return;
  if(mode==='ai'){
    if(!state.provider.enabled){notify('AI is not configured in this session. Switching to Autonomous Command mode.');setMode('command');return executePlan(text);}
    setBusy(true);addMessage('You',text,'user');$('command-input').value='';
    try{
      if(pending)await api('/api/cancel',{approval_id:pending.approval_id});resetApproval();
      const answer=await api('/api/chat',{text,persona:prefs.persona,consent:true});addMessage(`${$('assistant-name').textContent} · AI`,answer.answer);
      await refresh();
    }catch(error){addMessage('Attention',error.message,'error');}finally{setBusy(false);$('command-input').focus();}
  }else{
    await executePlan(text);
  }
});
$('command-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('command-form').requestSubmit();}});
$('approve-button').addEventListener('click',async()=>{
  if(!pending||busy)return;const id=pending.approval_id;setBusy(true);
  try{const outcome=await api('/api/confirm',{approval_id:id});addMessage($('assistant-name').textContent,outcome.message);}catch(error){addMessage('Action not confirmed',error.message,'error');}
  finally{resetApproval();setBusy(false);try{await refresh();}catch(e){notify(e.message);}}
});
$('cancel-button').addEventListener('click',async()=>{
  if(!pending||busy)return;setBusy(true);try{const result=await api('/api/cancel',{approval_id:pending.approval_id});addMessage('Cancelled',result.message);}catch(e){notify(e.message);}finally{resetApproval();setBusy(false);try{await refresh();}catch(e){notify(e.message);}}
});
$('pause-button').addEventListener('click',async()=>{
  $('pause-button').disabled=true;
  try{const result=await api('/api/pause',{paused:!state.paused});resetApproval();notify(result.message);await refresh();}catch(e){notify(e.message);}finally{$('pause-button').disabled=false;}
});
$('clear-session').addEventListener('click',async()=>{
  try{await api('/api/clear',{});resetApproval();$('conversation').querySelectorAll('.message').forEach(n=>n.remove());await refresh();}catch(e){notify(e.message);}
});
if($('auto-approve-toggle')){
  $('auto-approve-toggle').checked = prefs.autoApprove;
  $('auto-approve-toggle').addEventListener('change',()=>{prefs.autoApprove=$('auto-approve-toggle').checked;savePrefs();});
}
$('browser-select').addEventListener('change',()=>{prefs.browser=$('browser-select').value;savePrefs();});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));
document.querySelector('.brand').addEventListener('click',e=>{e.preventDefault();showView('command');});
document.querySelectorAll('[data-persona]').forEach(b=>b.addEventListener('click',()=>{setPersona(b.dataset.persona);savePrefs();}));
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mode)));
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();showView('command');$('command-input').focus();}});
function editorFields(items){
  $('shortcut-fields').replaceChildren(...items.map((item,i)=>{const row=node('div','shortcut-editor');const label=node('label','',`SHORTCUT ${i+1}`);const title=node('input');title.value=item.title;title.maxLength=30;title.required=true;title.name=`title-${i}`;label.append(title);const label2=node('label','','COMMAND');const command=node('input');command.value=item.command;command.maxLength=300;command.required=true;command.name=`command-${i}`;label2.append(command);row.append(label,label2);return row;}));
}
$('edit-shortcuts').addEventListener('click',()=>{editorFields(prefs.shortcuts);$('shortcut-dialog').showModal();});
$('close-shortcuts').addEventListener('click',()=>$('shortcut-dialog').close());
$('restore-shortcuts').addEventListener('click',()=>editorFields(defaults));
$('shortcut-form').addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target);prefs.shortcuts=defaults.map((item,i)=>({...item,title:data.get(`title-${i}`).trim(),command:data.get(`command-${i}`).trim()}));savePrefs();renderShortcuts();$('shortcut-dialog').close();});
$('reset-preferences').addEventListener('click',()=>{prefs={persona:'jarvis',browser:'default',autoApprove:true,shortcuts:structuredClone(defaults)};savePrefs();setPersona('jarvis');$('browser-select').value='default';if($('auto-approve-toggle'))$('auto-approve-toggle').checked=true;renderShortcuts();notify('Preferences reset to defaults.');});
$('skill-grid').replaceChildren(...skillData.map(([number,title,description,examples])=>{const card=node('article','skill-card');card.append(node('div','eyebrow',number),node('h2','',title),node('p','',description));examples.forEach(example=>{const b=node('button','',`⚡  ${example}`);b.addEventListener('click',()=>runQuickCommand(example));card.append(b);});return card;}));
setPersona(prefs.persona);$('browser-select').value=prefs.browser;renderShortcuts();
setBusy(false);
(async()=>{try{await refresh();connected=true;setBusy(false);}catch(error){notify(error.message);$('mode-badge').textContent='Session locked';}})();
setInterval(()=>{if(!pending)return;const seconds=Math.max(0,Math.ceil((deadline-Date.now())/1000));$('approval-clock').textContent=`${String(Math.floor(seconds/60)).padStart(2, '0')}:${String(seconds%60).padStart(2, '0')}`;if(seconds===0){resetApproval();addMessage('Approval expired','Send the request again to execute.');}},1000);
