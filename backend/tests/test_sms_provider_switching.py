import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models.entities import (
    User, UserRole, Medicine, Ward, Inventory, Bill, NotificationLog
)
from app.services.auth_service import create_access_token
from app.services.sms_provider import (
    SMSGatewayManager, sms_gateway, normalize_provider_id
)

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    yield db
    db.close()

@pytest.fixture(scope="module")
def pharmacist_auth():
    token = create_access_token("pharmacist", "PHARMACIST", "Dr. Sarah Alston", company_id=1, branch_id=1)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def data_manager_auth():
    token = create_access_token("data_manager", "DATA_MANAGER", "Alex Chen", company_id=1, branch_id=1)
    return {"Authorization": f"Bearer {token}"}

def test_1_provider_normalization():
    """Verify normalize_provider_id handles diverse case & label formats cleanly."""
    assert normalize_provider_id("fast2sms") == "fast2sms"
    assert normalize_provider_id("Fast2SMS (India)") == "fast2sms"
    assert normalize_provider_id("Fast2SMS India Gateway") == "fast2sms"
    assert normalize_provider_id("twilio") == "twilio"
    assert normalize_provider_id("Twilio REST API") == "twilio"
    assert normalize_provider_id("Twilio Live SMS Gateway") == "twilio"
    assert normalize_provider_id("custom_gateway") == "custom_gateway"
    assert normalize_provider_id("Custom HTTP Gateway") == "custom_gateway"
    assert normalize_provider_id("medisentinel_direct") == "medisentinel_direct"
    assert normalize_provider_id("MediSentinel Direct") == "medisentinel_direct"
    assert normalize_provider_id("") == "medisentinel_direct"
    assert normalize_provider_id(None) == "medisentinel_direct"

def test_2_incomplete_config_rejected_without_activation(pharmacist_auth):
    """
    Verify activating Fast2SMS or Twilio without minimum required credentials
    raises HTTP 400 'Provider configuration incomplete' and does NOT activate.
    """
    # Create temporary manager instance with empty keys
    temp_gw = SMSGatewayManager()
    temp_gw._fast2sms_key = ""
    temp_gw._active_provider = "medisentinel_direct"

    # Attempt to activate Fast2SMS without key
    with pytest.raises(ValueError) as excinfo:
        temp_gw.update_config(provider="fast2sms")
    assert "Provider configuration incomplete" in str(excinfo.value)
    assert temp_gw.get_active_provider_id() == "medisentinel_direct"

    # Same check via HTTP API
    resp = client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "twilio", "twilio_sid": "", "twilio_token": "", "twilio_phone": ""}
    )
    # If twilio was not already fully configured with credentials, it must reject with 400
    if not (sms_gateway._twilio_sid and sms_gateway._twilio_auth and sms_gateway._twilio_from):
        assert resp.status_code == 400
        assert "Provider configuration incomplete" in resp.json()["detail"]

