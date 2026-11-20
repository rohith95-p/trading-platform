"""Execute only three reviewed management modules under the guarded CPython3.13 loader."""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import types
from datetime import datetime,timezone


def main():
    root = Path(__file__).resolve().parents[2]
    extraction = Path('C:/Users/rohit/OneDrive/Documents/Desktop/WMC Genesis')
    sys.path.insert(0,str(extraction/'strategy_research'))
    from load_original import load_original
    load_original()
    manifest = {r['file'].replace('\\','/'):r['sha256'] for r in json.loads((extraction/'application_manifest.json').read_text())}
    package = types.ModuleType('Trade_Manager')
    package.__path__ = [str(extraction/'application_bytecode/Trade_Manager')]
    sys.modules['Trade_Manager'] = package
    hashes = {}
    for name in ('config','trade_state','trade_manager'):
        relative = 'Trade_Manager/'+name+'.pyc'
        path = extraction/'application_bytecode'/relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=manifest[relative]:
            raise ValueError('Original management module changed')
        hashes[relative] = digest
        full = 'Trade_Manager.'+name
        spec = importlib.util.spec_from_file_location(full,path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[full] = module
        setattr(package,name,module)
        spec.loader.exec_module(module)
    from Trade_Manager.trade_manager import TradeManager
    from Trade_Manager.trade_state import OpenTrade,TradeDirection
    sys.path.insert(0,str(root/'scripts/research'))
    from genesis_management import ManagementState,management_actions
    rng = random.Random(7180313)
    manager = TradeManager()
    for i in range(5000):
        side = rng.choice((-1,1))
        entry,risk = 2000.,10**rng.uniform(-2,1)
        initial = entry-side*risk
        stop = entry+side*rng.uniform(-2,2)*risk
        price = entry+side*rng.uniform(-3,5)*risk
        atr,peak = rng.uniform(.01,5)*risk,rng.uniform(0,5)*risk
        partial,be = rng.choice((True,False)),rng.choice((True,False))
        trade = OpenTrade(ticket=1,symbol='XAUUSD',direction=TradeDirection.BUY if side==1 else TradeDirection.SELL,
            entry_price=entry,lot_size=.02,initial_sl=initial,current_sl=stop,take_profit=entry+side*3*risk,
            open_time=datetime(2020,1,1,tzinfo=timezone.utc),current_price=price,
            peak_profit_price_units=peak,partial_close_done=partial,breakeven_done=be)
        actual = manager.evaluate(trade,atr)
        expected = management_actions(ManagementState(side,entry,initial,stop,price,atr,peak,partial,be))
        actions = [dict(action=a.action.value,new_sl=float(a.new_sl),close_percent=float(a.close_percent)) for a in actual.actions]
        if actions!=expected['actions'] or abs(actual.updated_peak_profit-expected['peak'])>1e-9:
            raise AssertionError((i,actions,expected))
    result = dict(cases=5000,all_matched=True,python=sys.version,management_bytecode_hashes=hashes,
                  port_sha256=hashlib.sha256((root/'scripts/research/genesis_management.py').read_bytes()).hexdigest(),
                  note='Action/peak parity only; does not reproduce broker acceptance, cadence or full application.')
    (root/'research/results/genesis_2026-11-11/manager_parity.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
