from ds.Block import Block
from utils.Utils import Utils

import time
import threading
import logging
import os
from typing import Union


logging.basicConfig(
    level=getattr(logging, os.environ.get('TC_LOG_LEVEL', 'INFO')),
    format='[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

class PoW(object):

    @classmethod
    def mine(cls, block: Block, mine_interrupt: threading.Event = None) -> Union[Block, None]:
        start = time.time()
        nonce = 0
        target = (1 << (256 - block.bits))
        mine_interrupt.clear()

        logger.info(f'[consensus] mining after block {block.prev_block_hash}')
        while int(Utils.sha256d(block.header(nonce)), 16) >= target:
            nonce += 1

            if mine_interrupt.is_set():
                logger.info(f'[consensus] mining interrupted +++ {nonce}')
                mine_interrupt.clear()
                return None

        block = block._replace(nonce=nonce)
        duration = max(time.time() - start, 0.0001)
        khs = (block.nonce // duration) // 1000
        logger.info(
            f'[consensus] mining block found at nonce={nonce} using {round(duration, 4)} s at rate {khs} KH/s: {block.id}')

        return block
