"use client";

import {useState} from "react";
import {Bot,Send,UserRound,Sparkles,RotateCcw} from "lucide-react";

type Message={role:"assistant"|"user";content:string};
const suggestions=[
 "Summarise the bank's current customer growth opportunities.",
 "Which customer value segments should relationship managers prioritise?",
 "What are the main churn risk indicators in the portfolio?",
 "Prepare an executive summary of product opportunities."
];

export default function AssistantPage(){
 const [messages,setMessages]=useState<Message[]>([{role:"assistant",content:"Hello. I'm Samora Intelligence, your AI banking business intelligence assistant. I can help interpret the portfolio metrics currently available to the platform, explain growth opportunities and prepare management-level analysis. What would you like to investigate?"}]);
 const [question,setQuestion]=useState("");
 const [asking,setAsking]=useState(false);
 const [error,setError]=useState("");
 async function ask(value=question){
  const prompt=value.trim();if(prompt.length<8||asking)return;
  setMessages(current=>[...current,{role:"user",content:prompt}]);setQuestion("");setAsking(true);setError("");
  try{
   const response=await fetch("/api/growth/assistant",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:prompt})});
   const data=await response.json();if(!response.ok)throw new Error(data.error||"The AI employee could not complete this request.");
   setMessages(current=>[...current,{role:"assistant",content:data.answer||"No answer was returned."}]);
  }catch(e){setError(e instanceof Error?e.message:"Unable to reach the AI employee.");}
  finally{setAsking(false);}
 }
 function reset(){setMessages([{role:"assistant",content:"Conversation cleared. I'm ready to help with banking intelligence and portfolio analysis. What would you like to investigate?"}]);setError("");}
 return <div className="page-content">
  <div className="page-heading"><div><span className="eyebrow">SAMORA INTELLIGENCE</span><h1>AI Employee</h1><p className="muted">Your banking intelligence partner for customer growth, portfolio analysis and business decisions.</p></div><button className="btn btn-secondary" onClick={reset}><RotateCcw size={14}/>New conversation</button></div>
  <section className="panel" style={{maxWidth:1040,margin:"0 auto"}}>
   <div className="panel-heading"><div style={{display:"flex",alignItems:"center",gap:12}}><div style={{width:44,height:44,borderRadius:12,display:"grid",placeItems:"center",background:"#edf3f7",color:"#183b56"}}><Bot size={23}/></div><div><h2 className="panel-title">Samora Intelligence</h2><p className="panel-caption">AI Banking Intelligence Employee · Portfolio analysis</p></div></div><span className="status-pill status-active">Ready</span></div>
   <div aria-live="polite" style={{display:"flex",flexDirection:"column",gap:16,minHeight:300,maxHeight:520,overflowY:"auto",padding:"18px 4px"}}>
    {messages.map((message,index)=><div key={index} style={{display:"flex",gap:10,alignItems:"flex-start",flexDirection:message.role==="user"?"row-reverse":"row"}}>
     <div style={{width:32,height:32,flex:"0 0 32px",borderRadius:10,display:"grid",placeItems:"center",background:message.role==="user"?"#e9eef2":"#edf3f7",color:"#183b56"}}>{message.role==="user"?<UserRound size={17}/>:<Bot size={17}/>}</div>
     <div style={{maxWidth:"85%",padding:"12px 14px",borderRadius:12,background:message.role==="user"?"#f0f4f7":"#f7f9fa",whiteSpace:"pre-wrap",lineHeight:1.65,fontSize:14}}>{message.content}</div>
    </div>)}
    {asking&&<div style={{display:"flex",gap:10,alignItems:"center",color:"#687782",fontSize:13}}><Bot size={18}/>Analysing portfolio information…</div>}
   </div>
   {error&&<div className="governance-callout" role="alert">{error}</div>}
   <form onSubmit={e=>{e.preventDefault();void ask();}} style={{display:"flex",gap:10,alignItems:"stretch",marginTop:14}}>
    <textarea aria-label="Message Samora Intelligence" rows={2} value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void ask();}}} placeholder="Ask about customer behaviour, churn, growth opportunities or performance…" style={{flex:1,minWidth:0,padding:13,border:"1px solid #dce3e8",borderRadius:9,resize:"vertical",font:"inherit"}}/>
    <button className="btn" type="submit" disabled={asking||question.trim().length<8} aria-label="Send message"><Send size={16}/>Send</button>
   </form>
   <p className="muted small-note">Shift + Enter for a new line. Current answers use aggregate portfolio context only; individual customer and transaction investigation is a planned capability, not yet enabled.</p>
  </section>
  <section style={{maxWidth:1040,margin:"18px auto 0"}}><div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10,color:"#657581",fontSize:13,fontWeight:600}}><Sparkles size={15}/>SUGGESTED QUESTIONS</div><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:10}}>{suggestions.map(item=><button key={item} type="button" className="panel" onClick={()=>void ask(item)} disabled={asking} style={{textAlign:"left",padding:14,cursor:"pointer",font:"inherit",color:"inherit"}}>{item}</button>)}</div></section>
 </div>;
}
