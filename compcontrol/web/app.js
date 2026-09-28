'use strict';
const $ = (id) => document.getElementById(id);
const defaults = [
  {title:'Set the soundtrack', command:'play sad Hindi songs on Spotify', icon:'♫', note:'Find your next favorite'},
  {title:'A little screen time', command:'open Brave and search for Sidemen videos on YouTube', icon:'▷', note:'Go straight to YouTube'},
  {title:'Find anything', command:'search for things to do in Delhi', icon:'↗', note:'Your curiosity, one search away'},
  {title:'A fresh page', command:'open Notepad', icon:'▤', note:'Make room for an idea'},
];
const skillData = [
  ['01 / Applications','Your everyday essentials','Open registered Windows apps using trusted installation paths. No shell commands or arbitrary executables.', ['open Calculator','open Brave','open Notepad','open File Explorer']],
  ['02 / Web & video','Follow your curiosity','Search Google, YouTube or Maps in your default or named browser. Search terms go to the chosen website.', ['search YouTube for Sidemen videos','search for weekend projects','search Maps for coffee near Delhi']],
  ['03 / Music','Find your soundtrack','Open Spotify search and liked songs. Choose playback yourself; no login automation or paid-service workarounds.', ['play sad Hindi songs','open Spotify and play my liked playlist']],
  ['04 / Media keys','Stay in the moment','Send one media key to the active Windows player. Toggle state is not read; this may affect another active player.', ['toggle playback','next track','volume down','toggle mute']],
  ['05 / Local utilities','A little headspace','Check local time or evaluate bounded arithmetic, with no network request or AI model.', ['what time is it','calculate (2400 * 0.18) + 2400']],
  ['06 / Text assistant','Two personalities. Your choice.','Jarvis is measured; Friday is direct. Optional local or cloud text answers, with explicit consent and no tool access.', ['help']],
];
const viewNames = {command:'Command center', skills:'Skill library', activity:'Activity', settings:'Settings'};
let prefs = {persona:'jarvis', browser:'default', shortcuts:structuredClone(defaults)};
try {
  const saved = JSON.parse(localStorage.getItem('compcontrol.preferences') || 'null');
  if (saved && ['jarvis','friday'].includes(saved.persona)) prefs.persona = saved.persona;
  if (saved && ['default','chrome','brave','edge'].includes(saved.browser)) prefs.browser = saved.browser;
  if (saved && Array.isArray(saved.shortcuts) && saved.shortcuts.length === 4 && saved.shortcuts.every(x=>x && typeof x.title === 'string' && x.title.length <= 30 && typeof x.command === 'string' && x.command.length <= 300)) {
    prefs.shortcuts = saved.shortcuts.map((x,i)=>({...defaults[i], title:x.title, command:x.command}));
  }
} catch (_) { /* Storage is optional, not a requirement. */ }
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
if (location.hash) history.replaceState(null, '', location.pathname);
const demoToken = document.querySelector('meta[name="compcontrol-demo"]').content;
if (!token && demoToken !== 'PRIVATE_SESSION') token = demoToken;
// Token stays only in memory; not in localStorage, sessionStorage, cookies or URLs.
let state = {demo:false, paused:false, activity:[], provider:{enabled:false}};
let mode = 'command', busy = false, pending = null, deadline = 0, connected = false;

