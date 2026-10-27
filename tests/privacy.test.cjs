const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const staticDir = path.join(__dirname, '../app/static');
function privacy() {
  const context = vm.createContext({URL});
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'privacy.js'), 'utf8'), context);
  return context.addressPrivacy;
}
test('screens IPv4 and IPv6 in text, including legacy messages and sentence punctuation', () => {
  const p = privacy();
  for (const ip of ['192.168.1.10', '2001:db8::10', '::1', '::ffff:192.0.2.1', 'fe80::1%eth0']) {
    assert.equal(p.screen(`Device at ${ip} failed.`), 'Device at [IP hidden] failed.');
  }
  assert.equal(p.screen('Try [2001:db8::1]:443 or 192.0.2.1:8000.'), 'Try [[IP hidden]]:443 or [IP hidden]:8000.');
});
test('preserves hostnames, device names, timestamps, and non-address numbers', () => {
  const p = privacy();
  const text = 'nas.local Router router-192.168.1.10.local 12:34:56 999.999.999.999';
  assert.equal(p.screen(text), text);
  assert.equal(p.isIP('nas.local'), false);
});
test('revealing is temporary and a new session always starts private', () => {
  const p = privacy();
  assert.equal(p.shown, false);
  p.setShown(true);
  assert.equal(p.screen('192.0.2.1'), '192.0.2.1');
  assert.equal(privacy().shown, false);
  p.setShown(false);
  assert.equal(p.screen('192.0.2.1'), '[IP hidden]');
});
function dashboard() {
  const elements = new Map();
  const events = {};
  const hosts = [{value:'192.0.2.1',type:'password'}, {value:'nas.local',type:'text'}];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {innerHTML:'',textContent:'',value:'',hidden:false,
      events:{}, attrs:{}, addEventListener(event, fn) {this.events[event] = fn;},
      setAttribute(name,value) {this.attrs[name] = value;}});
    return elements.get(id);
  }
  const context = vm.createContext({URL, URLSearchParams, console, Date, document:{getElementById:element,
    querySelectorAll:selector => selector === 'input[name="host"]' ? hosts : [],
    body:{classList:{remove(){},add(){}}}},
    window:{addEventListener:(event, fn) => {const previous=events[event]; events[event] = () => {if(previous) previous(); fn();};}},
    historyView:{render:(id, entries, timestamp, row) => {element(id).innerHTML = entries.map(row).join('');}},
    fetch:() => new Promise(() => {}), setInterval(){}, AbortSignal:{timeout(){return null;}}, location:{}});
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'privacy.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(staticDir, 'app.js'), 'utf8'), context);
  const data = {observer_instance:'first', local_user:'Owner', checking:false, batch_size:2,
    interval_seconds:15,confirmation_seconds:90,peers:[{id:'home', name:'Home', owner:'Owner',
      transport:'local',status:'healthy', advice:'Check 192.0.2.1.', can_recheck:true,
      availability:{state:'green',reachable:2,total:2}, incidents:[], targets:[
        {id:'one',name:'Router',host:'192.0.2.1',kind:'device',enabled:true,status:'healthy',method:'icmp', detail:'Reply from 192.0.2.1'},
        {id:'two',name:'NAS',host:'nas.local',kind:'device',enabled:true,status:'healthy',method:'icmp', detail:'Reply from 2001:db8::1'}]}],
    notifications:[{recipient:'Owner',created_at:0,message:'Router at 192.0.2.1 has failed.'}]};
  context.fixture = data;
  vm.runInContext('render(fixture)', context);
  return {context, element, hosts, events};
}
test('dashboard masks cards and old notifications, reveals on demand, and resets after server restart', () => {
  const {context,element,hosts} = dashboard();
  assert.ok(element('peers').innerHTML.includes('Router'));
  assert.ok(element('peers').innerHTML.includes('nas.local'));
  for (const id of ['peers','notifications']) assert.ok(!element(id).innerHTML.includes('192.0.2.1'));
  vm.runInContext('setAddressesShown(true)', context);
  assert.ok(element('peers').innerHTML.includes('192.0.2.1'));
  assert.equal(hosts[0].type, 'text');
  vm.runInContext("render({...fixture, observer_instance:'second'})", context);
  assert.ok(!element('peers').innerHTML.includes('192.0.2.1'));
  assert.equal(hosts[0].type, 'password');
  assert.equal(hosts[1].type, 'text');
  assert.equal(element('toggle-addresses').textContent, 'Show IP addresses');
});
test('settings preserve the real address while hiding it, and page restoration resets reveal', () => {
  const {context,events,element} = dashboard();
  const ipHTML = vm.runInContext("deviceFields({name:'Router',host:'192.0.2.1'})", context);
  assert.ok(ipHTML.includes('name="host" type="password" value="192.0.2.1"'));
  const dnsHTML = vm.runInContext("deviceFields({name:'NAS',host:'nas.local'})", context);
  assert.ok(dnsHTML.includes('name="host" type="text" value="nas.local"'));
  vm.runInContext("showError('Could not reach 192.0.2.1'); setAddressesShown(true)", context);
  events.pageshow();
  assert.equal(element('error').textContent, 'Could not reach [IP hidden]');
  assert.equal(context.addressPrivacy.shown, false);
});

test('external path addresses stay visible while monitored device addresses are screened', () => {
  const {context} = dashboard();
  const external = vm.runInContext("targetCard({name:'Cloudflare',host:'1.1.1.1',kind:'external',status:'healthy',method:'tcp',port:443,detail:'Reply from 1.1.1.1'})", context);
  assert.ok(external.includes('1.1.1.1:443'));
  assert.ok(external.includes('Reply from 1.1.1.1'));
  const device = vm.runInContext("targetCard({name:'Router',host:'192.0.2.1',kind:'device',status:'healthy',method:'icmp',detail:'Reply from 192.0.2.1'})", context);
  assert.ok(!device.includes('192.0.2.1'));
  vm.runInContext('setAddressesShown(true); setAddressesShown(false)', context);
  assert.equal(context.addressPrivacy.shown, false);
  const afterHide = vm.runInContext("targetCard({name:'Google DNS',host:'8.8.8.8',kind:'external',status:'healthy',method:'tcp',port:53})", context);
  assert.ok(afterHide.includes('8.8.8.8:53'));
});

test('existing host pairing accepts only complete HTTP(S) login links and does not rewrite hosts', () => {
  const {context} = dashboard();
  for (const link of ['http://nas.local:8000/login#key=abcd', 'https://192.0.2.1/login#key=abcd']) {
    context.link = link;
    assert.equal(vm.runInContext('existingHostLink(link)', context), link);
  }
  for (const link of ['javascript:alert(1)', 'file:///login#key=abcd', 'https://host/login',
      'https://user:password@host/login#key=abcd', 'https://host/login?key=abcd#key=abcd',
      'https://host/login#key=one&key=two', 'https://host/other#key=abcd']) {
    context.link = link;
    assert.throws(() => vm.runInContext('existingHostLink(link)', context));
  }
});
test('pairing and transfer inputs clear when a page is restored or hidden', () => {
  const {element,events} = dashboard();
  for (const event of ['pageshow','pagehide']) {
    for (const id of ['existing-pairing-link','transfer-key','transfer-file']) element(id).value='private';
    element('transfer-confirm').checked=true;
    events[event]();
    for (const id of ['existing-pairing-link','transfer-key','transfer-file']) assert.equal(element(id).value,'');
    assert.equal(element('transfer-confirm').checked,false);
  }
});
