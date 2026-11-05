const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function deferred() {
    let resolve, reject;
    const promise = new Promise((a,b) => { resolve=a; reject=b; });
    return {promise, resolve, reject};
}
class Element {
    constructor() { this.children=[]; this.listeners={}; this.style={}; this.value=''; this.textContent=''; }
    appendChild(child) { this.children.push(child); }
    replaceChildren() { this.children=[]; }
    setAttribute() {}
    addEventListener(name, callback) { this.listeners[name]=callback; }
    close() {}
    showModal() {}
}
function harness() {
    const nodes=new Map();
    const get=id => { if(!nodes.has(id)) nodes.set(id,new Element()); return nodes.get(id); };
    const calls=[];
    const document={querySelector:get, querySelectorAll:()=>[],createElement:()=>new Element()};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../frontend/app.js'),'utf8'),{
        document, AbortController, Map, fetch: (url, options) => {
            const item=deferred();calls.push({...item,url,options});return item.promise;
        }
    });
    get('#subject').value='STAT';get('#number').value='211';get('#term').value='2026-SPRING';
    return {get,calls,search:()=>get('#search-form').listeners.submit({preventDefault(){}})};
}
function data(course,section='200') {
    return {course,term:'2026-SPRING',section_count:1,sections:[{section,college:'AT',instructor_as_reported:'SMITH B',a:7,b:4,c:1,d:0,f:0,af_total:12,gpa_reported:3.5,gpa_calculated:3.5,gpa_difference:0,gpa_discrepancy:false,q_count:0,enrollment_total:12,quality_status:'checks_passed'}]};
}
const ok=body=>({ok:true,json:async()=>body});

test('only latest response can render results when responses arrive out of order',async()=>{
    const h=harness();const old=h.search();h.get('#number').value='201';const latest=h.search();
    h.calls[1].resolve(ok(data('STAT 201')));await latest;
    h.calls[0].resolve(ok(data('STAT 211')));await old;
    assert.match(h.get('#message').textContent,/STAT 201/);
    assert.equal(h.get('#results').children.length,1);
});

test('stale error cannot replace the current search status',async()=>{
    const h=harness();const old=h.search();const latest=h.search();
    h.calls[1].resolve(ok(data('STAT 201')));await latest;
    h.calls[0].reject(new Error('old request failed'));await old;
    assert.match(h.get('#message').textContent,/STAT 201/);
});

test('delayed JSON from an old response cannot mutate latest state',async()=>{
    const h=harness();const body=deferred();const old=h.search();
    h.calls[0].resolve({ok:true,json:()=>body.promise});await Promise.resolve();
    const latest=h.search();h.calls[1].resolve(ok(data('STAT 201')));await latest;
    body.resolve(data('STAT 211'));await old;
    assert.match(h.get('#message').textContent,/STAT 201/);
    assert.equal(h.get('#results').children.length,1);
});

test('current errors remain visible and prior request is cancelled',async()=>{
    const h=harness();const old=h.search();const latest=h.search();
    h.calls[1].reject(new Error('current failure'));await latest;
    h.calls[0].resolve(ok(data('STAT 211')));await old;
    assert.equal(h.get('#message').textContent,'current failure');
    assert.equal(h.calls[0].options?.signal.aborted,true);
});


async function showSections(sections) {
    const h=harness();
    const pending=h.search();
    const response=data('STAT 211');
    response.sections=sections;
    response.section_count=sections.length;
    h.calls[0].resolve(ok(response));
    await pending;
    return h;
}
const rowValues=row=>row.children.map(cell=>cell.textContent);

test('calculated GPA is primary while a reported zero and its discrepancy remain visible',async()=>{
    const section={...data('STAT 211').sections[0],a:12,b:0,c:0,gpa_calculated:4,gpa_reported:0,gpa_difference:4,gpa_discrepancy:true};
    const h=await showSections([section]);
    assert.deepEqual(rowValues(h.get('#results').children[0]).slice(3,7),
        ['4.000','0.000','4.000','Difference flagged']);
});

test('zero A-F enrollment displays N/A instead of a zero calculated GPA',async()=>{
    const section={...data('STAT 211').sections[0],a:0,b:0,c:0,af_total:0,gpa_calculated:null,gpa_reported:0,gpa_difference:null,gpa_discrepancy:false};
    const h=await showSections([section]);
    assert.deepEqual(rowValues(h.get('#results').children[0]).slice(3,7),
        ['N/A','0.000','N/A','N/A']);
});

test('comparison shows calculated, original, difference, and discrepancy for both sections',async()=>{
    const left={...data('STAT 211').sections[0],gpa_calculated:4,gpa_reported:0,gpa_difference:4,gpa_discrepancy:true};
    const right={...data('STAT 211','201').sections[0],gpa_calculated:3.5,gpa_reported:3.5,gpa_difference:0,gpa_discrepancy:false};
    const h=await showSections([left,right]);
    for(const row of h.get('#results').children) {
        const checkbox=row.children[0].children[0];
        checkbox.checked=true;
        checkbox.listeners.change();
    }
    h.get('#compare-button').listeners.click();
    const rows=h.get('#compare-results').children.map(rowValues);
    assert.deepEqual(rows.slice(1,5),[
        ['MaroonWay GPA (A-F based)','4.000','3.500'],
        ['TAMU Reported GPA','0.000','3.500'],
        ['Absolute GPA Difference','4.000','0.000'],
        ['GPA Discrepancy','Difference flagged','No difference flagged']
    ]);
});

test('GPA columns and explanation distinguish the calculation from official GPA',()=>{
    const html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8');
    assert.match(html,/<th>MaroonWay GPA \(A-F based\)<\/th>/);
    assert.match(html,/<th>TAMU Reported GPA<\/th>/);
    assert.match(html,/<th>Absolute GPA Difference<\/th>/);
    assert.match(html,/<th>GPA Discrepancy<\/th>/);
    assert.match(html,/variable or zero credit hours/);
    assert.match(html,/not a guaranteed measure of course difficulty/);
});


test('absolute GPA difference stays positive when TAMU reported GPA is higher',async()=>{
    const section={...data('STAT 211').sections[0],gpa_calculated:3.8,gpa_reported:4,gpa_difference:0.2,gpa_discrepancy:true};
    const h=await showSections([section]);
    assert.equal(rowValues(h.get('#results').children[0])[5],'0.200');
    const html=fs.readFileSync(path.join(__dirname,'../frontend/index.html'),'utf8');
    assert.match(html,/<th>Absolute GPA Difference<\/th>/);
});