def test_3_switch_to_fast2sms_and_persist(pharmacist_auth):
    """Verify configuring Fast2SMS activates Fast2SMS and saves credentials."""
    resp = client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={
            "provider": "fast2sms",
            "fast2sms_key": "test_fast2sms_secret_key_123"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_fast2sms"] is True
    assert "Fast2SMS" in data["active_provider"]
    assert data["active_provider_id"] == "fast2sms"

    # Verify get_sms_config reflects Fast2SMS
    get_res = client.get("/api/reminders/sms-config", headers=pharmacist_auth)
    assert get_res.status_code == 200
    assert get_res.json()["active_provider_id"] == "fast2sms"

def test_4_switch_to_twilio_preserves_fast2sms_key(pharmacist_auth):
    """
    Verify switching to Twilio activates Twilio, AND Fast2SMS credentials remain preserved.
    """
    resp = client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={
            "provider": "twilio",
            "twilio_sid": "ACtest_account_sid_999",
            "twilio_token": "test_auth_token_888",
            "twilio_phone": "+12025550199"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_twilio"] is True
    assert data["has_fast2sms"] is True  # Preserved!
    assert "Twilio" in data["active_provider"]
    assert data["active_provider_id"] == "twilio"
    assert data["twilio_from"] == "+12025550199"

def test_5_switch_back_to_fast2sms_without_reentering_credentials(pharmacist_auth):
    """
    Verify switching back to Fast2SMS succeeds without re-typing the key
    because separate credentials were preserved!
    """
    resp = client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "fast2sms"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_provider_id"] == "fast2sms"
    assert "Fast2SMS" in data["active_provider"]
    assert data["has_twilio"] is True  # Twilio still preserved!
    assert data["has_fast2sms"] is True

def test_6_switch_to_medisentinel_direct(pharmacist_auth):
    """Verify switching to MediSentinel Direct succeeds seamlessly."""
    resp = client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "medisentinel_direct"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_provider_id"] == "medisentinel_direct"
    assert "MediSentinel Direct" in data["active_provider"]

def test_7_test_connection_endpoint(pharmacist_auth):
    """Verify test-connection endpoint checks provider reachability without patient SMS."""
    # Test MediSentinel Direct
    res_direct = client.post(
        "/api/reminders/sms-config/test",
        headers=pharmacist_auth,
        json={"provider": "medisentinel_direct"}
    )
    assert res_direct.status_code == 200
    assert res_direct.json()["success"] is True
    assert "Connection successful" in res_direct.json()["message"]

    # Test Fast2SMS with mock key
    res_f2s = client.post(
        "/api/reminders/sms-config/test",
        headers=pharmacist_auth,
        json={"provider": "fast2sms", "fast2sms_key": "mock_key_test"}
    )
    assert res_f2s.status_code == 200
    assert res_f2s.json()["success"] is True

def test_8_active_provider_is_strictly_used_without_waterfall(db_session: Session, pharmacist_auth):
    """
    Verify that when MediSentinel Direct is active, dispatch strictly uses MediSentinel Direct
    and does NOT waterfall or route to another provider.
    """
    # Ensure active provider is medisentinel_direct
    client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "medisentinel_direct"}
    )

    med = db_session.query(Medicine).first()
    ward = db_session.query(Ward).first()
    inv = db_session.query(Inventory).filter(Inventory.medicine_id == med.id, Inventory.ward_id == ward.id).first()
    if not inv or inv.current_stock < 5:
        if not inv:
            inv = Inventory(medicine_id=med.id, ward_id=ward.id, current_stock=20, reorder_level=5)
            db_session.add(inv)
        else:
            inv.current_stock = 20
        db_session.commit()
        db_session.refresh(inv)

    payload = {
        "ward_id": ward.id,
        "patient_name": "Karthik Subramanian",
        "patient_phone": "+919840199887",
        "notification_consent": True,
        "items": [
            {
                "medicine_id": med.id,
                "inventory_id": inv.id,
                "quantity": 1,
                "days_supply": 7,
                "unit_price": 20.0
            }
        ]
    }

    res = client.post("/api/billing/bills", json=payload, headers=pharmacist_auth)
    assert res.status_code == 201
    b_data = res.json()
    assert b_data["sms_notification"]["provider"] in ("MediSentinel Carrier Direct SMS Gateway", "MediSentinel Direct Carrier SMS Gateway", "MediSentinel Direct SMS Gateway")
    assert b_data["sms_notification"]["status"] == "QUEUED"

def test_9_historical_notification_logs_unaltered_by_provider_switch(db_session: Session, pharmacist_auth):
    """Verify switching providers does not modify existing NotificationLog historical records."""
    # Create or find a historical log with a fixed provider
    old_log = NotificationLog(
        bill_id=None,
        channel="SMS",
        recipient="+919840199887",
        masked_phone_number="+91 ******9887",
        message="Historical message from Fast2SMS",
        provider="Fast2SMS India Gateway",
        provider_message_id="F2S-HIST-001",
        status="SENT",
        created_at=datetime.utcnow(),
        sent_at=datetime.utcnow()
    )
    db_session.add(old_log)
    db_session.commit()
    db_session.refresh(old_log)
    log_id = old_log.id

    # Switch active provider to twilio
    client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "twilio"}
    )

    # Re-fetch old_log and verify its provider is STILL 'Fast2SMS India Gateway'
    db_session.expire_all()
    re_log = db_session.query(NotificationLog).filter(NotificationLog.id == log_id).first()
    assert re_log.provider == "Fast2SMS India Gateway"
    assert re_log.provider_message_id == "F2S-HIST-001"

    # Reset back to medisentinel_direct
    client.post(
        "/api/reminders/sms-config",
        headers=pharmacist_auth,
        json={"provider": "medisentinel_direct"}
    )
