"""Exercise actual functions without importing the API's database startup side effect."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

APP=Path(__file__).resolve().parents[1]/'app'
def load_functions(file,namespace):
    tree=ast.parse((APP/file).read_text())
    tree.body=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name=='auth') or (file=='research.py' and isinstance(n,(ast.FunctionDef,ast.Assign)))]
    exec(compile(tree,str(APP/file),'exec'),namespace)
    return namespace

@pytest.mark.parametrize('key',[None,'','dev-only-change-me','REQUIRED_KEY','REQUIRED'])
def test_unconfigured_auth_rejects_even_matching_key(key):
    class Denied(Exception):pass
    ns=load_functions('main.py',{'settings':SimpleNamespace(dealos_api_key=key),'Header':lambda x:x,'HTTPException':Denied,'FastAPI':Mock(),'SessionLocal':Mock()})
    with pytest.raises(Denied):ns['auth'](key)

def test_configured_auth_rejects_wrong_key():
    class Denied(Exception):pass
    ns=load_functions('main.py',{'settings':SimpleNamespace(dealos_api_key='fixture-valid-key'),'Header':lambda x:x,'HTTPException':Denied,'FastAPI':Mock(),'SessionLocal':Mock()})
    assert ns['auth']('fixture-valid-key') is True
    with pytest.raises(Denied):ns['auth']('wrong')

@pytest.mark.parametrize('operation',['run_research','scan_lane'])
def test_research_uses_responses_web_search_and_accounts_usage(operation):
    calls=[];response=SimpleNamespace(output_text='{"result":"fixture"}')
    client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:(calls.append(kw) or response)))
    budget=Mock();usage=Mock()
    ns=load_functions('research.py',{'json':json,'settings':SimpleNamespace(openai_standard_model='fixture-model'),'assert_openai_budget':budget,'record_openai_usage':usage,'lanes':lambda:{'private_market':{'fixture':{'scan_prompt':'fixture'}}},'lane_enabled':lambda lane:True})
    ns['_client']=lambda:client
    assert ns[operation]('fixture')=={'result':'fixture'}
    budget.assert_called_once_with(0.10)
    assert calls[0]['tools']==[{'type':'web_search'}]
    assert calls[0]['text']['format']['type']=='json_schema'
    assert 'input' in calls[0] and 'messages' not in calls[0]
    assert usage.call_args.args[2] is response

def test_budget_denial_prevents_provider_call():
    ns=load_functions('research.py',{'json':json,'settings':SimpleNamespace(),'assert_openai_budget':Mock(side_effect=ValueError('budget denied'))})
    client=Mock();ns['_client']=client
    with pytest.raises(ValueError):ns['run_research']('fixture')
    client.assert_not_called()
