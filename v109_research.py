"""V1.09.1 independent research collector; no orders, market API or push credentials."""
import argparse
import csv
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen

VERSION = '1.09.1'
TASK = 'AI-Daytrade-V109-Research'
BASE_TASK = 'AI-Daytrade-V108-Shadow'
TW = timezone(timedelta(hours=8))
PROJECT = Path(__file__).resolve().parent
PRIVATE = Path.home() / '.ai-daytrade-private'
LOCAL = PRIVATE / 'v109-research'
POLICY_URL = 'https://raw.githubusercontent.com/lishengchen01/ai-daytrade/main/v109/research_policy.json'
DEFAULT = {'revision': 1, 'window_days': 14, 'focus': 'balanced'}
FOCUSES = {'balanced', 'scan_health', 'filter_diagnostics', 'push_reliability'}
STATUSES = {'completed', 'outside_session', 'blocked_or_error', 'outside_market'}
COUNTS = ('qualified_count', 'requests', 'push_ready_count', 'attempted_alerts', 'notifications_sent')
GATES = {'盤後初篩候選數', '策略未通過：跳空幅度未達2至4%', '策略未通過：首根K方向', '量能不足'}


def now():
    return datetime.now(TW)


def read_json(path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def atomic(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        name = f.name
        try:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            Path(name).unlink(missing_ok=True)
            raise
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def integer(v):
    return v if type(v) is int and 0 <= v <= 100000 else None


def normalize(obj):
    if not isinstance(obj, dict) or obj.get('version') != 'V1.08.2-shadow':
        return None
    try:
        t = datetime.fromisoformat(obj['checked_at'])
        if t.tzinfo is None:
            return None
        t = t.astimezone(TW)
        if t > now() + timedelta(minutes=2):
            return None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if obj.get('status') not in STATUSES:
        return None
    row = {'checked_at': t.isoformat(), 'status': obj['status']}
    row.update({k: integer(obj.get(k)) for k in COUNTS})
    g = obj.get('gate_counts')
    row['gates'] = {k: integer(v) for k, v in g.items() if k in GATES and integer(v) is not None} if isinstance(g, dict) else {}
    # Other anonymous gate counts are counted but their arbitrary keys are never exported.
    row['other_gate_total'] = sum(integer(v) or 0 for k, v in g.items() if k not in GATES) if isinstance(g, dict) else 0
    return row


def import_history(db, private):
    for name in ('shadow-v108-history.previous.jsonl', 'shadow-v108-history.jsonl', 'shadow-v108-status.json'):
        p = private / name
        if not p.is_file():
            continue
        if name.endswith('.jsonl'):
            with p.open('r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    try:
                        row = normalize(json.loads(line))
                    except (ValueError, TypeError):
                        continue
                    if row and row['status'] != 'outside_session':
                        db.execute('INSERT OR IGNORE INTO scans VALUES (?, ?)', (row['checked_at'], json.dumps(row, ensure_ascii=False)))
        else:
            try:
                row = normalize(read_json(p))
                if row and row['status'] != 'outside_session':
                    db.execute('INSERT OR IGNORE INTO scans VALUES (?, ?)', (row['checked_at'], json.dumps(row, ensure_ascii=False)))
            except (OSError, ValueError, TypeError):
                pass


def valid_policy(p):
    return (isinstance(p, dict) and set(p) == set(DEFAULT) and type(p['revision']) is int
            and 1 <= p['revision'] <= 100000 and type(p['window_days']) is int
            and p['window_days'] in (7, 14, 30) and isinstance(p['focus'], str) and p['focus'] in FOCUSES)


def policy_update(local, fetch=True):
    path = local / 'policy.json'
    try:
        current = read_json(path)
        if not valid_policy(current):
            raise ValueError('invalid local policy')
    except FileNotFoundError:
        current = DEFAULT.copy()
        atomic(path, current)
    changed = False
    state = 'offline'
    if fetch:
        try:
            with urlopen(POLICY_URL, timeout=8) as response:
                if response.geturl() != POLICY_URL:
                    raise ValueError('unexpected redirect')
                raw = response.read(4097)
            if len(raw) > 4096:
                raise ValueError('oversize policy')
            candidate = json.loads(raw)
            if not valid_policy(candidate):
                raise ValueError('invalid remote policy')
            if candidate['revision'] > current['revision']:
                atomic(local / 'policy.previous.json', current)
                # Only data, never executable code or a production strategy setting.
                atomic(path, candidate)
                current = candidate
                changed = True
            elif candidate['revision'] == current['revision'] and candidate != current:
                raise ValueError('same revision changed')
            state = 'ok' if candidate['revision'] >= current['revision'] else 'older_ignored'
        except (OSError, ValueError, TypeError):
            state = 'unavailable_or_rejected'
    return current, changed, state


def report(local, private, project, fetch=True):
    local.mkdir(parents=True, exist_ok=True)
    policy, changed, update_state = policy_update(local, fetch)
    with closing(sqlite3.connect(local / 'research.sqlite3', timeout=15)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS scans (checked_at TEXT PRIMARY KEY, data TEXT NOT NULL)')
        import_history(db, private)
        db.execute('DELETE FROM scans WHERE checked_at < ?', ((now() - timedelta(days=180)).isoformat(),))
        rows = [json.loads(x[0]) for x in db.execute('SELECT data FROM scans WHERE checked_at >= ? ORDER BY checked_at', ((now()-timedelta(days=policy['window_days'])).isoformat(),))]
    completed = [r for r in rows if r['status'] == 'completed']
    errors = sum(r['status'] == 'blocked_or_error' for r in rows)
    gate_totals = {k: sum(r['gates'].get(k, 0) for r in completed) for k in sorted(GATES)}
    attempts = sum(r['attempted_alerts'] or 0 for r in completed)
    accepted = sum(r['notifications_sent'] or 0 for r in completed)
    # Deterministic research recommendation, not an optimization of trading parameters.
    focus = policy['focus']
    if not completed or errors:
        focus = 'scan_health'
    elif attempts > accepted:
        focus = 'push_reliability'
    elif focus == 'balanced':
        focus = 'filter_diagnostics'
    summary = {'version': VERSION, 'policy_revision': policy['revision'], 'window_days': policy['window_days'],
               'scan_records': len(rows), 'completed_scans': len(completed), 'blocked_or_error_scans': errors,
               'count_totals': {k: sum(r[k] or 0 for r in completed) for k in COUNTS},
               'known_gate_totals': gate_totals, 'other_gate_total': sum(r['other_gate_total'] for r in completed),
               'next_research_focus': focus, 'performance_measured': False,
               'note': 'Counts are scan totals, not unique signals, trades, returns or win rates.'}
    atomic(local / 'research_summary.json', summary)
    # Explicitly local research file; never copied to Drive by this program.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='', dir=local, delete=False) as f:
        csv_name = f.name
        w = csv.DictWriter(f, fieldnames=['checked_at', 'status', *COUNTS, 'other_gate_total'])
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in w.fieldnames})
    try:
        os.replace(csv_name, local / 'research_scans.csv')
    finally:
        Path(csv_name).unlink(missing_ok=True)
    try:
        status = normalize(read_json(private / 'shadow-v108-status.json'))
    except (OSError, ValueError, TypeError):
        status = None
    age = (now()-datetime.fromisoformat(status['checked_at'])).total_seconds() if status else None
    # Cloud allowlist: operational health only; no tickers, prices, per-scan counts, gate totals or secrets.
    health = {'collector_version': VERSION, 'checked_at': now().isoformat(),
              'scanner_status': status['status'] if status else 'unknown',
              'scanner_recent': age is not None and 0 <= age <= 660,
              'scanner_version': 'V1.08.2-shadow' if status else 'unknown',
              'authorization_file_present': (private / 'v1082-private-notify.json').is_file(),
              'policy_revision': policy['revision'], 'policy_check': update_state,
              'research_focus': policy['focus'], 'cloud_scope': 'operational_metadata_only'}
    # Recover event after an interruption between policy write and event write.
    event_path = local / 'latest_update.json'
    try:
        event = read_json(event_path)
    except (OSError, ValueError, TypeError):
        event = {}
    if policy['revision'] > 1 and (changed or not isinstance(event, dict) or event.get('policy_revision') != policy['revision']):
        atomic(event_path, {'collector_version': VERSION, 'policy_revision': policy['revision'], 'focus': policy['focus'], 'applied_at': now().isoformat(), 'scope': 'research_only'})
    atomic(local / 'collector_status.json', health)
    return health


def drive_root():
    # Accept only an existing project directory under an actual mounted My Drive.
    if os.name != 'nt':
        return None
    matches = []
    for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
        for label in ('My Drive', '我的雲端硬碟', '我的雲端硬碟 (My Drive)'):
            p = Path(letter + ':/' + label) / 'AI_Daytrade_APP_Research'
            if p.is_dir():
                matches.append(p)
    return matches[0] if len(matches) == 1 else None


def sync(local, health):
    target = drive_root()
    if target is None:
        return 'drive_folder_not_found_or_ambiguous'
    atomic(target / 'collector_status.json', health)
    update = local / 'latest_update.json'
    if update.is_file():
        obj = read_json(update)
        if (isinstance(obj, dict) and set(obj) == {'collector_version','policy_revision','focus','applied_at','scope'}
                and obj['scope'] == 'research_only' and obj['collector_version'] == VERSION
                and type(obj['policy_revision']) is int and obj['focus'] in FOCUSES):
            # Reconstruct from allowed values, no arbitrary payload forwarded.
            stamp = datetime.fromisoformat(obj['applied_at'])
            atomic(target / 'latest_update.json', {'collector_version': VERSION, 'policy_revision': obj['policy_revision'], 'focus': obj['focus'], 'applied_at': stamp.astimezone(TW).isoformat(), 'scope': 'research_only'})
    return 'written_to_local_drive_mount'


def task(*args):
    return subprocess.run(['schtasks.exe', *args], capture_output=True, timeout=30)


def task_text(raw):
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')) or b'\x00' in raw[:100]:
        return raw.decode('utf-16', errors='replace')
    return raw.decode('mbcs', errors='replace')


def install():
    if os.name != 'nt':
        raise RuntimeError('Windows only')
    if not (PROJECT / 'v108' / 'start_hidden.py').is_file():
        raise RuntimeError('Place this script in the existing ai-daytrade-main directory')
    q = task('/Query','/TN',BASE_TASK,'/XML')
    if q.returncode or str(PROJECT / 'v108' / 'start_hidden.py').casefold() not in task_text(q.stdout).casefold():
        raise RuntimeError('Existing V108 scanner task does not match this project')
    health = report(LOCAL, PRIVATE, PROJECT)
    cloud = sync(LOCAL, health)
    q = task('/Query','/TN',TASK,'/XML')
    if q.returncode == 0:
        if str(Path(__file__).resolve()).casefold() not in task_text(q.stdout).casefold():
            raise RuntimeError('Research task already exists at a different path')
    else:
        runner = Path(sys.executable).with_name('pythonw.exe')
        if not runner.is_file():
            raise RuntimeError('pythonw.exe missing')
        action = subprocess.list2cmdline([str(runner), '-B', str(Path(__file__).resolve()), 'run'])
        user = subprocess.check_output(['whoami.exe'], timeout=10).decode('mbcs').strip()
        p = task('/Create','/TN',TASK,'/SC','MINUTE','/MO','15','/TR',action,'/RU',user,'/IT','/RL','LIMITED')
        if p.returncode:
            raise RuntimeError('Research task registration failed')
    atomic(LOCAL / 'sync_status.json', {'checked_at':now().isoformat(),'drive_sync':cloud})
    print('INSTALL_OK V'+VERSION)
    print('DRIVE_SYNC='+cloud)
    print('SCANNER_RECENT='+str(health['scanner_recent']))
    print('POLICY_REVISION='+str(health['policy_revision']))
    print('Original scanner, alerts, strategy and credentials unchanged.')


def selftest():
    import unittest
    from unittest.mock import patch
    from io import BytesIO
    class FakeResponse(BytesIO):
        def geturl(self): return POLICY_URL
    class Tests(unittest.TestCase):
        def test_policy_reject_code_or_strategy(self):
            self.assertFalse(valid_policy(dict(DEFAULT, code='run')))
            self.assertFalse(valid_policy(dict(DEFAULT, live=True)))
            self.assertFalse(valid_policy(dict(DEFAULT, revision=True)))
            self.assertTrue(valid_policy(DEFAULT))
        def test_update_and_rollback_rejection(self):
            with tempfile.TemporaryDirectory() as t:
                p = Path(t)
                for rev in (2, 1):
                    with patch(__name__+'.urlopen', return_value=FakeResponse(json.dumps(dict(DEFAULT,revision=rev)).encode())):
                        c, changed, state = policy_update(p)
                        self.assertEqual(c['revision'],2)
                        self.assertEqual(changed, rev==2)
                self.assertEqual(read_json(p/'policy.previous.json')['revision'],1)
        def test_history_dedup_and_cloud_privacy(self):
            with tempfile.TemporaryDirectory() as t:
                p=Path(t); private=p/'private'; local=p/'research'; cloud=p/'drive'; private.mkdir(); cloud.mkdir()
                raw={'version':'V1.08.2-shadow','checked_at':now().isoformat(),'status':'completed','qualified_count':2,'symbol':'SECRET6148','api_key':'SECRET','gate_counts':{'量能不足':3,'SECRET6148':5}}
                (private/'shadow-v108-history.jsonl').write_text((json.dumps(raw)+'\n')*2,encoding='utf-8')
                atomic(private/'shadow-v108-status.json',raw)
                connections=[]
                connect=sqlite3.connect
                def tracked(*args, **kwargs):
                    db=connect(*args, **kwargs); connections.append(db); return db
                with patch.object(sqlite3, 'connect', side_effect=tracked):
                    health=report(local,private,p,fetch=False)
                self.assertTrue(connections)
                for db in connections:
                    with self.assertRaises(sqlite3.ProgrammingError):
                        db.execute('SELECT 1')
                self.assertEqual(read_json(local/'research_summary.json')['scan_records'],1)
                with patch(__name__+'.drive_root',return_value=cloud): self.assertEqual(sync(local,health),'written_to_local_drive_mount')
                out=(cloud/'collector_status.json').read_text(encoding='utf-8')
                self.assertNotIn('SECRET',out); self.assertNotIn('qualified_count',out); self.assertNotIn('gate',out)
                self.assertEqual(len(list(cloud.iterdir())),1)
        def test_bad_input(self):
            self.assertIsNone(normalize({'version':'bad'}))
            self.assertIsNone(normalize({'version':'V1.08.2-shadow','checked_at':'invalid'}))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    return 0 if result.wasSuccessful() else 1


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('action',choices=('install','run','selftest','status')); args=parser.parse_args()
    if args.action=='selftest': return selftest()
    if args.action=='install':
        if selftest(): return 1
        install(); return 0
    if args.action=='status':
        print(json.dumps(read_json(LOCAL/'collector_status.json'),ensure_ascii=False,indent=2))
        if (LOCAL/'sync_status.json').is_file(): print(json.dumps(read_json(LOCAL/'sync_status.json'),ensure_ascii=False,indent=2))
        return 0
    health=report(LOCAL,PRIVATE,PROJECT); cloud=sync(LOCAL,health)
    atomic(LOCAL/'sync_status.json', {'checked_at':now().isoformat(),'drive_sync':cloud})
    print('DRIVE_SYNC='+cloud); return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Keep potentially private path/exception detail out of remote logs.
        print('V109_ERROR='+type(exc).__name__)
        sys.exit(1)
