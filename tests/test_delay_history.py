import base64
import json

import pytest

from app.migration import cipher, export_data, restore_data
from app.monitor import Monitor
from app.notify import DestinationInput, Notifier
from app.presence import month_bounds, report, summarize
from app.store import Store
from app.transport import Result
from test_migration import fresh_settings


def test_delay_observations_survive_raw_pruning_and_capture_original_threshold(settings, tmp_path):
    store=Store(tmp_path/'history.db')
    peer=settings.peers[0]; device=peer.targets[0]
    start,_=month_bounds('2026-10')
    for offset,ms in [(1,1043.33),(2,1023.62),(3,120.0)]:
        store.record(peer,device,Result('delayed',ms),start+offset,90,60)
    device.delayed_ms=500
    device.name='Renamed device'
    store.record(peer,device,Result('delayed',700),start+4,90,60)
    store.record(peer,device,Result('healthy',1),start+5,90,60)
    # An external-path delay and a disabled placeholder are excluded.
    store.record(peer,peer.targets[2],Result('delayed',1000),start+6,90,60)
    device.enabled=False
    store.record(peer,device,Result('delayed',1000),start+7,90,60)
    device.enabled=True
    store.prune(start+100,summary_cutoff=start-1)
    assert not store.db.execute('SELECT 1 FROM samples').fetchone()
    store.close()
    store=Store(tmp_path/'history.db')
    d=report(store,'home','2026-10',start+100)['delays']
    assert d['count']==4 and d['worst_ms']==1043.33
    assert d['devices'][0]['average_ms']==721.74
    assert d['devices'][0]['name']=='Renamed device'
    assert d['recent'][0]['threshold_ms']==500
    assert d['recent'][-1]['threshold_ms']==100
    assert d['recent'][-1]['name']=='One'
    assert store.incidents('home')==[]
    assert summarize([dict(kind='device',enabled=True,status='delayed')])['state']=='green'
    store.prune(start+100,summary_cutoff=start+3)
    assert report(store,'home','2026-10',start+100)['delays']['count']==2
    store.close()


def test_month_boundaries_future_observations_and_full_totals_with_bounded_preview(settings,tmp_path):
    store=Store(tmp_path/'months.db');p=settings.peers[0];t=p.targets[0]
    start,end=month_bounds('2026-10')
    for now in [start-1,*range(int(start),int(start)+75),end,end+1]:
        store.record(p,t,Result('delayed',200),now,90,60)
    d=report(store,'home','2026-10',start+74)['delays']
    assert d['count']==75 and len(d['recent'])==50
    assert report(store,'home','2026-10',start+10)['delays']['count']==11
    assert report(store,'home','2026-10',end+10)['delays']['count']==75
    assert report(store,'home','2026-11',end+10)['delays']['count']==2
    assert report(store,'other','2026-10',end+10)['delays']['count']==0
    store.close()


@pytest.mark.anyio
async def test_provider_monthly_summary_includes_delays_without_creating_immediate_alerts(settings,tmp_path):
    store=Store(tmp_path/'monthly.db');p=settings.peers[0];t=p.targets[0]
    start,end=month_bounds('2026-10')
    store.record(p,t,Result('delayed',1043.33),start+100,90,60)
    # Supply known availability so the existing monthly report is eligible.
    store.db.execute("INSERT INTO availability(group_id,start,end,expires,state,reachable,total) VALUES(?,?,?,?,?,?,?)",('home',start,start+100,start+200,'green',2,2))
    store.db.commit()
    n=Notifier(store,clock=lambda:end+100)
    await n.configure(DestinationInput(provider='slack',enabled=True,monthly=True,secret='https://hooks.slack.com/services/test/delay/report'))
    n.collect(settings);n.collect(settings)
    rows=store.db.execute('SELECT * FROM deliveries').fetchall()
    assert len(rows)==1 and rows[0]['event_key'].startswith('month:')
    assert 'Delayed checks 1; worst 1043.33 ms' in rows[0]['message']
    assert store.notifications(['home'],'owner')==[]
    store.close()


def test_delay_history_transfers_and_old_transfer_files_still_restore(settings,tmp_path):
    store=Store(tmp_path/'source.db');m=Monitor(settings,store);n=Notifier(store)
    store.record(settings.peers[0],settings.peers[0].targets[0],Result('delayed',1043.33),100,90,60)
    archive=export_data(m,n,'a'*32)
    for legacy in [False,True]:
        envelope=json.loads(archive)
        if legacy:
            c=cipher('a'*32,base64.b64decode(envelope['salt']))
            payload=json.loads(c.decrypt(envelope['data'].encode()))
            payload['version']=1
            for table in ['delay_events','delay_log_info']:del payload['tables'][table]
            envelope['data']=c.encrypt(json.dumps(payload).encode()).decode()
        dst=Store(tmp_path/f'destination-{legacy}.db');dm=Monitor(fresh_settings(),dst);dn=Notifier(dst)
        restore_data(dm,dn,json.dumps(envelope),'a'*32,tmp_path/f'config-{legacy}.json')
        assert dst.db.execute('SELECT COUNT(*) FROM delay_events').fetchone()[0]==(0 if legacy else 1)
        dst.close()
    store.close()


def test_existing_database_upgrades_without_inventing_prior_delays(settings,tmp_path):
    path=tmp_path/'legacy.db';store=Store(path)
    p=settings.peers[0];t=p.targets[0]
    start,_=month_bounds('2026-10')
    store.record(p,t,Result('delayed',1043),start+1,90,60)
    store.db.executescript('DROP TABLE delay_events; DROP TABLE delay_log_info;')
    store.close()
    store=Store(path)
    assert store.latest('home','one')['latency_ms']==1043
    assert report(store,'home','2026-10',start+100)['delays']['count']==0
    assert report(store,'home','2026-10',start+100)['delays']['logging_started_at'] is None
    store.record(p,t,Result('delayed',1024),start+2,90,60)
    data=report(store,'home','2026-10',start+100)['delays']
    assert data['count']==1 and data['logging_started_at']==start+2
    store.close()
