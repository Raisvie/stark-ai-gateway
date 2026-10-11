import pytest
from fastapi.testclient import TestClient

from backend import analytics, audit
from backend.detector import cpf_valid, inspect, luhn_valid, sanitize
from backend.education_agent import chat
from backend.policy_engine import Context, decide
from backend.validation import ADVERSARIAL, base_cases, run_suite


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "LOG", tmp_path / "audit.jsonl")
    monkeypatch.setenv("IRIS_OFFLINE", "1")


def test_base_suite_all_correct():
    assert all(r.status == "Correto" for r in run_suite(base_cases()))


def test_adversarial_never_exposes():
    assert all(r.status != "EXPOSIÇÃO" for r in run_suite(ADVERSARIAL))


def test_replay_blocks_every_historical_critical_event():
    s = analytics.replay_summary(analytics.replay())
    assert s["criticos"] == 74 and s["criticos_bloqueados"] == 74


def test_secret_blocked_even_in_approved_tool():
    d = decide(Context(tool="Copiloto de Produtividade", purpose="Criar rascunho"), inspect("token: ghp_" + "a" * 30))
    assert d.action == "BLOCK" and d.rule_id == "R03"


def test_monitor_mode_registers_without_enforcing():
    d = decide(Context(tool="IA Pública A"), inspect("CPF 529.982.247-25"), enforce=False)
    assert d.action == "BLOCK" and not d.enforced


def test_plain_admin_request_flows_freely():
    d = decide(Context(tool="Copiloto de Produtividade", purpose="Criar rascunho"),
               inspect("Escreva um e-mail de boas-vindas para a nova analista do time."))
    assert d.action == "ALLOW"


def test_validators_and_masking():
    assert cpf_valid("529.982.247-25") and not cpf_valid("000.000.000-00")
    assert luhn_valid("4111 1111 1111 1111")
    out = sanitize("Responda a João Pereira (joao@x.com) CPF 529.982.247-25")
    assert "João" not in out and "joao@x.com" not in out and "529" not in out


def test_audit_chain_detects_tampering():
    ctx = Context(tool="IA Pública A")
    for txt in ["CPF 529.982.247-25", "ata de reunião interna"]:
        insp = inspect(txt)
        audit.record(ctx, insp, decide(ctx, insp), txt)
    assert audit.verify_chain() == (True, 2)
    lines = audit.LOG.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"BLOCK"', '"ALLOW"')
    audit.LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert audit.verify_chain()[0] is False


def test_agent_never_receives_secret_or_pii():
    turn = chat("minha senha: hunter2", Context(), [])
    assert turn.sanitized == "" and "credencial" in turn.reply
    turn = chat("Como respondo o cliente CPF 529.982.247-25?", Context(), [])
    assert "529.982" not in turn.sanitized


def test_api_inspect_blocks_and_hides_content():
    from api import app
    r = TestClient(app).post("/v1/inspect", json={"tool": "IA Pública B", "content": "Folha: salário R$ 9.000, CPF 529.982.247-25"})
    body = r.json()
    assert r.status_code == 200 and body["action"] == "BLOCK" and body["content_to_send"] is None
