import binascii
import time
import json
import hashlib
import threading
import logging
import socketserver
import socket
import random
import os
from functools import lru_cache, wraps
from typing import (
    Iterable, NamedTuple, Dict, Mapping, Union, get_type_hints, Tuple,
    Callable)
from _thread import RLock

from params.Params import Params

logging.basicConfig(
    level=getattr(logging, os.environ.get('TC_LOG_LEVEL', 'INFO')),
    format='[%(asctime)s][%(module)s:%(lineno)d] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)



class Utils(object):

    @classmethod
    def serialize(cls, obj) -> str:
        """NamedTuple-flavored serialization to JSON."""
        def contents_to_primitive(o):
            if hasattr(o, '_asdict'):
                o = {**o._asdict(), '_type': type(o).__name__}
            elif isinstance(o, (list, tuple)):
                return [contents_to_primitive(i) for i in o]
            elif isinstance(o, bytes):
                return binascii.hexlify(o).decode()
            elif not isinstance(o, (dict, bytes, str, int, float,type(None))):
                raise ValueError(f"Can't serialize {o}")
            if isinstance(o, Mapping):
                for k, v in o.items():
                    o[k] = contents_to_primitive(v)
            return o
        return json.dumps(contents_to_primitive(obj), sort_keys=True, separators=(',', ':'))

    @classmethod
    def deserialize(cls, serialized: str, gs: dict) -> object:
        """NamedTuple-flavored serialization from JSON."""

        def contents_to_objs(o):
            if isinstance(o, list):
                return [contents_to_objs(i) for i in o]
            elif not isinstance(o, Mapping):
                return o

            _type = gs[o.pop('_type', None)]
            bytes_keys = {
                k for k, v in get_type_hints(_type).items() if v == bytes}

            for k, v in o.items():
                o[k] = contents_to_objs(v)

                if k in bytes_keys:
                    o[k] = binascii.unhexlify(o[k]) if o[k] else o[k]

            return _type(**o)
        return contents_to_objs(json.loads(serialized))

    @classmethod
    def sha256d(cls, s: Union[str, bytes]) -> str:
        """A double SHA-256 hash."""
        if not isinstance(s, bytes):
            s = s.encode()

        return hashlib.sha256(hashlib.sha256(s).digest()).hexdigest()

    @classmethod
    def encode_chain_data(cls, chain: Iterable[NamedTuple]) -> bytes:
        """Our protocol is: first 4 bytes signify msg length."""
        def int_to_20bytes(a: int) -> bytes:
            int_str = str(a)
            int_str = '0'*(20 - len(int_str)) + int_str
            return int_str.encode()
        block_len = len(chain)
        to_send = cls.serialize(chain).encode()
        msg_len = len(to_send)
        return int_to_20bytes(block_len) + int_to_20bytes(msg_len) + to_send

    @classmethod
    def encode_socket_data(cls, data: object) -> bytes:
        """Our protocol is: first 4 bytes signify msg length."""
        def int_to_8bytes(a: int) -> bytes:
            return binascii.unhexlify(f"{a:0{8}x}")
        to_send = Utils.serialize(data).encode()
        return int_to_8bytes(len(to_send)) + to_send

    @classmethod
    def send_to_peer(cls, data, peer, itself: bool = False) -> int:

        from p2p.Message import Actions
        from p2p.Message import Message

        tries_left = int(Params.TRIES_MAXIMUM)

        if tries_left <= 0:
            logger.info(f'[utils] initial tries_left is less than 1, will not send data to other nodes')
            return -2

        while tries_left > 0:

            try:
                if not itself:
                    #logger.info(f'[utils] begin to create socket connection with peer {peer}' )
                    pass
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: #socket.create_connection(peer(), timeout=30) as s:
                    s.connect(peer())
                    #logger.info(f'[Utils] succeed to create socket connection with {peer}')
                    s.sendall(cls.encode_socket_data(data))
                    #logger.info(f'[Utils] succeed to send data to {peer}')
            except ConnectionRefusedError as e:
                logger.exception(f'[utils] {repr(e)}, failed to send to {peer} data about {Actions.num2name[str(data.action)] if hasattr(data, "action") else None} '
                                 f' in {Params.TRIES_MAXIMUM+1-tries_left}th time')
                try:
                    s.close()
                except:
                    pass
                tries_left -= 1
                time.sleep(2)
                if tries_left <= 0:
                    return 1
            except TimeoutError as e:
                logger.exception(f'[utils] {repr(e)}, failed to send to {peer} data about {Actions.num2name[str(data.action)] if hasattr(data, "action") else None} '
                                 f' in {Params.TRIES_MAXIMUM+1-tries_left}th time')
                try:
                    s.close()
                except:
                    pass
                tries_left -= 1
                time.sleep(2)
                if tries_left <= 0:
                    return 2
            except BrokenPipeError as e:
                logger.exception(f'[utils] {repr(e)}, failed to send to {peer} data about {Actions.num2name[str(data.action)] if hasattr(data, "action") else None} '
                                 f' in {Params.TRIES_MAXIMUM+1-tries_left}th time')
                try:
                    s.close()
                except:
                    pass
                tries_left -= 1
                time.sleep(2)
                if tries_left <= 0:
                    return 3
            except Exception as e:
                logger.exception(f'[utils] {repr(e)}, failed to send to {peer} data about {Actions.num2name[str(data.action)] if hasattr(data, "action") else None} '
                                 f' in {Params.TRIES_MAXIMUM+1-tries_left}th time')
                try:
                    s.close()
                except:
                    pass
                tries_left -= 1
                time.sleep(2)
                if tries_left <= 0:
                    return -1
            else:
                try:
                    s.close()
                except:
                    pass
                if not itself:
                    if hasattr(data, "action") and data.action != 10:
                        logger.info(f'[utils] succeed in sending to {peer} data about {Actions.num2name[str(data.action)]}'
                                f' in {Params.TRIES_MAXIMUM+1-tries_left}th time')
                return 0
    @classmethod
    def is_peer_valid(cls, peer) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect(peer())
        except ConnectionRefusedError:
            try:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
            except:
                pass
            return False
        except Exception:
            try:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
            except:
                pass
        else:
            try:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
            except:
                pass
            return True
        return True


    @classmethod
    def read_all_from_socket(cls, req, gs) -> object:
        data = b''
        # Our protocol is: first 4 bytes signify msg length.
        msg_len = int(binascii.hexlify(req.recv(4) or b'\x00'), 16)

        while msg_len > 0:
            tdat = req.recv(1024)
            data += tdat
            msg_len -= len(tdat)

        return cls.deserialize(data.decode(), gs) if data else None



