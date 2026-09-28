(function(){
var LP=window.LP;
LP.loadProducts=async function(){
  LP.state.products=await LP.api("/api/products");
  var ready=LP.state.products.filter(function(p){return p.status==="READY"});
  if(!LP.state.productId||!ready.some(function(p){return Number(p.id)===Number(LP.state.productId)}))LP.state.productId=ready.length?ready[0].id:null;
};
LP.loadPipeline=async function(){
  if(!LP.state.productId){LP.state.pipeline=null;LP.state.evidence=[];return;}
  var x=await Promise.all([
    LP.api("/api/orchestrator/pipeline_status?product_id="+LP.state.productId),
    LP.api("/api/orchestrator/evidence?product_id="+LP.state.productId)
  ]);
  LP.state.pipeline=x[0];LP.state.evidence=x[1]||[];
};
LP.renderFind=async function(){
  var root=LP.$("#view-find");LP.page(root,"Customer discovery","Find Customers","Choose a product, set a budget and run the existing customer-discovery engine.");
  try{
    await LP.loadProducts();await LP.loadPipeline();
    var ready=LP.state.products.filter(function(p){return p.status==="READY"});
    if(!ready.length){root.appendChild(LP.note("No ready products. Open Advanced → Products to create and analyze one.","warn"));return;}
    var layout=LP.el("div",{className:"find-layout"});
    var side=LP.card([], "side-card");
    side.appendChild(LP.el("div",{className:"section-title"},[LP.el("div",{},[LP.el("h3",{text:"Products"}),LP.el("p",{text:"Ready products only."})])]));
    var list=LP.el("div",{className:"side-list"});
    ready.forEach(function(p){
      list.appendChild(LP.el("button",{className:"side-item "+(Number(p.id)===Number(LP.state.productId)?"active":""),onClick:function(){LP.state.productId=p.id;LP.renderFind();}},[
        LP.el("strong",{text:p.name}),LP.el("small",{text:"READY"})
      ]));
    });
    side.appendChild(list);layout.appendChild(side);layout.appendChild(LP.el("div",{id:"find-main"}));root.appendChild(layout);LP.drawFind();
  }catch(e){root.appendChild(LP.note(e.message,"bad"))}
};
LP.drawFind=function(){
  var root=LP.$("#find-main");if(!root)return;LP.clear(root);
  var s=LP.state,p=s.products.find(function(x){return Number(x.id)===Number(s.productId)}),status=s.pipeline?s.pipeline.campaign_status:"NOT_STARTED",qualified=Number(s.pipeline?s.pipeline.qualified:0);
  var select=LP.el("select",{id:"find-budget",className:"control"});
  [["50","50 · focused"],["150","150 · recommended"],["300","300 · broad"]].forEach(function(v){select.appendChild(LP.el("option",{value:v[0],text:v[1]}))});
  select.value="150";
  var run=LP.button(status==="RUNNING"?"Researching…":status==="COMPLETED"?"Run again":"Find customers","btn-good",async function(){
    run.disabled=true;
    try{await LP.api("/api/orchestrator/auto_pilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:Number(s.productId),max_leads:Number(select.value)})});LP.toast("Research started","good");LP.watchFind();}
    catch(e){LP.toast(e.message,"error");run.disabled=false;}
  });
  run.disabled=status==="RUNNING";
  root.appendChild(LP.card([LP.el("div",{className:"step-row"},[
    LP.el("div",{className:"step-label"},[LP.el("span",{className:"step-no",text:"01"}),LP.el("div",{},[LP.el("h3",{text:p?p.name:""}),LP.el("p",{text:"Product Intelligence READY."})])]),
    LP.el("span",{className:"pill good",text:"READY"})
  ])]));
  root.appendChild(LP.card([LP.el("div",{className:"step-row"},[
    LP.el("div",{className:"step-label"},[LP.el("span",{className:"step-no",text:"02"}),LP.el("div",{},[LP.el("h3",{text:"Discovery budget"}),LP.el("p",{text:"The existing relevance and sender gates stay unchanged."})])]),select
  ]),LP.el("div",{className:"actions"},[LP.el("span",{className:"muted small",text:status}),run])]));
  var metrics=LP.el("div",{className:"metrics"});
  [["Discovered",s.pipeline?s.pipeline.discovered:0],["Qualified",qualified],["Rejected",s.pipeline?s.pipeline.rejected:0],["Approved",s.pipeline?s.pipeline.approved:0]].forEach(function(m){metrics.appendChild(LP.el("div",{className:"metric"},[LP.el("span",{text:m[0]}),LP.el("strong",{text:String(m[1])})]))});
  root.appendChild(LP.card([LP.el("div",{className:"section-title"},[LP.el("div",{},[LP.el("h3",{text:"Research results"}),LP.el("p",{text:"Live production counters."})])]),metrics]));
  if(qualified){
    var evid=LP.el("div",{className:"evidence"});
    s.evidence.forEach(function(x){
      var actions=x.evidence_reviewed_at?LP.el("span",{className:"pill good",text:"Reviewed"}):LP.el("div",{className:"toolbar"},[
        LP.button("Approve","btn-good",function(){LP.reviewEvidence(x.id,"APPROVE")}),
        LP.button("Reject","btn-danger",function(){LP.reviewEvidence(x.id,"REJECT")})
      ]);
      evid.appendChild(LP.el("div",{className:"evidence-row"},[
        LP.el("div",{},[LP.el("h4",{text:String(x.company_name||"")+" · "+Number(x.fit_score||0)+"/100"}),LP.el("p",{text:x.reason||""})]),actions
      ]));
    });
    if(!s.evidence.length)evid.appendChild(LP.el("div",{className:"empty",text:"Qualified results exist, but evidence is not available yet."}));
    root.appendChild(LP.card([LP.el("div",{className:"section-title"},[LP.el("div",{},[LP.el("h3",{text:"Evidence review"}),LP.el("p",{text:"Human review remains the outreach gate."})])]),evid]));
    root.appendChild(LP.card([LP.el("div",{className:"step-row"},[
      LP.el("div",{},[LP.el("h3",{text:"Next step: outreach"}),LP.el("p",{text:"Build the sales strategy and sequence."})]),
      LP.button("Open outreach","btn-primary",function(){LP.nav("outreach")})
    ])]));
  }
  root.appendChild(LP.card([LP.el("div",{className:"step-row"},[
    LP.el("div",{},[LP.el("h3",{text:"Advanced discovery"}),LP.el("p",{text:"Manual search and query controls stay out of the main workflow."})]),
    LP.button("Open Advanced","btn-secondary",function(){LP.nav("advanced")})
  ])]));
};
LP.reviewEvidence=async function(id,action){
  var reason=action==="REJECT"?(prompt("Reason:","Not a fit")||"Not a fit"):"";
  try{await LP.api("/api/orchestrator/prospect/"+id+"/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:action,reason:reason})});LP.toast("Evidence updated","good");await LP.loadPipeline();LP.drawFind();}
  catch(e){LP.toast(e.message,"error");}
};
LP.watchFind=function(){
  if(LP.state.poll)clearInterval(LP.state.poll);
  LP.state.poll=setInterval(async function(){try{await LP.loadPipeline();LP.drawFind();if(!LP.state.pipeline||LP.state.pipeline.campaign_status!=="RUNNING"){clearInterval(LP.state.poll);LP.state.poll=null;}}catch(e){}},3000);
};
})();