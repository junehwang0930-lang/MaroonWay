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
    return {course,term:'2026-SPRING',section_count:1,sections:[{section,college:'AT',instructor_as_reported:'SMITH B',a:7,b:4,c:1,d:0,f:0,af_total:12,gpa_reported:3.5,q_count:0,enrollment_total:12,quality_status:'checks_passed'}]};
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
