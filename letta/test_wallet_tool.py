"""
Unit tests for letta/wallet_tool.py

This suite targets the changes introduced in the "web3.py v7 drift" fix:

- `SelfSovereignWallet.sign_transaction` now sends
  `signed_tx.raw_transaction` (web3.py v7 attribute) instead of the
  removed `signed_tx.rawTransaction` (v6) attribute, and accepts `data`
  as either `bytes` or a 0x-prefixed hex `str`.
- `SelfSovereignWallet.anchor_state` and `SelfSovereignWallet.submit_liveness_proof`
  now call `contract.encode_abi(fn_name, args=...)` (positional function
  name) instead of the removed `contract.encodeABI(fn_name=..., args=...)`,
  and pass the resulting hex string straight through to
  `sign_transaction` without re-encoding it with `.encode()` (which used
  to corrupt the calldata by turning the hex *text* into UTF-8 bytes).

Web3/eth-account are mocked throughout so these tests run fully offline
and do not require network access or a funded account.

Run with:
    pytest letta/test_wallet_tool.py -v
"""

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from wallet_tool import SelfSovereignWallet  # noqa: E402


TEST_PRIVATE_KEY = "0x" + "11" * 32
EXECUTOR_ADDRESS = "0xExecutorAddress0000000000000000000000"
CONTRACT_ADDRESS = "0xContractAddress0000000000000000000000"
TOKEN_ID = 7


class _SignedTx:
    """
    Stand-in for eth_account's SignedTransaction.

    Deliberately exposes ONLY `raw_transaction` (the web3.py v7 name) and
    NOT `rawTransaction` (the removed v6 name), so that if the code under
    test regresses to the old attribute, the test fails with a loud
    AttributeError instead of silently passing via a MagicMock's
    auto-attribute behavior.
    """

    def __init__(self, raw: bytes):
        self.raw_transaction = raw


def make_wallet(private_key=TEST_PRIVATE_KEY, **overrides):
    """Construct a SelfSovereignWallet with Web3/Account fully mocked."""
    kwargs = dict(
        private_key=private_key,
        contract_address=CONTRACT_ADDRESS,
        token_id=TOKEN_ID,
    )
    kwargs.update(overrides)

    with patch("wallet_tool.Web3") as MockWeb3, patch("wallet_tool.Account") as MockAccount:
        mock_w3 = MagicMock()
        MockWeb3.return_value = mock_w3
        MockWeb3.HTTPProvider.return_value = MagicMock()

        mock_account = MagicMock()
        mock_account.address = EXECUTOR_ADDRESS
        MockAccount.from_key.return_value = mock_account

        wallet = SelfSovereignWallet(**kwargs)

    return wallet


def configure_sign_transaction_mocks(wallet, raw_tx=b"\xde\xad\xbe\xef", tx_hash=b"\xaa" * 32,
                                      block_number=123, gas_used=21000, status=1,
                                      estimated_gas=21000, nonce=5, gas_price=1_000_000_000):
    """Wire up wallet.w3 / wallet.account mocks for a successful sign_transaction call."""
    wallet.w3.eth.get_transaction_count.return_value = nonce
    wallet.w3.eth.estimate_gas.return_value = estimated_gas
    wallet.w3.eth.gas_price = gas_price
    wallet.account.sign_transaction.return_value = _SignedTx(raw_tx)
    wallet.w3.eth.send_raw_transaction.return_value = tx_hash
    wallet.w3.eth.wait_for_transaction_receipt.return_value = {
        "transactionHash": tx_hash,
        "blockNumber": block_number,
        "gasUsed": gas_used,
        "status": status,
    }


# ---------------------------------------------------------------------------
# sign_transaction
# ---------------------------------------------------------------------------

