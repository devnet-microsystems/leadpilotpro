(function(){
var LP=window.LP;

LP.loadProducts=async function(){
  LP.state.products=await LP.api("/api/products");
  var ready=LP.state.products.filter(function(p){return p.status==="READY"});
  if(!LP.state.productId||!ready.some(function(p){return Number(p.id)===Number(LP.state.productId)})){
    LP.state.productId=ready.length?ready[0].id:null;
  }
};

LP.loadPipeline=async function(){
  if(!LP.state.productId){
    LP.state.pipeline=null;LP.state.evidence=[];LP.state.approvedLeads=[];
    return;
  }
  var x=await Promise.all([
    LP.api("/api/orchestrator/pipeline_status?product_id="+LP.state.productId),
    LP.api("/api/orchestrator/evidence?product_id="+LP.state.productId),
    LP.api("/api/orchestrator/approved_leads?product_id="+LP.state.productId)
  ]);
  LP.state.pipeline=x[0];
  LP.state.evidence=x[1]||[];
  LP.state.approvedLeads=x[2]||[];
};

LP.loadSearchConfig=async function(){
  try{
    LP.state.searchProviders=await LP.api("/api/search_providers");
  }catch(e){
    LP.state.searchProviders=[];
  }
};

function field(id,label,value,placeholder){
  return LP.el("div",{className:"field"},[
    LP.el("label",{text:label}),
    LP.el("input",{id:id,className:"input",value:value||"",placeholder:placeholder||""})
  ]);
}

function selectedProviders(){
  return (LP.state.searchProviders||[]).filter(function(p){
    var el=LP.$("#provider-"+p.id);
    return el&&el.checked;
  }).map(function(p){return p.id});
}

function renderProviderChoices(){
  var box=LP.$("#find-providers");
  if(!box)return;
  LP.clear(box);
  (LP.state.searchProviders||[]).forEach(function(p){
    var checked=p.enabled && ["DuckDuckGoProvider","BraveProvider"].includes(p.id);
    var cb=LP.el("input",{type:"checkbox",id:"provider-"+p.id});
    cb.checked=checked;
    cb.disabled=!p.enabled;
    box.appendChild(LP.el("label",{className:"check-card"+(p.enabled?"":" disabled")},[
      cb,
      LP.el("span",{},[
        LP.el("strong",{text:p.name}),
        LP.el("small",{text:p.enabled?"Available for this search":"Not configured in Settings"})
      ])
    ]));
  });
  if(!(LP.state.searchProviders||[]).some(function(p){return p.enabled})){
    box.appendChild(LP.note("No configured search provider is available. Configure credentials once in Settings; provider selection stays here.","warn"));
  }
}

function renderApprovedSection(root){
  var approved=LP.state.approvedLeads||[];
  var card=LP.card([]);
  card.appendChild(LP.el("div",{className:"section-title"},[
    LP.el("div",{},[
      LP.el("h3",{text:"Approved leads"}),
      LP.el("p",{text:approved.length+" lead pronti alla preparazione della campagna."})
    ])
  ]));

  if(!approved.length){
    card.appendChild(LP.el("div",{className:"empty",text:"Nessun lead approvato. Approva i risultati qui sopra per abilitarli all'outreach."}));
    root.appendChild(card);
    return;
  }

  var table='<div class="table-wrap"><table class="table"><thead><tr><th>Company</th><th>Email</th><th>Score</th><th>Campaign</th></tr></thead><tbody>';
  approved.forEach(function(x){
    table+="<tr><td>"+LP.esc(x.company_name||"")+"</td><td>"+LP.esc(x.business_email||"")+"</td><td>"+Number(x.fit_score||0)+"/100</td><td>"+LP.esc(x.campaign_name||"—")+"</td></tr>";
  });
  table+="</tbody></table></div>";
  card.insertAdjacentHTML("beforeend",table);

  var campaignSelect=LP.el("select",{id:"out-campaign",className:"control"});
  campaignSelect.appendChild(LP.el("option",{value:"",text:"Crea automaticamente una nuova campagna"}));
  var campaigns=LP.state.outreachCampaigns||[];
  campaigns.forEach(function(c){
    campaignSelect.appendChild(LP.el("option",{value:String(c.id),text:c.name}));
  });

  var newName=LP.el("input",{
    id:"out-new-name",className:"input",
    placeholder:"Nome nuova campagna (es. Audit CRM Pro – Italia)"
  });

  var prepare=LP.button("Prepara per invio","btn-primary",async function(){
    prepare.disabled=true;
    try{
      var ids=approved.map(function(x){return Number(x.id)});
      var payload={
        product_id:Number(LP.state.productId),
        prospect_ids:ids
      };
      if(campaignSelect.value)payload.campaign_id=Number(campaignSelect.value);
      else payload.campaign_name=(newName.value||"").trim() || ("Auto · "+(LP.state.products.find(function(p){return Number(p.id)===Number(LP.state.productId)})||{}).name);
      var d=await LP.api("/api/orchestrator/prepare_outreach",{
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
      });
      LP.state.lastPreparedCampaign=d;
      LP.toast(d.prepared+" lead preparati per "+d.campaign,"good");
      await LP.loadPipeline();
      LP.drawFind();
    }catch(e){LP.toast(e.message,"error");prepare.disabled=false;}
  });

  card.appendChild(LP.el("div",{className:"grid two"},[
    LP.el("div",{className:"field"},[LP.el("label",{text:"Campagna"}),campaignSelect]),
    LP.el("div",{className:"field"},[LP.el("label",{text:"Nome nuova campagna"}),newName])
  ]));
  card.appendChild(LP.el("div",{className:"actions"},[prepare]));
  root.appendChild(card);
}

function renderSendSection(root){
  var approved=LP.state.approvedLeads||[];
  var prepared=approved.filter(function(x){return x.campaign_id});
  if(!prepared.length)return;

  var byCampaign={};
  prepared.forEach(function(x){
    var key=String(x.campaign_id);
    if(!byCampaign[key])byCampaign[key]={name:x.campaign_name,count:0};
    byCampaign[key].count++;
  });
  var card=LP.card([]);
  card.appendChild(LP.el("div",{className:"section-title"},[
    LP.el("div",{},[
      LP.el("h3",{text:"Invio"}),
      LP.el("p",{text:"L'invio resta sempre esplicito e richiede conferma."})
    ])
  ]));

  var campaignKeys=Object.keys(byCampaign);
  if(!campaignKeys.length)return;
  var sel=LP.el("select",{id:"send-campaign-inline",className:"control"});
  campaignKeys.forEach(function(k){
    sel.appendChild(LP.el("option",{value:k,text:byCampaign[k].name+" · "+byCampaign[k].count+" lead"}));
  });
  var limit=LP.el("input",{id:"send-limit-inline",className:"input",type:"number",value:String(byCampaign[campaignKeys[0]].count),min:"1"});
  sel.onchange=function(){
    var c=byCampaign[sel.value];
    limit.value=String(c?c.count:1);
  };
  var send=LP.button("✉ Invia lead approvati","btn-danger",async function(){
    var c=byCampaign[sel.value];
    if(!c)return;
    if(!confirm("Inviare "+Number(limit.value||c.count)+" lead della campagna «"+c.name+"» adesso?"))return;
    send.disabled=true;
    try{
      await LP.api("/api/send",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({campaign:c.name,limit:Number(limit.value||c.count)})
      });
      LP.toast("Invio avviato","good");
      await LP.loadPipeline();LP.drawFind();
    }catch(e){LP.toast(e.message,"error");send.disabled=false;}
  });

  card.appendChild(LP.el("div",{className:"grid two"},[
    LP.el("div",{className:"field"},[LP.el("label",{text:"Campagna pronta"}),sel]),
    LP.el("div",{className:"field"},[LP.el("label",{text:"Numero lead da inviare"}),limit])
  ]));
  card.appendChild(LP.el("div",{className:"actions"},[send]));
  root.appendChild(card);
}

LP.renderFind=async function(){
  var root=LP.$("#view-find");
  LP.page(root,"Trova clienti","Research → Approva → Campagna → Invia","Un solo percorso operativo. Le impostazioni tecniche restano fuori dal flusso.");
  try{
    await LP.loadProducts();
    await LP.loadSearchConfig();
    await LP.loadPipeline();

    var ready=LP.state.products.filter(function(p){return p.status==="READY"});
    if(!ready.length){
      root.appendChild(LP.note("Nessun prodotto READY. Crea e analizza prima un prodotto.","warn"));
      return;
    }

    var layout=LP.el("div",{className:"find-layout"});
    var side=LP.card([], "side-card");
    side.appendChild(LP.el("div",{className:"section-title"},[
      LP.el("div",{},[
        LP.el("h3",{text:"Prodotti"}),
        LP.el("p",{text:"Scegli il prodotto da cui partire."})
      ])
    ]));
    var list=LP.el("div",{className:"side-list"});
    ready.forEach(function(p){
      list.appendChild(LP.el("button",{
        className:"side-item "+(Number(p.id)===Number(LP.state.productId)?"active":""),
        onClick:function(){LP.state.productId=p.id;LP.renderFind();}
      },[LP.el("strong",{text:p.name}),LP.el("small",{text:"READY"})]));
    });
    side.appendChild(list);
    layout.appendChild(side);
    layout.appendChild(LP.el("div",{id:"find-main"}));
    root.appendChild(layout);

    LP.drawFind();
  }catch(e){
    root.appendChild(LP.note(e.message,"bad"));
  }
};

LP.drawFind=function(){
  var root=LP.$("#find-main");
  if(!root)return;
  LP.clear(root);

  var s=LP.state;
  var p=s.products.find(function(x){return Number(x.id)===Number(s.productId)});
  var status=s.pipeline?s.pipeline.campaign_status:"NOT_STARTED";
  var qualified=Number(s.pipeline?s.pipeline.qualified:0);
  var approved=(s.approvedLeads||[]).length;

  var providersCard=LP.card([]);
  providersCard.appendChild(LP.el("div",{className:"section-title"},[
    LP.el("div",{},[
      LP.el("h3",{text:"1. Come vuoi cercare?"}),
      LP.el("p",{text:"Puoi usare più motori contemporaneamente. La scelta vale solo per questa ricerca."})
    ])
  ]));
  providersCard.appendChild(LP.el("div",{id:"find-providers",className:"check-grid"}));
  providersCard.appendChild(LP.el("label",{className:"check-card ai-card"},[
    (function(){
      var cb=LP.el("input",{type:"checkbox",id:"find-ai",checked:true});
      cb.checked=LP.state.findAiEnabled!==false;
      cb.onchange=function(){LP.state.findAiEnabled=cb.checked};
      return cb;
    })(),
    LP.el("span",{},[LP.el("strong",{text:"AI qualification"}),LP.el("small",{text:"Genera il motivo del match e arricchisce la valutazione."})])
  ]));
  root.appendChild(providersCard);

  renderProviderChoices();

  var targetCard=LP.card([]);
  targetCard.appendChild(LP.el("div",{className:"section-title"},[
    LP.el("div",{},[
      LP.el("h3",{text:"2. Target della ricerca"}),
      LP.el("p",{text:"Lascia vuoto per usare automaticamente il profilo del prodotto."})
    ])
  ]));
  targetCard.appendChild(LP.el("div",{className:"grid two"},[
    field("find-role","Ruoli / buyer",s.findRole||"","CEO, CTO, Sales Director"),
    field("find-industry","Settore",s.findIndustry||"","B2B SaaS, cybersecurity"),
    field("find-location","Zona / città",s.findLocation||"","Milano, Toscana, Europa"),
    field("find-country","Paese",s.findCountry||"","Italy, Germany, UK")
  ]));
  root.appendChild(targetCard);

  var budget=LP.el("select",{id:"find-budget",className:"control"});
  [["50","50 risultati"],["150","150 risultati"],["300","300 risultati"],["500","500 risultati"]].forEach(function(v){
    budget.appendChild(LP.el("option",{value:v[0],text:v[1]}));
  });
  budget.value=s.findBudget||"150";

  var run=LP.button(status==="RUNNING"?"Ricerca in corso…":"🔎 AVVIA RICERCA","btn-good",async function(){
    var providers=selectedProviders();
    if(!providers.length){
      LP.toast("Seleziona almeno un motore di ricerca.","error");
      return;
    }
    s.findRole=LP.$("#find-role").value.trim();
    s.findIndustry=LP.$("#find-industry").value.trim();
    s.findLocation=LP.$("#find-location").value.trim();
    s.findCountry=LP.$("#find-country").value.trim();
    s.findBudget=budget.value;
    s.findAiEnabled=LP.$("#find-ai").checked;
    run.disabled=true;
    try{
      await LP.api("/api/orchestrator/auto_pilot",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({
          product_id:Number(s.productId),
          max_leads:Number(budget.value),
          providers:providers,
          ai_enabled:s.findAiEnabled,
          role:s.findRole,
          industry:s.findIndustry,
          location:s.findLocation,
          country:s.findCountry
        })
      });
      LP.toast("Ricerca avviata","good");
      LP.watchFind();
    }catch(e){LP.toast(e.message,"error");run.disabled=false;}
  });
  run.disabled=status==="RUNNING";

  var productCard=LP.card([
    LP.el("div",{className:"step-row"},[
      LP.el("div",{className:"step-label"},[
        LP.el("span",{className:"step-no",text:"01"}),
        LP.el("div",{},[
          LP.el("h3",{text:p?p.name:""}),
          LP.el("p",{text:"Prodotto pronto per la ricerca."})
        ])
      ]),
      LP.el("span",{className:"pill good",text:"READY"})
    ])
  ]);
  root.appendChild(productCard);

  root.appendChild(LP.card([
    LP.el("div",{className:"step-row"},[
      LP.el("div",{className:"step-label"},[
        LP.el("span",{className:"step-no",text:"03"}),
        LP.el("div",{},[
          LP.el("h3",{text:"Budget e avvio"}),
          LP.el("p",{text:"La ricerca crea/riusa automaticamente la campagna tecnica di discovery."})
        ])
      ]),
      budget
    ]),
    LP.el("div",{className:"actions"},[
      LP.el("span",{className:"muted small",text:status}),
      run
    ])
  ]));

  var metrics=LP.el("div",{className:"metrics"});
  [
    ["Trovati",s.pipeline?s.pipeline.discovered:0],
    ["Qualificati",qualified],
    ["Approvati",approved],
    ["Pronti invio",(s.approvedLeads||[]).filter(function(x){return !!x.campaign_id}).length]
  ].forEach(function(m){
    metrics.appendChild(LP.el("div",{className:"metric"},[LP.el("span",{text:m[0]}),LP.el("strong",{text:String(m[1])})]));
  });
  root.appendChild(LP.card([
    LP.el("div",{className:"section-title"},[
      LP.el("div",{},[
        LP.el("h3",{text:"4. Risultati"}),
        LP.el("p",{text:"Contatti trovati e qualificati dal motore corrente."})
      ])
    ]),
    metrics
  ]));

  if(qualified){
    var evid=LP.el("div",{className:"evidence"});
    var selectable=[];
    s.evidence.forEach(function(x){
      var reviewed=!!x.evidence_reviewed_at;
      if(!reviewed)selectable.push(x);
      evid.appendChild(LP.el("div",{className:"evidence-row"},[
        LP.el("div",{className:"evidence-main"},[
          reviewed?null:LP.el("input",{type:"checkbox",className:"evidence-check","data-id":String(x.id)}),
          LP.el("div",{},[
            LP.el("h4",{text:String(x.company_name||"")+" · "+Number(x.fit_score||0)+"/100"}),
            LP.el("p",{text:String(x.business_email||"")}),
            LP.el("p",{text:x.reason||"Match qualificato."})
          ])
        ]),
        reviewed?LP.el("span",{className:"pill good",text:"APPROVATO"}):LP.el("span",{className:"muted small",text:"Da approvare"})
      ]));
    });
    if(!s.evidence.length)evid.appendChild(LP.el("div",{className:"empty",text:"Nessun risultato qualificato."}));
    var approveSelected=LP.button("✓ Approva selezionati","btn-good",async function(){
      var ids=Array.from(root.querySelectorAll(".evidence-check:checked")).map(function(x){return Number(x.dataset.id)});
      if(!ids.length){LP.toast("Seleziona almeno un lead.","error");return;}
      approveSelected.disabled=true;
      try{
        await Promise.all(ids.map(function(id){return LP.reviewEvidence(id,"APPROVE")}));
        LP.toast(ids.length+" lead approvati","good");
        await LP.loadPipeline();LP.drawFind();
      }catch(e){LP.toast(e.message,"error");approveSelected.disabled=false;}
    });
    var approveAll=LP.button("✓ Approva tutti i risultati","btn-secondary",async function(){
      if(!selectable.length)return;
      if(!confirm("Approvare tutti i "+selectable.length+" risultati qualificati?"))return;
      approveAll.disabled=true;
      try{
        await Promise.all(selectable.map(function(x){return LP.reviewEvidence(x.id,"APPROVE")}));
        LP.toast(selectable.length+" lead approvati","good");
        await LP.loadPipeline();LP.drawFind();
      }catch(e){LP.toast(e.message,"error");approveAll.disabled=false;}
    });
    var card=LP.card([
      LP.el("div",{className:"section-title"},[
        LP.el("div",{},[
          LP.el("h3",{text:"5. Approva i lead"}),
          LP.el("p",{text:"L'approvazione è il tuo controllo umano prima dell'outreach."})
        ])
      ]),
      evid,
      LP.el("div",{className:"actions"},[approveSelected,approveAll])
    ]);
    root.appendChild(card);
  }

  renderApprovedSection(root);
  renderSendSection(root);

  root.appendChild(LP.card([
    LP.el("div",{className:"step-row"},[
      LP.el("div",{},[
        LP.el("h3",{text:"Area tecnica"}),
        LP.el("p",{text:"Settings e Advanced sono disponibili solo per configurazione e debug; non servono nel percorso normale."})
      ]),
      LP.button("Apri Advanced","btn-secondary",function(){LP.nav("advanced")})
    ])
  ]));
};

LP.reviewEvidence=async function(id,action){
  var reason=action==="REJECT"?(prompt("Motivo:","Non pertinente")||"Non pertinente"):"";
  return LP.api("/api/orchestrator/prospect/"+id+"/review",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action:action,reason:reason})
  });
};

LP.watchFind=function(){
  if(LP.state.poll)clearInterval(LP.state.poll);
  LP.state.poll=setInterval(async function(){
    try{
      await LP.loadPipeline();
      LP.drawFind();
      if(!LP.state.pipeline||LP.state.pipeline.campaign_status!=="RUNNING"){
        clearInterval(LP.state.poll);LP.state.poll=null;
      }
    }catch(e){}
  },3000);
};
})();