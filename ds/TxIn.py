from typing import (NamedTuple, Union)

from ds.OutPoint import OutPoint


class TxIn(NamedTuple):
    """Inputs to a Transaction."""
    # A reference to the output we're spending(UTXO).
    # This is None for coinbase transactions.
    to_spend: Union[OutPoint, None]

    # temparary: OutPoint = NamedTuple('OutPoint', [('txid', str), ('txout_idx', int)]) address and index.

    # define scriptSig here
    # the scriptSig which un locks the TxOut for spending.

    signature_script: bytes

    # A sender-defined sequence number which allows us replacement of the txn
    # if desired.
    sequence: int