class TestSignTransaction:
    def test_uses_raw_transaction_attribute_not_camel_case(self):
        """send_raw_transaction must be called with signed_tx.raw_transaction."""
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet, raw_tx=b"\xde\xad\xbe\xef")

        result = wallet.sign_transaction(to=CONTRACT_ADDRESS, value=0, data=b"\x01\x02", gas_limit=21000)

        wallet.w3.eth.send_raw_transaction.assert_called_once_with(b"\xde\xad\xbe\xef")
        assert result == {
            "tx_hash": (b"\xaa" * 32).hex(),
            "block_number": 123,
            "gas_used": 21000,
            "status": "success",
        }

    def test_status_failed_when_receipt_status_is_zero(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet, status=0)

        result = wallet.sign_transaction(to=CONTRACT_ADDRESS, gas_limit=21000)

        assert result["status"] == "failed"

    def test_accepts_bytes_data(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, data=b"\xca\xfe", gas_limit=21000)

        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["data"] == b"\xca\xfe"

    def test_accepts_hex_string_data(self):
        """data may be a 0x-prefixed hex string (as returned by encode_abi in v7)."""
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, data="0xdeadbeef", gas_limit=21000)

        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["data"] == "0xdeadbeef"
        assert isinstance(sent_tx["data"], str)

    def test_default_data_is_empty_bytes(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, gas_limit=21000)

        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["data"] == b""

    def test_estimates_gas_when_gas_limit_not_provided(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet, estimated_gas=54321)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, value=100, data=b"\x01")

        wallet.w3.eth.estimate_gas.assert_called_once_with({
            "to": CONTRACT_ADDRESS,
            "from": EXECUTOR_ADDRESS,
            "value": 100,
            "data": b"\x01",
        })
        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["gas"] == 54321

    def test_skips_gas_estimation_when_gas_limit_provided(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, gas_limit=99999)

        wallet.w3.eth.estimate_gas.assert_not_called()
        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["gas"] == 99999

    def test_tx_includes_nonce_chain_id_and_gas_price(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet, nonce=42, gas_price=7)

        wallet.sign_transaction(to=CONTRACT_ADDRESS, value=1, gas_limit=21000)

        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["nonce"] == 42
        assert sent_tx["gasPrice"] == 7
        assert sent_tx["chainId"] == wallet.chain_id
        assert sent_tx["to"] == CONTRACT_ADDRESS
        assert sent_tx["value"] == 1

    def test_raises_when_no_account_available(self):
        wallet = make_wallet(private_key=None)
        wallet.account = None
        wallet.executor_address = None

        with pytest.raises(ValueError, match="No private key available"):
            wallet.sign_transaction(to=CONTRACT_ADDRESS, value=0)

    def test_waits_for_and_returns_receipt(self):
        wallet = make_wallet()
        configure_sign_transaction_mocks(wallet, tx_hash=b"\x99" * 32)

        result = wallet.sign_transaction(to=CONTRACT_ADDRESS, gas_limit=21000)

        wallet.w3.eth.wait_for_transaction_receipt.assert_called_once_with(b"\x99" * 32)
        assert result["tx_hash"] == (b"\x99" * 32).hex()


# ---------------------------------------------------------------------------
# anchor_state
# ---------------------------------------------------------------------------

