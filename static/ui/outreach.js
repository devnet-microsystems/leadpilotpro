(function(){
var LP=window.LP;
LP.renderOutreach=function(){
  var root=LP.$("#view-outreach");LP.page(root,"Outreach","Controlled outreach","Queue and history are separate from sequence generation.");
  var panel=LP.card([]),tabs=LP.el("div",{className:"tabs"});
  [["queue","Sender Queue"],["history","History"],["builder","Campaign Builder"]].forEach(function(x){
    tabs.appendChild(LP.el("button",{className:"tab-btn "+(LP.state.outTab===x[0]?"active":""),text:x[1],onClick:function(){LP.state.outTab=x[0];LP.renderOutreach();}}));
  });
  panel.appendChild(tabs);panel.appendChild(LP.el("div",{id:"out-body"}));root.appendChild(panel);
  if(LP.state.outTab==="queue")return LP.renderQueue();
  if(LP.state.outTab==="history")return LP.renderHistory();
  LP.$("#out-body").appendChild(LP.note("The complete strategy/sequence editor remains available in the archived UI while the primary navigation is consolidated.","good"));
  LP.$("#out-body").appendChild(LP.button("Open campaign builder","btn-primary",function(){window.open("/static/old/index.html","_blank");}));
};
LP.renderQueue=async function(){
  var x=await Promise.all([LP.api("/api/status"),LP.api("/api/campaigns")]),s=x[0],campaigns=x[1]||[],root=LP.$("#out-body");
  root.appendChild(LP.note("Only exported campaigns appear here. Sending remains explicit.","good"));
  root.appendChild(LP.el("div",{className:"grid two section"},[
    LP.card([LP.el("div",{className:"label",text:"Approved queue"}),LP.el("div",{className:"value",text:String(s.approved||0)})]),
    LP.card([LP.el("div",{className:"label",text:"Exported campaigns"}),LP.el("div",{className:"value",text:String(campaigns.length)})])
  ]));
  var select=LP.el("select",{id:"send-c",className:"control"});select.appendChild(LP.el("option",{value:"",text:"Choose campaign"}));
  campaigns.forEach(function(c){select.appendChild(LP.el("option",{value:c.name,text:c.name}));});
  var limit=LP.el("input",{id:"send-limit",className:"input",type:"number",value:"25",min:"1"});
  var when=LP.el("input",{id:"send-time",className:"input",type:"datetime-local"});
  var send=LP.button("Send approved queue","btn-danger",async function(){
    if(!confirm("Send approved prospects now?"))return;
    var payload={campaign:select.value,limit:Number(limit.value||25)};
    if(when.value)payload.scheduled_at=new Date(when.value).toISOString();
    try{await LP.api("/api/send",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});LP.toast(payload.scheduled_at?"Scheduled":"Sending started","good");}
    catch(e){LP.toast(e.message,"error");}
  });
  send.disabled=true;select.onchange=function(){send.disabled=!select.value;};
  root.appendChild(LP.card([
    LP.el("div",{className:"grid three"},[
      LP.el("div",{className:"field"},[LP.el("label",{text:"Campaign"}),select]),
      LP.el("div",{className:"field"},[LP.el("label",{text:"Limit"}),limit]),
      LP.el("div",{className:"field"},[LP.el("label",{text:"Schedule optional"}),when])
    ]),
    LP.el("div",{className:"actions"},[send])
  ]));
};
LP.renderHistory=async function(){
  var rows=await LP.api("/api/archive"),root=LP.$("#out-body");
  if(!rows.length){root.appendChild(LP.el("div",{className:"empty",text:"No sent history yet."}));return;}
  var table='<div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Company</th><th>Email</th><th>Campaign</th></tr></thead><tbody>';
  rows.forEach(function(x){
    table+="<tr><td>"+LP.esc((x.sent_at_utc||"").slice(0,16).replace("T"," "))+"</td><td>"+LP.esc(x.company_name||"")+"</td><td>"+LP.esc(x.business_email||"")+"</td><td>"+LP.esc(x.campaign||"")+"</td></tr>";
  });
  table+="</tbody></table></div>";root.insertAdjacentHTML("beforeend",table);
};
})();