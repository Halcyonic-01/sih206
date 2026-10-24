// Isolated component tests. No app shell, browser, real auth or HTTP assertions.
const assert = require('node:assert/strict');
const path = require('node:path');
const {createRequire} = require('node:module');
const runtime = path.resolve(process.argv[2] || 'data/saksham-ui-tools');
const local = createRequire(path.join(runtime, 'package.json'));
const React = local('react');
const {create} = local('react-test-renderer');
const {act} = React;
const types = require(path.join(runtime, 'build/client.js'));
const institutions = require(path.join(runtime, 'build/institutions.js'));
const releases = require(path.join(runtime, 'build/releases.js'));
const reports = require(path.join(runtime, 'build/reports.js'));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const views = [];
const text = tree => JSON.stringify(tree.toJSON());
const click = (tree, label) => tree.root.findAllByType('button').find(b => b.children.join('') === label);
const baseCase = {id:1,version:1,instrument_version:5,status:'APPROVED',path:'TERM_COMPLETE',mode:'FDR',monitoring_active:true,
  next_action:'Separate evidence-backed completion',readiness:null,actions:{},clearances:[],penalties:[],penalty_review_complete:true,letter:null};
const noopClient = {get:async()=>({}),post:async()=>({}),download:async()=>{}};
async function mount(component, props) {
  let tree; await act(async()=>{tree=create(React.createElement(component, props));}); views.push(tree); return tree;
}
async function test(name, action) {await action();console.log('PASS '+name);}

(async()=>{
  await test('integer money, nulls and exact INR parsing',async()=>{
    assert.equal(types.money(null),'Unavailable');assert.equal(types.money(0),'INR 0.00');
    assert.equal(types.money(50000025),'INR 5,00,000.25');assert.equal(types.money(1.5),'Unavailable');
    assert.equal(types.paise('123.45'),12345);
    assert.equal(types.money('9007199254740993'),'INR 9,00,71,99,25,47,409.93');
    for(const input of ['1.234','1e3','-1','0','9007199254740992'])assert.throws(()=>types.paise(input));
  });
  await test('strict separate public record allowlist',async()=>{
    const record={serial:'SYNTH-X',issue_date:'2026-10-24',institution_name:'Synthetic A',kind:'NOC',status:'ISSUED'};
    assert.deepEqual(types.publicRecord(record),record);
    assert.throws(()=>types.publicRecord({...record,monitoring_active:true}));
    assert.throws(()=>types.publicRecord({...record,status:'VALID'}));
  });
  await test('approval remains monitored and completion pending',async()=>{
    const tree=await mount(releases.ReleaseCase,{client:{...noopClient,get:async()=>baseCase},identityKey:'authority',caseId:1});
    assert.match(text(tree),/Release authorized; completion pending/);assert.match(text(tree),/Active/);
    assert.equal(click(tree,'Record evidence-backed completion'),undefined);
  });
  await test('ready does not grant an authority action',async()=>{
    const item={...baseCase,status:'PENDING',readiness:{outcome:'READY_FOR_AUTHORITY_REVIEW'}};
    const tree=await mount(releases.ReleaseCase,{client:{...noopClient,get:async()=>item},identityKey:'officer',caseId:1});
    assert.match(text(tree),/no approval recorded/);assert.equal(click(tree,'Record authority authorization'),undefined);
  });
  await test('service failure has no synthetic fallback',async()=>{
    const tree=await mount(releases.ReleaseCase,{client:{...noopClient,get:async()=>{throw {status:503};}},identityKey:'officer',caseId:1});
    assert.match(text(tree),/Service unavailable/);assert.doesNotMatch(text(tree),/SYNTH-|Saved status/);
  });
  await test('old identity response cannot populate new screen',async()=>{
    let first,second;let count=0;
    const client={...noopClient,get:()=>new Promise(resolve=>{if(count++===0)first=resolve;else second=resolve;})};
    const tree=await mount(institutions.InstitutionList,{client,identityKey:'A',onSelect:()=>{}});
    await act(async()=>{tree.update(React.createElement(institutions.InstitutionList,{client,identityKey:'B',onSelect:()=>{}}));});
    await act(async()=>{second({count:1,results:[{id:2,name:'Only B',code:'B'}]});});
    await act(async()=>{first({count:1,results:[{id:1,name:'Secret A',code:'A'}]});});
    assert.match(text(tree),/Only B/);assert.doesNotMatch(text(tree),/Secret A/);
  });
  await test('missing canonical questionnaire blocks wizard',async()=>{
    let posts=0;
    const tree=await mount(releases.ReleaseWizard,{client:{...noopClient,post:async()=>{posts++;}},identityKey:'institution',
      inputs:{instrumentId:1,obligationId:1,instrumentVersion:1,canRequest:true,documentsReady:true,documents:null},onCreated:()=>{}});
    await act(async()=>{tree.root.findByType('textarea').props.onChange({target:{value:'Synthetic request'}});});
    await act(async()=>{click(tree,'Next').props.onClick();});
    assert.match(text(tree),/Declaration template unavailable/);assert.equal(click(tree,'Next').props.disabled,true);assert.equal(posts,0);
  });
  await test('mutation projection is ignored in favour of refreshed saved state',async()=>{
    let writes=0;let saved={...baseCase,status:'PENDING',actions:{can_approve:true}};
    const client={...noopClient,get:async()=>saved,post:async()=>{writes++;saved=baseCase;return {case_status_after_action:'COMPLETED',monitoring_after_action:false};}};
    const tree=await mount(releases.ReleaseCase,{client,identityKey:'authority',caseId:1});
    await act(async()=>{tree.root.findByType('textarea').props.onChange({target:{value:'Independent review'}});});
    await act(async()=>{await click(tree,'Record authority authorization').props.onClick();});
    assert.equal(writes,1);assert.match(text(tree),/APPROVED/);assert.match(text(tree),/Active/);assert.doesNotMatch(text(tree),/COMPLETED/);
  });
  await test('revoked public record has no private links',async()=>{
    const tree=await mount(releases.PublicVerification,{client:{...noopClient,get:async()=>({serial:'SYNTH-X',issue_date:'2026-10-24',institution_name:'Synthetic',kind:'NOC',status:'REVOKED'})},token:'synthetic-token'});
    assert.match(text(tree),/Revoked/);assert.equal(tree.root.findAllByType('a').length,0);assert.doesNotMatch(text(tree),/monitoring|refund_reference/);
  });
  await test('public not-found differs from service failure',async()=>{
    for(const status of [404,503]){
      const tree=await mount(releases.PublicVerification,{client:{...noopClient,get:async()=>{throw {status};}},token:'synthetic-token'});
      assert.match(text(tree),status===404?/Verification record unavailable/:/Verification service temporarily unavailable/);
    }
  });
  await test('KPI does not fetch an unspecified cohort',async()=>{
    let reads=0;await mount(reports.Kpis,{client:{...noopClient,get:async()=>{reads++;return {};}},identityKey:'officer'});assert.equal(reads,0);
  });
  for(const tree of views)await act(async()=>tree.unmount());
  console.log(JSON.stringify({tests:11,passed:11,failed:0,browser_tests:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