class TestAnchorState:
    def _mock_contract(self, wallet, encoded_data="0xf00dbabe"):
        contract = MagicMock()
        contract.encode_abi.return_value = encoded_data
        wallet.w3.eth.contract.return_value = contract
        return contract

    def test_calls_encode_abi_with_positional_fn_name(self):
        """
        Regression test: web3.py v7 renamed encodeABI(fn_name=..., args=...)
        to encode_abi(fn_name, args=...) with the function name passed
        positionally.
        """
        wallet = make_wallet()
        contract = self._mock_contract(wallet)

        with patch.object(wallet, "sign_transaction") as mock_sign:
            wallet.anchor_state({"foo": "bar"}, "ipfs://state-uri")

        assert contract.encode_abi.call_count == 1
        call = contract.encode_abi.call_args
        assert call.args[0] == "anchorState"
        assert "fn_name" not in call.kwargs

    def test_passes_correct_args_to_encode_abi(self):
        wallet = make_wallet()
        contract = self._mock_contract(wallet)
        state_data = {"b": 2, "a": 1}

        with patch.object(wallet, "sign_transaction"):
            wallet.anchor_state(state_data, "ipfs://state-uri")

        expected_hash = hashlib.sha256(
            json.dumps(state_data, sort_keys=True).encode()
        ).digest()
        call = contract.encode_abi.call_args
        assert call.kwargs["args"] == [TOKEN_ID, expected_hash, "ipfs://state-uri"]

    def test_passes_encoded_hex_string_through_unmodified(self):
        """
        Regression test: the old code did
        `data.encode() if isinstance(data, str) else data`, which corrupted
        the calldata by turning the hex *text* into UTF-8 bytes. The fixed
        code must forward the exact string returned by encode_abi.
        """
        wallet = make_wallet()
        self._mock_contract(wallet, encoded_data="0xf00dbabe")

        with patch.object(wallet, "sign_transaction") as mock_sign:
            wallet.anchor_state({"foo": "bar"}, "ipfs://state-uri")

        mock_sign.assert_called_once_with(to=CONTRACT_ADDRESS, data="0xf00dbabe")
        passed_data = mock_sign.call_args.kwargs["data"]
        assert isinstance(passed_data, str)
        assert passed_data != "0xf00dbabe".encode()

    def test_full_flow_result_matches_sign_transaction_result(self):
        """End-to-end: anchor_state's return value is whatever sign_transaction returns."""
        wallet = make_wallet()
        self._mock_contract(wallet, encoded_data="0xabc123")
        configure_sign_transaction_mocks(wallet)

        result = wallet.anchor_state({"x": 1}, "ipfs://uri")

        assert result["status"] == "success"
        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["data"] == "0xabc123"
        assert sent_tx["to"] == CONTRACT_ADDRESS


# ---------------------------------------------------------------------------
# submit_liveness_proof
# ---------------------------------------------------------------------------

class TestSubmitLivenessProof:
    def _mock_contract(self, wallet, encoded_data="0xbeef0001"):
        contract = MagicMock()
        contract.encode_abi.return_value = encoded_data
        wallet.w3.eth.contract.return_value = contract
        return contract

    def test_calls_encode_abi_with_positional_fn_name(self):
        wallet = make_wallet()
        contract = self._mock_contract(wallet)

        with patch.object(wallet, "sign_transaction"):
            wallet.submit_liveness_proof(attestation=b"\x01" * 32)

        assert contract.encode_abi.call_count == 1
        call = contract.encode_abi.call_args
        assert call.args[0] == "submitLivenessProof"
        assert "fn_name" not in call.kwargs

    def test_passes_correct_args_to_encode_abi(self):
        wallet = make_wallet()
        contract = self._mock_contract(wallet)
        attestation = b"\x02" * 32

        with patch.object(wallet, "sign_transaction"):
            wallet.submit_liveness_proof(attestation=attestation)

        call = contract.encode_abi.call_args
        assert call.kwargs["args"] == [TOKEN_ID, attestation]

    def test_passes_encoded_hex_string_through_unmodified(self):
        wallet = make_wallet()
        self._mock_contract(wallet, encoded_data="0xbeef0001")

        with patch.object(wallet, "sign_transaction") as mock_sign:
            wallet.submit_liveness_proof(attestation=b"\x03" * 32)

        mock_sign.assert_called_once_with(to=CONTRACT_ADDRESS, data="0xbeef0001")
        passed_data = mock_sign.call_args.kwargs["data"]
        assert isinstance(passed_data, str)

    def test_generates_attestation_when_none_provided(self):
        """When no attestation is given, one is derived from a signed message (unchanged logic)."""
        wallet = make_wallet()
        self._mock_contract(wallet)
        wallet.w3.eth.block_number = 999

        signed_message = MagicMock()
        signed_message.signature = b"\x07" * 65
        wallet.account.sign_message.return_value = signed_message

        with patch.object(wallet, "sign_transaction"):
            wallet.submit_liveness_proof(attestation=None)

        wallet.account.sign_message.assert_called_once()

    def test_full_flow_result_matches_sign_transaction_result(self):
        wallet = make_wallet()
        self._mock_contract(wallet, encoded_data="0xdead0002")
        configure_sign_transaction_mocks(wallet)

        result = wallet.submit_liveness_proof(attestation=b"\x04" * 32)

        assert result["status"] == "success"
        sent_tx = wallet.account.sign_transaction.call_args[0][0]
        assert sent_tx["data"] == "0xdead0002"