function savePrefs(){try{localStorage.setItem('compcontrol.preferences', JSON.stringify(prefs));}catch(_){notify('Preferences cannot be saved in this browser. The session still works.');}}
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
  $('welcome-text').textContent=name==='jarvis'?'What can I take off your hands?':"All right. What are we getting done?";
}
function addMessage(speaker,text,type='assistant'){
  const wrap=node('div',`message ${type}`);wrap.append(node('span','speaker',speaker),node('p','',text));
  $('conversation').append(wrap);while($('conversation').children.length>40)$('conversation').children[1].remove();
  $('conversation').scrollTop=$('conversation').scrollHeight;
}
function setBusy(value){busy=value;$('send-button').disabled=value||!connected;$('approve-button').disabled=value;$('cancel-button').disabled=value;$('clear-session').disabled=value;$('assistant-status').textContent=value?'Working on your request…':(state.paused?'Actions are paused':'Ready when you are');}
async function api(path, body){
  const options={headers:{Authorization:`Bearer ${token}`},cache:'no-store',credentials:'omit'};
  if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch(path,options);let data;try{data=await response.json();}catch(_){throw new Error('Server unavailable. Restart CompControl and reopen its private launch URL.');}
  if(!response.ok)throw new Error(data.error||'Request failed.');return data;
}
function resetApproval(){pending=null;$('approval').hidden=true;}
function statusClass(status){return ['executed','simulated','resumed'].includes(status)?'green':['awaiting approval','paused','failed','expired'].includes(status)?'amber':'';}
function activityRow(event){
  const row=node('div','activity-row');row.append(node('time','',event.time),node('strong','',event.title),node('span',`tag ${statusClass(event.status)}`,event.status.toUpperCase()));return row;
}
function renderActivity(){
  $('activity-count').textContent=state.activity.length;$('log-total').textContent=`/ ${state.activity.length} events`;
  $('activity-list').replaceChildren(...(state.activity.length?state.activity.map(activityRow):[node('div','empty-state','No actions yet. Your activity stays in this session.')]));
  if(state.activity.length){const event=state.activity[0];$('recent-activity').replaceChildren(node('span','empty-icon','↗'));const detail=node('div');detail.append(node('strong','',event.title),node('p','',`${event.time} · ${event.status} · current session only`));$('recent-activity').append(detail);}
  else{$('recent-activity').replaceChildren(node('span','empty-icon','↗'));const d=node('div');d.append(node('strong','','A clean slate.'),node('p','','Your approved actions will appear here. Nothing runs in the background.'));$('recent-activity').append(d);}
}
function renderState(){
  $('mode-badge').replaceChildren(node('i'),document.createTextNode(state.demo?'Interactive demo':'Windows · local'));
  $('pause-button').textContent=state.paused?'▶ Resume actions':'Ⅱ Pause actions';
  $('pause-button').setAttribute('aria-pressed',String(state.paused));
  $('provider-summary').textContent=state.provider.enabled?`${state.provider.kind} · ${state.provider.model} · ${state.provider.host}. Only explicit AI questions are sent.`:'No AI provider configured. All command skills still work.';
  $('provider-tag').textContent=state.provider.enabled?(state.provider.cloud?'CLOUD · OPT-IN':'LOCAL · OPT-IN'):'OFF BY DEFAULT';
  $('ai-consent-text').textContent=state.provider.cloud?`Send only this question to ${state.provider.host}. Charges may apply. This provider's privacy policy applies. AI cannot execute actions.`:'Send only this question to my configured local model. AI cannot execute actions.';
  if(pending && state.pending_id!==pending.approval_id){resetApproval();}
  renderActivity();
  if(!busy)$('assistant-status').textContent=state.paused?'Actions are paused':'Ready when you are';
}
async function refresh(){state=await api('/api/state');renderState();}
function renderShortcuts(){
  $('shortcuts').replaceChildren(...prefs.shortcuts.map((item,i)=>{const button=node('button','shortcut');button.type='button';const top=node('span','shortcut-top');top.append(node('span','shortcut-icon',defaults[i].icon),node('span','shortcut-arrow','↗'));button.append(top,node('strong','',item.title),node('small','',item.command===defaults[i].command?defaults[i].note:item.command));button.addEventListener('click',()=>fillCommand(item.command));return button;}));
}
function fillCommand(text){showView('command');setMode('command');$('command-input').value=text;$('command-input').focus();}
function setMode(value){
  mode=value;$('ai-consent').checked=false;$('ai-consent-row').hidden=value!=='ai';
  document.querySelectorAll('[data-mode]').forEach(b=>{const active=b.dataset.mode===value;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('engine-label').textContent=value==='ai'?'TEXT ONLY · NO TOOLS':'LOCAL COMMANDS';
  $('command-input').placeholder=value==='ai'?'Ask a text question. No tools or desktop actions.':'Try “open Brave and search for Sidemen on YouTube”';
}
function showApproval(plan){
  pending=plan;deadline=Date.now()+plan.expires_in*1000;$('approval-title').textContent=plan.title;$('approval-detail').textContent=plan.message;
  $('approval-destination').textContent=plan.destinations.join('\n');
  $('approval-mode-note').textContent=state.demo?'DEMO: approval records a simulation only. Your device is not controlled.':'Windows will ask once more before dispatching. The native dialog shows the exact executable or destination. Default answer: No.';
  $('approve-button').textContent=state.demo?'Simulate approval ↗':'Approve action ↗';$('approval').hidden=false;$('approval-clock').textContent='02:00';
}
$('command-form').addEventListener('submit',async(event)=>{
  event.preventDefault();const text=$('command-input').value.trim();if(!text||busy||!connected)return;
  if(mode==='ai'&&!state.provider.enabled){notify('AI is off. Open Settings for local-model setup. No text was sent to a provider.');return;}
  if(mode==='ai'&&!$('ai-consent').checked){notify('Please review and accept the provider disclosure before asking AI.');return;}
  setBusy(true);addMessage('You',text,'user');$('command-input').value='';
  try{
    if(mode==='ai'){
      if(pending)await api('/api/cancel',{approval_id:pending.approval_id});resetApproval();
      const answer=await api('/api/chat',{text,persona:prefs.persona,consent:true});addMessage(`${$('assistant-name').textContent} · AI text`,answer.answer);
    }else{
      resetApproval();const plan=await api('/api/plan',{text,browser:prefs.browser});
      if(plan.approval_id)showApproval(plan);else addMessage($('assistant-name').textContent,`${plan.title}\n${plan.message}`);
    }
    await refresh();
  }catch(error){addMessage('No action taken',error.message,'error');}finally{setBusy(false);$('ai-consent').checked=false;$('command-input').focus();}
});
$('command-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('command-form').requestSubmit();}});
$('approve-button').addEventListener('click',async()=>{
  if(!pending||busy)return;const id=pending.approval_id;setBusy(true);
  try{const outcome=await api('/api/confirm',{approval_id:id});addMessage(outcome.status==='simulated'?'Demo result':$('assistant-name').textContent,outcome.message);}catch(error){addMessage('Action not confirmed',error.message,'error');}
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
  if(!window.confirm('Clear this session’s activity, conversation and any pending approval?'))return;
  try{await api('/api/clear',{});resetApproval();$('conversation').querySelectorAll('.message').forEach(n=>n.remove());await refresh();}catch(e){notify(e.message);}
});
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
$('reset-preferences').addEventListener('click',()=>{if(!window.confirm('Reset persona, browser and all shortcuts?'))return;prefs={persona:'jarvis',browser:'default',shortcuts:structuredClone(defaults)};savePrefs();setPersona('jarvis');$('browser-select').value='default';renderShortcuts();notify('Local preferences reset.');});
$('skill-grid').replaceChildren(...skillData.map(([number,title,description,examples])=>{const card=node('article','skill-card');card.append(node('div','eyebrow',number),node('h2','',title),node('p','',description));examples.forEach(example=>{const b=node('button','',`›  ${example}`);b.addEventListener('click',()=>fillCommand(example));card.append(b);});return card;}));
setPersona(prefs.persona);$('browser-select').value=prefs.browser;renderShortcuts();
setBusy(false);
(async()=>{try{await refresh();connected=true;setBusy(false);if(state.demo)notify('INTERACTIVE DEMO · Try commands and approvals. Nothing runs on your computer or this server. AI is disabled.');}catch(error){notify(error.message);$('mode-badge').textContent='Session locked';}})();
setInterval(()=>{if(!pending)return;const seconds=Math.max(0,Math.ceil((deadline-Date.now())/1000));$('approval-clock').textContent=`${String(Math.floor(seconds/60)).padStart(2, '0')}:${String(seconds%60).padStart(2, '0')}`;if(seconds===0){resetApproval();addMessage('Approval expired','Send the request again to create a fresh approval. Nothing was dispatched.');}},1000);
